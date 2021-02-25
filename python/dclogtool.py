#!/usr/bin/env python3
"""
digitalcorpora log tool.

"""

import os
import pymysql
import weblog.schema
import weblog.weblog
import aws_secrets
import ctools.dbfile as dbfile
import ctools.clogging as clogging
import urllib.parse
import boto3
import hashlib
import multiprocessing
import json
import logging
import pickle
import copy
import time

from botocore import UNSIGNED
from botocore.client import Config
from botocore.exceptions import ClientError


def import_logfile(auth, logfile, args):
    # see if the schema is present. If not, send it with the wipe command
    db = dbfile.DBMySQL(auth)
    cursor = db.cursor()
    cursor.execute("SELECT count(*) from downloads")
    with open(logfile) as f:
        for line in f:
            obj = weblog.weblog.Weblog(line)
            weblog.schema.send_weblog(cursor, obj)


BUFSIZE=65536
def import_s3obj(obj):
    """
    Typical obj:
    {'Key': 'corpora/files/2009-audio/media1/media1_27_192kbps_44100Hz_Stereo_art.mp3', 'LastModified': datetime.datetime(2020, 11, 21, 23, 7, 31, tzinfo=tzlocal()), 'ETag': '"3045e3c6a79e791bbacd97a06c27f969"', 'Size': 384429, 'StorageClass': 'INTELLIGENT_TIERING', 'Bucket': 'digitalcorpora'}
    :param auth: authentication object.
    :param obj: dictionary with s3 object information.
    """

    auth   = obj['auth']
    s3key  = obj['Key']
    # Make sure that this object is in the database.

    cmd  = "insert into downloadable (s3key,bytes,mtime,etag) values (%s,%s,%s,%s)"
    vals = (s3key, obj['Size'], obj['LastModified'], obj['ETag'])
    try:
        dbfile.DBMySQL.csfr(auth, cmd, vals)
    except pymysql.err.IntegrityError as e:
        if e.args[0]==1062:
            # It already exists. If the ETag hasn't changed and we have both sha2_256 and sha3_256, just return
            rows = dbfile.DBMySQL.csfr(auth, "SELECT ETag from downloadable where s3key=%s and (sha2_256 is not null) and (sha3_256 is not null)", (s3key,))
            if len(rows)==1 and rows[0][0]==obj['ETag']:
                logging.info('ETag matches; will not update %s', s3key)
                return None
        else:
            raise(e)

    # Get a handle to the s3 file
    s3client  = boto3.client('s3', config=Config(signature_version=UNSIGNED))
    o2   = s3client.get_object(Bucket=obj['Bucket'], Key=obj['Key'])

    """
    Typical o2:
    {'ResponseMetadata': {'RequestId': 'EF6D913C1C48EEF1', 'HostId': 'CB6TRV/KlxtzU4FbXiYQKb6+PPYztCzvdI1FcXAeAoNeXkiGhm+BwBrrIUqbNyGPy3XsqsKENOU=', 'HTTPStatusCode': 200, 'HTTPHeaders': {'x-amz-id-2': 'CB6TRV/KlxtzU4FbXiYQKb6+PPYztCzvdI1FcXAeAoNeXkiGhm+BwBrrIUqbNyGPy3XsqsKENOU=', 'x-amz-request-id': 'EF6D913C1C48EEF1', 'date': 'Tue, 16 Feb 2021 01:32:14 GMT', 'last-modified': 'Sat, 21 Nov 2020 23:07:31 GMT', 'etag': '"3045e3c6a79e791bbacd97a06c27f969"', 'x-amz-storage-class': 'INTELLIGENT_TIERING', 'x-amz-version-id': 'kNdAWbQHuj0p_HxvobEGvcjuZKWox7Ct', 'accept-ranges': 'bytes', 'content-type': 'audio/mpeg', 'content-length': '384429', 'server': 'AmazonS3'}, 'RetryAttempts': 0}, 'AcceptRanges': 'bytes', 'LastModified': datetime.datetime(2020, 11, 21, 23, 7, 31, tzinfo=tzutc()), 'ContentLength': 384429, 'ETag': '"3045e3c6a79e791bbacd97a06c27f969"', 'VersionId': 'kNdAWbQHuj0p_HxvobEGvcjuZKWox7Ct', 'ContentType': 'audio/mpeg', 'Metadata': {}, 'StorageClass': 'INTELLIGENT_TIERING', 'Body': <botocore.response.StreamingBody object at 0x7f0d5f98ca10>}
    """
    t0 = time.time()
    body         = o2['Body']
    bytes_hashed = 0
    sha2_256 = hashlib.sha256()
    sha3_256 = hashlib.sha3_256()
    while True:
        data = body.read(BUFSIZE)
        if len(data)==0:
            break
        sha2_256.update(data)
        sha3_256.update(data)
        bytes_hashed += len(data)
    assert bytes_hashed == o2['ContentLength']
    t1 = time.time()

    # Update the database. Remember, every column except the key may have changed.
    cmd = "update downloadable set ETag=%s, mtime=%s, bytes=%s, sha2_256=%s, sha3_256=%s where s3key=%s"
    vals = (o2['ETag'], o2['LastModified'], bytes_hashed, sha2_256.hexdigest(), sha3_256.hexdigest(), s3key)
    dbfile.DBMySQL.csfr(auth, cmd, vals)
    logging.info('updated %s.  %d bytes, %6.2f seconds.  (%d bytes/sec)', s3key, bytes_hashed, (t1 -t0), bytes_hashed /(t1 -t0))
    return s3key

def import_s3prefix(auth, s3prefix, threads=40):
    """Because we can enumerate all of digitalcorpora in 3 seconds, we do that here. We then request hashing using python's multiprocessing module"""
    p = urllib.parse.urlparse(s3prefix)

    # First, get all of the keys and etags from the database that match this prefix
    # (Because of MD5 collisions, we check both etag and mtime)
    # We need to use our own auth because we don't want it activated
    auth2 = copy.deepcopy(auth)
    rows = dbfile.DBMySQL.csfr(auth2, "select s3key,etag,mtime from downloadable where s3key like %s and (sha2_256 is not null) and (sha3_256 is not null) ", (p.path[1:] +"%"))
    logging.info("found %d entries in database with hashes", len(rows))
    hashed = {row[0]: {'ETag': row[1], 'mtime': row[2]} for row in rows}

    # Now get directory information for all of the S3 objects on the website. See if the etag has changed
    s3client  = boto3.client('s3', config=Config(signature_version=UNSIGNED))
    paginator = s3client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=p.netloc, Prefix=p.path[1:])
    objs = []
    already_hashed = 0
    for page in pages:
        for obj in page.get('Contents'):
            s3key = obj['Key']
            try:
                t1 = obj['LastModified'].replace(tzinfo=None)
                t2 = hashed[s3key]['mtime']
                # for now ignore t1==t2 because our time was wrong.
                # if obj['ETag']==hashed[s3key]['ETag'] and t1==t2:
                if obj['ETag']==hashed[s3key]['ETag']:
                    logging.debug('Already hashed in database: %s', obj['Key'])
                    already_hashed +=1
                    if t1!=t2:
                        logging.info("set mtime in database for %s from %s to %s for etag %s", obj['Key'], t2, t1, obj['ETag'])
                        dbfile.DBMySQL.csfr(auth2, "update downloadable set mtime=%s where s3key=%s and etag=%s", (t1, obj['Key'], obj['ETag']))
                    continue
            except KeyError as e:
                pass

            obj['auth']   = auth
            obj['Bucket'] = p.netloc
            objs.append(obj)

    logging.info("Objects to hash: %d  (already hashed: %d)", len(objs), already_hashed)
    if threads==1:
        for obj in objs:
            import_s3obj(obj)
    else:
        with multiprocessing.Pool(threads) as p:
            p.map(import_s3obj, objs)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Import the Digital Corpora logs.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--wipe", help="Wipe database and load a new schema", action='store_true')
    parser.add_argument("--prod", help="Use production database", action='store_true')
    parser.add_argument("--logfile", help="Log file to import")
    parser.add_argument("--debug", action='store_true')
    parser.add_argument("--s3prefix", help="Scan an S3 prefix")
    parser.add_argument("--threads", "-j", type=int, default=1)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--aws", help="Get database password from aws secrets system", action='store_true')
    g.add_argument("--env", help="Get database password from environment variables", action='store_true')
    clogging.add_argument(parser)
    args = parser.parse_args()
    clogging.setup(args.loglevel)

    if args.aws:
        s = aws_secrets.get_secret()
        database = "dcstats_test" if not args.prod else 'dcstats'
        auth = dbfile.DBMySQLAuth(host=s['host'],
                                  database=database,
                                  user=s['username'],
                                  password=s['password'],
                                  debug=args.debug)

    elif args.env:
        database = "dcstats_test" if not args.prod else 'dcstats'
        auth = dbfile.DBMySQLAuth(host=os.environ['DBWRITER_HOSTNAME'],
                                  database=database,
                                  user=os.environ['DBWRITER_USERNAME'],
                                  password=os.environ['DBWRITER_PASSWORD'])

    if args.debug:
        print("auth:", auth)

    if args.wipe:
        db = dbfile.DBMySQL(auth)
        db.create_schema(open("schema.sql", "r").read())

    if args.logfile:
        import_logfile(auth, args.logfile, args)

    if args.s3prefix:
        import_s3prefix(auth, args.s3prefix, threads=args.threads)
