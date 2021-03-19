#!/usr/bin/env python3
"""
digitalcorpora log tool.

"""

import os
import urllib.parse
import hashlib
import multiprocessing
import logging
import copy
import time
import datetime
import codecs
import queue
import threading
import signal
import json

import boto3
import pymysql

from botocore import UNSIGNED
from botocore.client import Config
#from botocore.exceptions import ClientError

import weblog.schema
import weblog.weblog

import aws_secrets
import ctools.dbfile as dbfile
import ctools.clogging as clogging

year = datetime.datetime.now().year

S3_LOG_BUCKET = 'digitalcorpora-logs'
S3_LOGFILE_PATH = os.path.join( os.getenv("HOME"), "s3logs", f"s3logs.{year}.log")

def import_apache_logfile(auth, logfile):
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

    cmd  = "INSERT INTO downloadable (s3key,bytes,mtime,etag) VALUES (%s,%s,%s,%s)"
    vals = (s3key, obj['Size'], obj['LastModified'], obj['ETag'])
    try:
        dbfile.DBMySQL.csfr(auth, cmd, vals)
    except pymysql.err.IntegrityError as e:
        if e.args[0]==1062:
            # It already exists. If the ETag hasn't changed and we have both sha2_256 and sha3_256, just return
            rows = dbfile.DBMySQL.csfr(auth, "SELECT ETag FROM downloadable WHERE s3key=%s AND (sha2_256 IS NOT NULL) AND (sha3_256 IS NOT NULL)", (s3key,))
            if len(rows)==1 and rows[0][0]==obj['ETag']:
                logging.info('ETag matches; will not update %s', s3key)
                return None
        else:
            raise e

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

def hash_s3prefix(auth, s3prefix, threads=40):
    """Because we can enumerate all of digitalcorpora in 3 seconds, we do that here. We then request hashing using python's multiprocessing module"""
    p = urllib.parse.urlparse(s3prefix)

    # First, get all of the keys and etags from the database that match this prefix
    # (Because of MD5 collisions, we check both etag and mtime)
    # We need to use our own auth because we don't want it activated
    auth2 = copy.deepcopy(auth)
    rows = dbfile.DBMySQL.csfr(auth2,
                               """select s3key,etag,mtime from downloadable
                               WHERE s3key LIKE %s AND (sha2_256 IS NOT NULL) AND (sha3_256 IS NOT NULL)
                               """, (p.path[1:] +"%"))
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
                        logging.info("set mtime in database for %s from %s to %s for etag %s",
                                     obj['Key'], t2, t1, obj['ETag'])
                        dbfile.DBMySQL.csfr(auth2,
                                            "UPDATE downloadable SET mtime=%s WHERE s3key=%s AND etag=%s",
                                            (t1, obj['Key'], obj['ETag']))
                    continue
            # pylint: disable=W0612
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

def add_download(auth, obj):
    """ First make sure that it's in downloads and get its ID.
    Note that the downloads are tracked by key, even though the object identified by the key may change.
    """
    logging.info("obj: %s",obj)
    try:
        dbfile.DBMySQL.csfr(auth,
                            """INSERT INTO downloadable (s3key, bytes) VALUES (%s,%s) """,
                            (obj.key, obj.object_size), nolog=[1062])
    except pymysql.err.IntegrityError as e:
        if e.args[0]==1062:
            # It already exists.
            pass
        else:
            raise RuntimeError(e)
    # Now add the download
    r = dbfile.DBMySQL.csfr(auth,
                        """
                        INSERT INTO downloads (did, ipaddr, dtime)
                        VALUES ((select id from downloadable where s3key=%s),%s,%s)
                        """,
                        (obj.key, obj.remote_ip, obj.time))
    logging.info("object added r=%s key=%s remote_ip=%s time=%s",r,obj.key,obj.remote_ip,obj.time)


seen_dates = set()
WRITE_OBJECTS = set([ 'REST.PUT.PART',
                      'REST.PUT.OBJECT',
                      'REST.POST.OBJECT',
                      'REST.POST.UPLOAD',
                      'REST.POST.UPLOADS',
                     ])

DEL_OBJECTS = set(['REST.DELETE.OBJECT',
                   'REST.DELETE.UPLOAD' ])
GET_OBJECTS = set([ 'REST.GET.OBJECT',
                    'WEBSITE.GET.OBJECT' ])
MISC_OBJECTS = set([ 'REST.GET.ACCELERATE',
                     'REST.GET.ACL',
                     'REST.GET.BUCKET',
                     'REST.COPY.OBJECT',
                     'REST.COPY.OBJECT_GET',
                     'REST.GET.BUCKETPOLICY',
                     'REST.GET.BUCKETVERSIONS',
                     'REST.GET.CORS',
                     'REST.GET.ENCRYPTION',
                     'REST.GET.INTELLIGENT_TIERING',
                     'REST.GET.INVENTORY',
                     'REST.GET.LIFECYCLE',
                     'REST.GET.LOCATION',
                     'REST.GET.LOGGING_STATUS',
                     'REST.GET.NOTIFICATION',
                     'REST.GET.OBJECT_LOCK_CONFIGURATION',
                     'REST.GET.OWNERSHIP_CONTROLS',
                     'REST.GET.POLICY_STATUS',
                     'REST.GET.PUBLIC_ACCESS_BLOCK',
                     'REST.GET.REPLICATION',
                     'REST.GET.REQUEST_PAYMENT',
                     'REST.GET.TAGGING',
                     'REST.GET.VERSIONING',
                     'REST.GET.WEBSITE',
                     'REST.GET.ANALYTICS',
                     'S3.TRANSITION_INT.OBJECT',
                     'REST.HEAD.OBJECT',
                     'WEBSITE.HEAD.OBJECT',
                     'REST.HEAD.BUCKET',
                     'REST.PUT.BUCKETPOLICY',
                     'REST.PUT.LOGGING_STATUS',
                     'REST.PUT.METRICS',
                     'REST.PUT.NOTIFICATION',
                     'REST.PUT.VERSIONING',
                     'REST.PUT.WEBSITE',
                     'REST.OPTIONS.PREFLIGHT' ])
def obj_ingest(auth, obj):
    if obj.time.date() not in seen_dates:
        logging.info("%s",obj.time.date())
        seen_dates.add(obj.time.date())
    if obj.operation in GET_OBJECTS:
        if obj.http_status in [200,206]:
            add_download(auth, obj)
        else:
            logging.warning("will not ingest: %s",obj)
    elif obj.operation in WRITE_OBJECTS:
        logging.warning("upload: %s",obj.key)
    elif obj.operation in DEL_OBJECTS:
        logging.warning("del: %s",obj.key)
    elif obj.operation in MISC_OBJECTS:
        pass
    else:
        raise ValueError(f"Unknown operation {obj.operation} in {obj}")

def s3_logfile_ingest(auth, f):
    for (ct,line) in enumerate(f):
        if ct%1000==0:
            logging.info("%s added...",ct)
        obj = weblog.weblog.S3Log(line)
        obj_ingest(auth, obj)

s3_logfile = open(S3_LOGFILE_PATH,"a")
def s3_log_ingest(auth, key):
    """Given an s3 key, ingest each of its records, and them to the databse, and then delete it.
    :param auth: authentication token to write to the database
    :param key: key of the logfile
    """
    logging.info("%s",key)
    s3client  = boto3.client('s3')
    o2   = s3client.get_object(Bucket=S3_LOG_BUCKET, Key=key)
    line_stream = codecs.getreader("utf-8")
    for line in line_stream(o2['Body']):
        obj = weblog.weblog.S3Log(line)
        obj_ingest(auth, obj)
        s3_logfile.write(line)
    s3client.delete_object(Bucket=S3_LOG_BUCKET, Key=key)
    s3_logfile.flush()


def s3_logs_download(auth, threads=1):
    """Download an S3 logs and ingest them.
    :param auth: authentication token to write to the database.
    :param threads: number of threads to use
    """
    q  = queue.Queue()           # forward channel
    bc = queue.Queue()          # backchannel

    def worker():
        auth2 = copy.deepcopy(auth) # thread local auth
        while True:
            key = q.get()
            try:
                s3_log_ingest(auth2, key)
            except ValueError as e:
                logging.error("%s",e)
                bc.put('DIE')
            q.task_done()


    # Terminate on control-c, but after this object is processed.
    terminate = False
    def handler(signum, frame):
        bc.put('DIE')
    signal.signal(signal.SIGINT, handler)

    # Start the threads
    for i in range(args.threads):
        threading.Thread(target=worker, daemon=True).start()
    s3client  = boto3.client('s3')
    paginator = s3client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=S3_LOG_BUCKET, Prefix='')
    for page in pages:
        # print("page=",json.dumps(page,indent=4))
        if 'Contents' not in page:
            continue
        for obj in page.get('Contents'):
            q.put(obj['Key'])
            try:
                back = bc.get(block=False)
            except queue.Empty:
                pass
            else:
                logging.info("Data received on backchannel: %s",back)
                if back=='DIE':
                    raise RuntimeError("time to die")
    if terminate:
        logging.info("Clean termination. Clearing work queue.")
        q.clear()


    # Block until all tasks are done
    # Don't bother killing the workers.
    q.join()

class Object:
    pass

def db_copy( auth ):
    """Copy the downloads from the dev database to the production database.
    This was created because I accidentally committed to the production database.
    There are 17,000 transactions and this ran in less than a minute.
    """
    db = dbfile.DBMySQL(auth)
    c = db.cursor()
    c.execute("SELECT b.s3key,b.bytes, a.ipaddr,a.dtime FROM dcstats_test.downloads a RIGHT JOIN downloadable b ON a.did=b.id where (a.ipaddr is not null) and (a.dtime is not null) ")
    count = 0
    for (s3key,bytes,ipaddr,dtime) in c.fetchall():
        count += 1
        if count%100==0:
            print(count)
        d = db.cursor()
        d.execute("SELECT id from dcstats.downloads where did = (select id from downloadable where s3key=%s) and ipaddr=%s and dtime=%s",
                  (s3key,ipaddr,dtime))
        m = d.fetchall()
        if len(m)==0:
            obj = Object()
            obj.key = s3key
            obj.object_size = bytes
            obj.remote_ip = ipaddr
            obj.time = dtime
            add_download( auth, obj)
            print("Added",s3key,ipaddr,dtime)
    print("total:",count)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Import the Digital Corpora logs.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--wipe", help="Wipe database and load a new schema", action='store_true')
    parser.add_argument("--debug", action='store_true')
    parser.add_argument("--verbose", action='store_true')
    parser.add_argument("--threads", "-j", type=int, default=1)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--apache_logfile", help="Apache combined log file to import (currently not working)")
    g.add_argument("--hash_s3prefix", help="Hash all of the new objects under a given S3 prefix")
    g.add_argument("--s3_download_ingest", action='store_true',
                        help='download S3 logs to local directory, combine into local logfile, and ingest')
    g.add_argument("--s3_logfile_ingest",
                        help='ingest an already downloaded s3 logfile')
    g.add_argument("--copy", action='store_true',
                   help='Copy downloads from test to prod that are not present in prod')
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--aws", help="Get database password from aws secrets system", action='store_true')
    g.add_argument("--env", help="Get database password from environment variables", action='store_true')
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--prod", help="Use production database", action='store_true')
    g.add_argument("--test", help="Use test database", action='store_true')

    clogging.add_argument(parser)
    args = parser.parse_args()
    clogging.setup(args.loglevel)

    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    if args.copy and args.test:
        logging.error("--copy requires --prod")
        exit(1)

    database = "dcstats_test" if not args.prod else 'dcstats'
    if args.aws:
        s = aws_secrets.get_secret()
        auth = dbfile.DBMySQLAuth(host=s['host'],
                                  database=database,
                                  user=s['username'],
                                  password=s['password'],
                                  debug=args.debug)

    elif args.env:
        auth = dbfile.DBMySQLAuth(host=os.environ['DBWRITER_HOSTNAME'],
                                  database=database,
                                  user=os.environ['DBWRITER_USERNAME'],
                                  password=os.environ['DBWRITER_PASSWORD'],
                                  debug=args.debug
                                  )

    if auth.debug:
        print("auth:", auth)

    if args.wipe:
        really = input("really wipe? [y/n]")
        if really[0]!='y':
            print("Will not wipe")
            exit(1)
        db = dbfile.DBMySQL(auth)
        db.create_schema(open("schema.sql", "r").read())

    if args.apache_logfile:
        import_apache_logfile(auth, args.apache_logfile)
    elif args.hash_s3prefix:
        hash_s3prefix(auth, args.hash_s3prefix, threads=args.threads)
    elif args.s3_download_ingest:
        s3_logs_download(auth, args.threads)
    elif args.s3_logfile_ingest:
        s3_logfile_ingest( auth, open(args.s3_logfile_ingest))
    elif args.copy:
        db_copy( auth )
    else:
        raise RuntimeError("Unknown action")
