#!/usr/bin/env python3
"""
digitalcorpora log tool.

"""

import os
import pymysql
import weblog.schema
import weblog.weblog
import aws_secrets
import ctools.dbfile
import urllib.parse
import boto3
import hashlib
import multiprocessing

from botocore import UNSIGNED
from botocore.client import Config
from botocore.exceptions import ClientError


def import_logfile(auth, logfile, args):
    # see if the schema is present. If not, send it with the wipe command
    db = ctools.dbfile.DBMySQL(auth)
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
    vals = (s3key, obj['Size'], obj['LastModified'],obj['ETag'])
    try:
        ctools.dbfile.DBMySQL.csfr(auth, cmd, vals)
    except pymysql.err.IntegrityError as e:
        if e.args[0]==1062:
            # It already exists. If the ETag hasn't changed, just return
            rows = ctools.dbfile.DBMySQL.csfr(auth, "SELECT ETag from downloadable where s3key=%s", (s3key,))
            if len(rows)==1 and rows[0][0]==obj['ETag']:
                if obj['verbose']:
                    print('no update',s3key)
                return None
        else:
            raise(e)

    # Get a handle to the s3 file
    s3client  = boto3.client('s3', config=Config(signature_version=UNSIGNED))
    o2   = s3client.get_object(Bucket=obj['Bucket'],Key=obj['Key'])

    """
    Typical o2:
    {'ResponseMetadata': {'RequestId': 'EF6D913C1C48EEF1', 'HostId': 'CB6TRV/KlxtzU4FbXiYQKb6+PPYztCzvdI1FcXAeAoNeXkiGhm+BwBrrIUqbNyGPy3XsqsKENOU=', 'HTTPStatusCode': 200, 'HTTPHeaders': {'x-amz-id-2': 'CB6TRV/KlxtzU4FbXiYQKb6+PPYztCzvdI1FcXAeAoNeXkiGhm+BwBrrIUqbNyGPy3XsqsKENOU=', 'x-amz-request-id': 'EF6D913C1C48EEF1', 'date': 'Tue, 16 Feb 2021 01:32:14 GMT', 'last-modified': 'Sat, 21 Nov 2020 23:07:31 GMT', 'etag': '"3045e3c6a79e791bbacd97a06c27f969"', 'x-amz-storage-class': 'INTELLIGENT_TIERING', 'x-amz-version-id': 'kNdAWbQHuj0p_HxvobEGvcjuZKWox7Ct', 'accept-ranges': 'bytes', 'content-type': 'audio/mpeg', 'content-length': '384429', 'server': 'AmazonS3'}, 'RetryAttempts': 0}, 'AcceptRanges': 'bytes', 'LastModified': datetime.datetime(2020, 11, 21, 23, 7, 31, tzinfo=tzutc()), 'ContentLength': 384429, 'ETag': '"3045e3c6a79e791bbacd97a06c27f969"', 'VersionId': 'kNdAWbQHuj0p_HxvobEGvcjuZKWox7Ct', 'ContentType': 'audio/mpeg', 'Metadata': {}, 'StorageClass': 'INTELLIGENT_TIERING', 'Body': <botocore.response.StreamingBody object at 0x7f0d5f98ca10>}
    """
    body         = o2['Body']
    bytes_hashed = 0
    sha2_256 = hashlib.sha256()
    sha3_256 = hashlib.sha3_256()
    while True:
        data = body.read(BUFSIZE)
        if len(data)==0:
            break;
        sha2_256.update(data)
        sha3_256.update(data)
        bytes_hashed += len(data)
    assert bytes_hashed == o2['ContentLength']

    # Update the database. Remember, every column except the key may have changed.
    cmd = "update downloadable set ETag=%s, mtime=%s, bytes=%s, sha2_256=%s, sha3_256=%s where s3key=%s"
    vals = (o2['ETag'], o2['LastModified'], bytes_hashed, sha2_256.hexdigest(), sha3_256.hexdigest(), s3key)
    ctools.dbfile.DBMySQL.csfr(auth, cmd, vals)
    if obj['verbose']:
        print('updated',s3key)
    return s3key

def import_s3prefix(auth, s3prefix, threads=40, verbose=False):
    """Because we can enumerate all of digitalcorpora in 3 seconds, we do that here. We then request hashing using python's multiprocessing module"""
    p = urllib.parse.urlparse(s3prefix)

    s3client  = boto3.client('s3', config=Config(signature_version=UNSIGNED))
    paginator = s3client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=p.netloc, Prefix=p.path[1:])
    objs = []
    for page in pages:
        for obj in page.get('Contents'):
            obj['auth']   = auth
            obj['Bucket'] = p.netloc
            obj['verbose'] = verbose
            if threads==1:
                import_s3obj(obj)
            else:
                objs.append(obj)

    if threads>1:
        with multiprocessing.Pool(threads) as p:
            results = p.map(import_s3obj, objs)

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
    parser.add_argument("--verbose", action='store_true')
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--aws", help="Get database password from aws secrets system", action='store_true')
    g.add_argument("--env", help="Get database password from environment variables", action='store_true')
    args = parser.parse_args()


    if args.aws:
        s = aws_secrets.get_secret()
        database = "dcstats_test" if not args.prod else 'dcstats'
        auth = ctools.dbfile.DBMySQLAuth(host=s['host'],
                                         database=database,
                                         user=s['username'],
                                         password=s['password'],
                                         debug=args.debug)

    elif args.env:
        database = "dcstats_test" if not args.prod else 'dcstats'
        auth = ctools.dbfile.DBMySQLAuth(host=os.environ['DBWRITER_HOSTNAME'],
                                             database=database,
                                             user=os.environ['DBWRITER_USERNAME'],
                                             password=os.environ['DBWRITER_PASSWORD'],
                                             debug=args.debug)

    if args.wipe:
        wipe(auth)

    if args.debug:
        print("auth:",auth)

    if args.wipe:
        db = ctools.dbfile.DBMySQL(auth)
        db.create_schema(open("schema.sql","r").read())

    if args.logfile:
        import_logfile(auth, args.logfile, args)

    if args.s3prefix:
        import_s3prefix(auth, args.s3prefix, threads=args.threads)
