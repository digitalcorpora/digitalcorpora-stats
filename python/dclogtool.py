#!/usr/bin/env python3
"""
digitalcorpora log, hashing, and maintenance tool.
Performs any activity requiring write access to the database.


"""

import codecs
import copy
import datetime
import hashlib
import logging
import multiprocessing
import os
import queue
import sys
import threading
import time
import urllib.parse
import gzip
from collections import defaultdict

import boto3
import pymysql

from botocore import UNSIGNED
from botocore.client import Config

import weblog.schema
import weblog.weblog

import aws_secrets
# import ctools.dbfile as dbfile
# import ctools.clogging as clogging
from ctools import dbfile
from ctools import clogging
import ctools.lock

year = datetime.datetime.now().year

S3_DATA_BUCKET = 'digitalcorpora'
S3_LOG_BUCKET = 'digitalcorpora-logs'

# The logfile for this year
S3_LOGFILE_PATH = os.path.join( os.getenv("HOME"), "s3logs", f"s3logs.{year}.log")
DEFAULT_TIMEOUT = 30
WRITE_OBJECTS = set([ 'REST.PUT.PART',
                      'REST.PUT.OBJECT',
                      'REST.POST.OBJECT',
                      'REST.POST.UPLOAD',
                      'REST.POST.UPLOADS',
                     ])

DEL_OBJECTS = set(['REST.DELETE.OBJECT',
                   'REST.DELETE.UPLOAD',
                   'S3.EXPIRE.OBJECT',
                   ])


GET_OBJECTS = set([ 'REST.GET.OBJECT',
                    'REST.COPY.PART_GET',
                    'WEBSITE.GET.OBJECT' ])

MISC_OBJECTS = set([
    'REST.COPY.OBJECT',
    'REST.COPY.OBJECT_GET',
    'REST.GET.ACCELERATE',
    'REST.GET.ACL',
    'REST.GET.ANALYTICS',
    'REST.GET.BUCKET',
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
    'REST.GET.OBJECT_TAGGING',
    'REST.GET.OWNERSHIP_CONTROLS',
    'REST.GET.POLICY_STATUS',
    'REST.GET.PUBLIC_ACCESS_BLOCK',
    'REST.GET.REPLICATION',
    'REST.GET.REQUEST_PAYMENT',
    'REST.GET.TAGGING',
    'REST.GET.UPLOAD',
    'REST.GET.UPLOADS',
    'REST.GET.VERSIONING',
    'REST.GET.WEBSITE',
    'REST.HEAD.BUCKET',
    'REST.HEAD.OBJECT',
    'REST.OPTIONS.PREFLIGHT',
    'REST.POST.BUCKET',
    'REST.PUT.BUCKETPOLICY',
    'REST.PUT.LOGGING_STATUS',
    'REST.PUT.METRICS',
    'REST.PUT.NOTIFICATION',
    'REST.PUT.VERSIONING',
    'REST.PUT.WEBSITE',
    'S3.TRANSITION_INT.OBJECT',
    'WEBSITE.HEAD.OBJECT',
    'WEBSITE.INVALIDOPERATION',
])

DOWNLOAD = 'DOWNLOAD'
UPLOAD   = 'UPLOAD'
BAD      = 'BAD'
DELETED  = 'DELETED'
MISC     = 'MISC'
BLOCKED  = 'BLOCKED'
UNKNOWN  = 'UNKNOWN'

def import_apache_logfile(auth, logfile):
    # see if the schema is present. If not, send it with the wipe command
    db = dbfile.DBMySQL(auth)
    cursor = db.cursor()
    cursor.execute("SELECT count(*) from downloads")
    with open(logfile) as f:
        for line in f:
            line = line.strip()
            if line:
                obj = weblog.weblog.Weblog(line)
                weblog.schema.send_weblog(cursor, obj)

BUFSIZE=65536
def import_s3obj(obj):
    """
    This imports an S3 Object into the database, hashing it if necessary.
    It does not import S3 download logs. Those are in a different format and are imported by add_download().

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

def s3_get_objects(prefix='', limit=sys.maxsize):
    s3client  = boto3.client('s3')
    paginator = s3client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=S3_LOG_BUCKET, Prefix='')
    count = 0
    for page in pages:
        if limit > 0:
            logging.debug("count=%d limit=%d",count,limit)
        if count > limit:
            break
        if 'Contents' not in page:
            continue
        for obj in page.get('Contents'):
            count+=1
            if count > limit:
                break
            yield(obj)

def s3_logs_info(limit=sys.maxsize):
    earliest = None
    latest   = None
    count = 0
    for obj in s3_get_objects('', limit=limit):
        count += 1
        earliest = obj['LastModified'] if earliest is None else min(earliest,obj['LastModified'])
        latest   = obj['LastModified'] if latest is None else max(earliest,obj['LastModified'])
    print("Count:",count)
    print("Earliest:",earliest)
    print("Latest:",latest)

def hash_s3prefix(auth, s3prefix, threads=40):
    """Because we can enumerate all of digitalcorpora in 3 seconds, we do that here. We then request hashing using python's multiprocessing module"""
    p = urllib.parse.urlparse(s3prefix)

    # First, get all of the keys and etags from the database that match this prefix
    # (Because of MD5 collisions, we check both etag and mtime)
    # We need to use our own auth because we don't want it activated
    auth2 = copy.deepcopy(auth)
    lk = p.path[1:] +"%"
    rows = dbfile.DBMySQL.csfr(auth2,
                               """select s3key,etag,mtime from downloadable
                               WHERE s3key LIKE %s AND (sha2_256 IS NOT NULL) AND (sha3_256 IS NOT NULL)
                               """, (lk,))
    logging.info("found %d entries in database with hashes", len(rows))
    hashed = {row[0]: {'ETag': row[1], 'mtime': row[2]} for row in rows}

    # Now get directory information for all of the S3 objects on the website. See if the etag has changed
    s3client  = boto3.client('s3', config=Config(signature_version=UNSIGNED))
    paginator = s3client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=p.netloc, Prefix=p.path[1:])
    objs = []
    already_hashed = 0
    for page in pages:
        contents = page.get('Contents')
        if contents is None:
            logging.error("no objects with prefix %s", s3prefix)
            continue
        for obj in contents:
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

seen_dates = set()

ingested_s3key = set()
ingested_user_agent = set()
def insert_obj_into_db(auth, obj):
    """ First make sure that it's in downloads and get its ID.
    Note that the downloads are tracked by key, even though the object identified by the key may change.
    This is not very efficient, as it requires (on average) two aborted inserts due to duplicate keys and then an insert with two subselects per object.
    The aborted inserts get accelerated by the MySQL database because the files are indexed, but we can make this faster by only performing each insert once and tracking it in a set.
    We can't get away from the subselects due to threading issues.
    """
    if (obj.key,obj.object_size) not in ingested_s3key:
        dbfile.DBMySQL.csfr(auth,
                            """INSERT INTO downloadable (s3key, bytes) VALUES (%s,%s) """,
                            (obj.key, obj.object_size), ignore=[1062])
        ingested_s3key.add((obj.key, obj.object_size))

    # Make sure the browser is in the databse
    if obj.user_agent not in ingested_user_agent:
        dbfile.DBMySQL.csfr(auth,
                            """INSERT INTO user_agents (user_agent) VALUES (%s) """,
                            (obj.user_agent,), ignore=[1062])
        ingested_user_agent.add(obj.user_agent)


    # Now INSERT the file into the table
    dbfile.DBMySQL.csfr(auth,
                        """
                        INSERT INTO downloads (did, user_agent_id, remote_ipaddr, dtime, bytes_sent)
                        VALUES ((select id from downloadable where s3key=%s),
                                (select id from user_agents where user_agent=%s),
                               %s,%s,%s)
                        """,
                        (obj.key, obj.user_agent, obj.remote_ip, obj.dtime, obj.bytes_sent))


# pylint: disable=R0911
def validate_obj(auth, obj):
    """Write a logfile object to the database"""
    if obj.dtime.date() not in seen_dates:
        # Status report
        logging.info("Ingesting date=%s",obj.dtime.date())
        seen_dates.add(obj.dtime.date())
    if obj.operation in GET_OBJECTS:
        if obj.http_status in [200,206]:
            return DOWNLOAD
        elif obj.http_status in [400,404]:
            # bad URL
            return BAD
        elif obj.http_status in [416]:
            # Bad Range
            return BAD
        elif obj.http_status in [304]:
            # not modified
            return BAD
        elif obj.http_status in [301]:
            # moved permanently?
            return BAD
        elif obj.http_status in [304]:
            # not modified
            return BAD
        elif obj.http_status in [500]:
            # internal error
            return BAD
        else:
            # Log that we didn't ingest something, but throw it away
            logging.warning("will not ingest HTTP status %d: %s",obj.http_status, obj.line)
            return BAD
    elif obj.operation in WRITE_OBJECTS:
        if obj.http_status//100 in [4]:
            # Write objects blocked.
            return BLOCKED
        logging.warning("upload: %s %s %s from %s (status: %s)", obj.dtime, obj.operation, obj.key, obj.remote_ip, obj.http_status)
        return UPLOAD
    elif obj.operation in DEL_OBJECTS:
        logging.warning("del: %s %s %s",obj.dtime,obj.operation,obj.key)
        return DELETED
    elif obj.operation in MISC_OBJECTS:
        return MISC
    else:
        logging.error(f"Unknown operation {obj.operation} in {obj}")
        return UNKNOWN

def logfile_ingest(auth, f, factory):
    """Given a logfile, ingest it into the database.
    :param auth: database authentication token
    :param f: input file
    :param factory: function that parses a logfile recorded to a weblog object
    Because of the `factory` parameter, we can ingest either.
    """
    sums = defaultdict(int)
    earliest = None
    latest   = None
    for (ct,line) in enumerate(f):
        line = line.strip()
        if line=='':
            continue
        obj  = factory(line)
        what = validate_obj(auth, obj)
        if what==DOWNLOAD:
            insert_obj_into_db(auth, obj)
        sums[what] += 1
        earliest = obj.dtime if earliest is None else min(earliest,obj.dtime)
        latest = obj.dtime if latest is None else max(latest,obj.dtime)
        if (ct>0) and (ct % 10000)==0:
            logging.info("%s processed (last batch: %s to %s)...",ct,earliest,latest)
            earliest = None
            latest = None
    print("Ingest Status:")
    for (k,v) in sums.items():
        print(k,v)

def s3_log_ingest(s3_logfile, s3_logfile_lock, auth, key):
    """Given an s3 key, ingest each of its records (there can be many), and them to the databse, and then delete it.
    :param auth: authentication token to write to the database
    :param key: key of the logfile
    """
    config = Config(connect_timeout=5, retries={'max_attempts': 4})
    count = 0
    s3client  = boto3.client('s3', config=config)
    o2   = s3client.get_object(Bucket=S3_LOG_BUCKET, Key=key)
    line_stream = codecs.getreader("utf-8")
    for line in line_stream(o2['Body']):
        obj = weblog.weblog.S3Log(line)
        what = validate_obj(auth, obj)
        if what==DOWNLOAD:
            insert_obj_into_db(auth, obj)
            s3_logfile_lock.acquire()
            s3_logfile.write(line)
            s3_logfile_lock.release()
            count += 1

    # It turns out that deleting objects can take a really long time, so do it in another thread
    def delete_object_worker(key=key):
        s3client2  = boto3.client('s3')
        s3client2.delete_object(Bucket=S3_LOG_BUCKET, Key=key)
    threading.Thread(target=delete_object_worker, kwargs={"key":key}).start()
    s3_logfile_lock.acquire()
    s3_logfile.flush()
    s3_logfile_lock.release()
    return count


DIE_PARENT = "<<DIE PARENT>>"
DIE_THREAD = "<<DIE THREAD>>"     # hopefully no S3Key with this
def s3_logs_download_ingest_and_save(auth, threads=1, limit=sys.maxsize, timeout=DEFAULT_TIMEOUT):
    """Download an S3 logs and ingest them.
    Runs in the main thread.
    :param auth: authentication token to write to the database.
    :param threads: number of threads to use
    """
    count = 0
    q  = queue.Queue(maxsize = threads*2)          # forward channel
    bc = queue.Queue()          # backchannel

    s3_logfile      = open(S3_LOGFILE_PATH,"a")
    s3_logfile_lock = threading.Lock()
    def worker():
        """Runs in the worker thread"""
        nonlocal count
        # deepcopy assures that each thread has its own copy of the auth object.
        auth2 = copy.deepcopy(auth)
        while True:
            logging.debug("%d - Calling get...",threading.get_ident())
            key = q.get()
            logging.debug("%d - got %s",threading.get_ident(),key)
            if key==DIE_THREAD:
                q.task_done()
                return
            tally = s3_log_ingest(s3_logfile, s3_logfile_lock, auth2, key)
            count += tally
            q.task_done()
            time.sleep(0)

    # Start the threads
    for _ in range(threads):
        threading.Thread(target=worker, daemon=True).start()
    s3client  = boto3.client('s3')
    paginator = s3client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=S3_LOG_BUCKET, Prefix='')
    for page in pages:
        if count > limit:
            logging.debug("count=%d exceeds limit (%d)",count,limit)
            break
        if 'Contents' not in page:
            continue

        objs = page.get('Contents')
        for (ct,obj) in enumerate(objs,1):
            if count>limit:
                break
            q.put(obj['Key'],timeout=timeout)  # if we have blocked more than 30 seconds, something is wrong

            # Any news from the backchannel?
            # This allows exceptions in the worker thread to propigate to the parent.
            try:
                back = bc.get(block=False)
            except queue.Empty:
                pass
            else:
                logging.info("Data received on backchannel: %s",back)
                if back==DIE_PARENT:
                    raise RuntimeError("Received DIE_PARENT")
            time.sleep(0)

    # Block until all tasks are done
    # Don't bother killing the workers (why not?)
    logging.debug("done looping over pages")
    for _ in range(threads):
        q.put(DIE_THREAD)
    q.join()


def db_copy( auth ):
    """Copy the downloads from the dev database to the production database.
    This was created because I accidentally committed to the production database.
    There are 17,000 transactions and this ran in less than a minute.
    """
    db = dbfile.DBMySQL(auth)
    c = db.cursor()
    c.execute(
        """
        SELECT b.s3key,b.bytes, a.remote_ipaddr,a.dtime
        FROM dcstats_test.downloads a
        RIGHT JOIN downloadable b ON a.did=b.id where (a.remote_ipaddr is not null) and (a.dtime is not null)
        """)
    count = 0
    for (s3key,object_size,remote_ip,dtime) in c.fetchall():
        count += 1
        if count%100==0:
            print(count)
        d = db.cursor()
        d.execute("SELECT id from dcstats.downloads where did = (select id from downloadable where s3key=%s) and remote_ip=%s and dtime=%s",
                  (s3key,remote_ip,dtime))
        m = d.fetchall()
        if len(m)==0:
            obj = weblog.weblog.S3Log(None, {'key':s3key,
                                             'object_size': object_size,
                                             'remote_ip':remote_ip,
                                             'time':dtime})
            insert_obj_into_db( auth, obj)
            print("Added",s3key,remote_ip,dtime)
    print("total:",count)

def db_stats( auth ):
    db = dbfile.DBMySQL(auth)
    def show_query(message, query):
        c = db.cursor()
        c.execute(query)
        print(message % c.fetchall()[0])

    print("Stats on the database:")
    show_query("Downloadable objects in database: %s","select count(*) from downloadable")
    show_query("Downloads objects in database: %s from %s to %s ","select count(*), min(dtime), max(dtime) from downloads")

def logfile_opener(fname):
    if fname.endswith(".gz"):
        return gzip.open(fname,"rt", encoding='utf-8' )
    else:
        return open(fname, "rt")

def db_gc( auth, s3prefix ):
    db = dbfile.DBMySQL( auth )
    c = db.cursor()
    c.execute("SELECT s3key, id FROM downloadable")
    s3keys_in_db = {row[0]:row[1] for row in c.fetchall() }
    print("keys in database:",len(s3keys_in_db))

    # Now get the list of objects in S3
    p = urllib.parse.urlparse(s3prefix)
    s3client  = boto3.client('s3', config=Config(signature_version=UNSIGNED))
    paginator = s3client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=p.netloc, Prefix=p.path[1:])
    count = 0
    for page in pages:
        for obj in page.get('Contents'):
            s3key = obj['Key']
            if s3key not in s3keys_in_db:
                print("missing:",s3key)
            else:
                del s3keys_in_db[s3key]
            count += 1
    print("Objects in s3:",count)
    print("Objects no longer in S3:",len(s3keys_in_db))

    # Now, find all of downloadable IDs in the database that are also in the downloads table
    not_present = ",".join( (str(s) for s in sorted(s3keys_in_db.values()) ) )
    cmd = f"SELECT DISTINCT did FROM downloads WHERE did IN ({not_present})"
    c.execute( cmd )
    ids_that_were_downloaded = set([row[0] for row in c.fetchall()])
    print("Number of ids that were downloaded:",len(ids_that_were_downloaded))
    ids_not_downloaded = set(s3keys_in_db.values()).difference(ids_that_were_downloaded)
    print("Number of ids that were not downloaded:",len(ids_not_downloaded))
    print("Not downloaded and deletable:")

    s3keys_cant_delete = dict()
    to_delete = set()
    for (k,v) in sorted(s3keys_in_db.items()):
        if v in ids_not_downloaded:
            logging.info("delete from downloadable id %s path %s",v,k)
            to_delete.add(v)
            count += 1
        else:
            s3keys_cant_delete[k] = v
    print("Total not downloaded and deleted:",len(to_delete))
    cmd = "DELETE FROM downloadable where ID in (" + ",".join( (str(s) for s in sorted(to_delete)) ) + ")"
    c.execute(cmd)

    print("Downloaded at least once and therefore not deletable:",len(s3keys_cant_delete))
    print("Setting them present=0")
    not_present = ",".join( (str(s) for s in sorted(s3keys_cant_delete.values()) ) )
    cmd = f"UPDATE downloadable SET present=0 WHERE id IN ({not_present})"
    c.execute(cmd)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Import the Digital Corpora logs.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--wipe", help="Wipe database and load a new schema", action='store_true')
    parser.add_argument("--debug", action='store_true')
    parser.add_argument("--verbose", action='store_true')
    parser.add_argument("--threads", "-j", type=int, default=1)
    parser.add_argument("--limit", type=int, default=sys.maxsize, help="Limit number of imports to this number when reading from text files or s3 objects when reading from s3")

    # One of these options must be provided - tell me what to do
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--apache_logfile_ingest", help="Apache combined log file to import (currently not working)")
    g.add_argument("--hash_s3prefix",         help="Hash all of the new objects under a given S3 prefix")
    g.add_argument("--s3_logs_info", action='store_true',
                   help="Report information about the s3 logs that haven't been downloaded")
    g.add_argument("--s3_logs_download_ingest_and_save", action='store_true',
                        help='download S3 logs to local directory, combine into local logfile, and ingest')
    g.add_argument("--s3_logfile_ingest",  help='ingest an already downloaded s3 logfile')
    g.add_argument("--db_stats", help='provide information on database',action='store_true')
    g.add_argument("--copy", action='store_true',
                   help='Copy downloads from test to prod that are not present in prod')
    g.add_argument("--gc", action='store_true', help='Garbage collect the MySQL database')

    # Tell me how to authenticate ---
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--aws", help="Get database password from aws secrets system", action='store_true')
    g.add_argument("--env", help="Get database password from environment variables", action='store_true')

    # Tell me which database to use
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
        sys.exit(1)

    database = "dcstats_test" if not args.prod else 'dcstats'
    # Select the authentication approach
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

    # We won't want to do this ever
    if args.wipe:
        # pylint: disable=W0101
        raise RuntimeError("--wipe is disabled")
        really = input("really wipe? [y/n]")
        if really[0]!='y':
            print("Will not wipe")
            sys.exit(1)
        db = dbfile.DBMySQL(auth)
        db.create_schema(open("schema.sql", "r").read())

    # Don't allow another copy to run the script
    ctools.lock.lock_script()

    # Do what we are supposed to do
    if args.apache_logfile_ingest:
        with logfile_opener(args.apache_logfile_ingest) as f:
            logfile_ingest(auth, f, weblog.weblog.Weblog)
    elif args.s3_logfile_ingest:
        with logfile_opener(args.s3_logfile_ingest) as f:
            logfile_ingest( auth, f, weblog.weblog.S3Log)
    elif args.hash_s3prefix:
        hash_s3prefix(auth, args.hash_s3prefix, threads=args.threads)
    elif args.s3_logs_download_ingest_and_save:
        s3_logs_download_ingest_and_save(auth, args.threads, args.limit)
    elif args.s3_logs_info:
        s3_logs_info(args.limit)
    elif args.copy:
        db_copy( auth )
    elif args.gc:
        db_gc( auth, "s3://" + D3_DATA_BUCKET)
    elif args.db_stats:
        db_stats( auth )
    else:
        raise RuntimeError("Unknown action")
