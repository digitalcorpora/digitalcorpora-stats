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
import signal
import threading
import queue
from collections import defaultdict

import boto3
import botocore
import botocore.exceptions
import pymysql

from botocore import UNSIGNED
from botocore.client import Config
import botocore.exceptions

import weblog.schema
import weblog.weblog

from weblog.weblog import S3LogException

import aws_secrets

from dcstats_vendor import database as dbsupport
from dcstats_vendor import logging_support
from dcstats_vendor import locking

MULTIPROCESSING = False
DELETE_IN_BACKGROUND = False
DEFAULT_THREADS = 20   # Good for a microvm
NOTIFICATION_SIZE = 100_000_000
PROGRESS_INTERVAL_SECONDS = 30
SUMMARY_DELETE_BATCH_SIZE = 100_000
SUMMARY_STATE_TABLE = "download_summarize_state"
INGEST_TRANSACTION_RETRIES = 5
MYSQL_RETRYABLE_ERROR_CODES = {1205, 1213}

stats = defaultdict(int)
STAT_S3_OBJECTS = 'S3_OBJECTS'
STAT_S3_RECORDS = 'S3_RECORDS'
STAT_S3_DOWNLOAD_RECORDS = 'S3_DOWNLOAD_RECORDS'
STAT_S3_DOWNLOADS = 'S3_DOWNLOADS'
STAT_S3_EARLIEST = 'S3_EARLIEST'
STAT_S3_LATEST = 'S3_LATEST'


class ProgressReporter:
    """Emit bounded ingestion progress from concurrent workers."""

    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        with self.lock:
            self.started = time.monotonic()
            self.last_report = self.started
            self.source_records = 0
            self.downloads = 0
            self.bytes_sent = 0

    def committed(self, source_records, downloads, bytes_sent):
        """Record work only after its database transaction commits."""
        with self.lock:
            self.source_records += source_records
            self.downloads += downloads
            self.bytes_sent += bytes_sent
            now = time.monotonic()
            if now - self.last_report < PROGRESS_INTERVAL_SECONDS:
                return
            elapsed = now - self.started
            logging.info(
                "progress: %.0fs; %s log records (%.1f/s); %s downloads; %.2f GiB sent (%.2f MiB/s)",
                elapsed, self.source_records, self.source_records / elapsed,
                self.downloads, self.bytes_sent / (1024 ** 3),
                self.bytes_sent / elapsed / (1024 ** 2))
            self.last_report = now


progress_reporter = ProgressReporter()

S3_DATA_BUCKET = 'digitalcorpora'
S3_LOG_BUCKET = 'digitalcorpora-logs'

# The logfile for this year
S3_LOGFILE_PATH = os.path.join( os.getenv("HOME"), "s3logs", f"s3logs.{datetime.datetime.now().year}.log")
DEFAULT_TIMEOUT = 30
# Keep loss/replay exposure deliberately small on the shared DreamHost MySQL host.
INGEST_BATCH_LINES = 20
WRITE_OBJECTS = set([ 'REST.PUT.PART',
                      'REST.PUT.OBJECT',
                      'REST.POST.OBJECT',
                      'REST.POST.UPLOAD',
                      'REST.POST.UPLOADS',
                      'REST.COPY.PART'
                     ])

DEL_OBJECTS = set(['REST.DELETE.OBJECT',
                   'REST.DELETE.UPLOAD',
                   'REST.POST.MULTI_OBJECT_DELETE',
                   'REST.PUT.BUCKET',
                   'REST.PATCH.BUCKET',
                   'REST.DELETE.BUCKET',
                   'S3.EXPIRE.OBJECT',
                   ])


GET_OBJECTS = set([ 'REST.GET.OBJECT',
                    'REST.COPY.PART_GET',
                    'WEBSITE.GET.OBJECT' ])

# We ignore these
MISC_OBJECTS = set([
    'REST.COPY.NOTIFICATION',
    'REST.COPY.OBJECT',
    'REST.COPY.OBJECT_GET',
    'REST.GET.ACCELERATE',
    'REST.GET.ACL',
    'REST.GET.ANALYTICS',
    'REST.HEAD.TORRENT',
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
    'REST.GET.OBJECT_ATTRIBUTES',
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
    'REST.POST.LOCATION',
    'REST.POST.NOTIFICATION',
    'REST.POST.OBJECT_ATTRIBUTES',
    'REST.POST.RESTORE',
    'REST.POST.SELECT',
    'REST.POST.TORRENT',
    'REST.POST.WEBSITE',
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

# The config used for all S3 operations
config_unsigned = Config(connect_timeout=5, retries={'max_attempts': 4}, signature_version=UNSIGNED)
config_signed   = Config(connect_timeout=5, retries={'max_attempts': 4})


ignore_keys = set()

threads_started = 0
# S3 reads may run concurrently.  This serializes the atomic download/checkpoint
# transaction within one process; cross-process MySQL lock conflicts are retried.
database_write_lock = threading.Lock()

################################################################
### stats
################################################################

def stats_update_dtime(dtime):
    if STAT_S3_EARLIEST not in stats:
        stats[STAT_S3_EARLIEST] = dtime
    if STAT_S3_LATEST not in stats:
        stats[STAT_S3_LATEST] = dtime
    stats[STAT_S3_EARLIEST] = min(stats[STAT_S3_EARLIEST], dtime)
    stats[STAT_S3_LATEST] = max(stats[STAT_S3_LATEST], dtime)

def print_statistics():
    for (k,v) in stats.items():
        logging.info("%s %s",k,v)



################################################################
### Low-level routines for working with S3
################################################################

def s3_get_object(*, Bucket=None, Key=None, url=None, Signed=True, byte_range=None, etag=None):
    logging.debug("Bucket=%s Key=%s url=%s Signed=%s",Bucket,Key,url,Signed)
    if url:
        p = urllib.parse.urlparse(Prefix)
        Bucket = p.netloc
        Key    = p.path[1:]

    assert Bucket is not None
    assert Key is not None

    s3client  = boto3.client('s3', config = config_signed if Signed else config_unsigned)
    try:
        params = {'Bucket': Bucket, 'Key': Key}
        if byte_range is not None:
            params['Range'] = byte_range
        if etag is not None:
            params['IfMatch'] = etag
        return s3client.get_object(**params)
    except botocore.exceptions.ParamValidationError:
        logging.error("Bucket=%s Key=%s",Bucket,Key)
        raise


def s3_get_objects(*, Bucket=None, Prefix=None, url=None, limit=sys.maxsize, Signed=True):
    """Iterator for all s3 objects beginning with a prefix"""
    logging.debug("Bucket=%s Prefix=%s url=%s limit=%s Signed=%s",Bucket,Prefix,url,limit,Signed)
    if url is not None:
        p = urllib.parse.urlparse(url)
        Bucket = p.netloc
        Prefix = p.path[1:]

    assert Bucket is not None
    assert Prefix is not None

    s3client  = boto3.client('s3', config = config_signed if Signed else config_unsigned)
    paginator = s3client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=Bucket, Prefix=Prefix)
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
    if count==0:
        logging.error("no objects with prefix s3://%s/%s", Bucket, Prefix)


def s3_delete_object(*, Bucket, Key):
    logging.debug("Bucket=%s Key=%s",Bucket,Key)
    assert type(Bucket)==str
    assert type(Key)==str
    s3client  = boto3.client('s3', config = config_signed)
    s3client.delete_object(Bucket=Bucket, Key=Key)


################################################################
### hashing routines
################################################################


BUFSIZE=65536
def import_s3obj(obj):
    """
    This imports an S3 Object into the database, hashing it if necessary.
    It does not import S3 download logs. Those are in a different format and are imported by add_download().

    Typical obj:
    {'Key': 'corpora/files/2009-audio/media1/media1_27_192kbps_44100Hz_Stereo_art.mp3',
     'LastModified': datetime.datetime(2020, 11, 21, 23, 7, 31, tzinfo=tzlocal()),
     'ETag': '"3045e3c6a79e791bbacd97a06c27f969"',
     'Size': 384429,
     'StorageClass': 'INTELLIGENT_TIERING',
     'Bucket': 'digitalcorpora'}
    :param auth: authentication object.
    :param obj: dictionary with s3 object information.
    """

    # Reset timeout while hashing
    #signal.alarm(obj['timeout'])

    # Get the info
    auth   = obj['auth']
    s3key  = obj['Key']

    logging.info("import_s3obj %s",s3key)

    # Make sure that this object is in the database.
    cmd  = "INSERT INTO downloadable (s3key,bytes,mtime,etag) VALUES (%s,%s,%s,%s)"
    vals = (s3key, obj['Size'], obj['LastModified'], obj['ETag'])
    try:
        dbsupport.DBMySQL.csfr(auth, cmd, vals, nolog=[1062])
    except pymysql.err.IntegrityError as e:
        if e.args[0]==1062:
            # It already exists. If the ETag hasn't changed and we have both sha2_256 and sha3_256, just return
            rows = dbsupport.DBMySQL.csfr(auth, "SELECT ETag FROM downloadable WHERE s3key=%s AND (sha2_256 IS NOT NULL) AND (sha3_256 IS NOT NULL)", (s3key,))
            if len(rows)==1 and rows[0][0]==obj['ETag']:
                logging.info('ETag matches; will not update %s', s3key)
                return None
        else:
            raise e

    # Get a handle to the s3 object
    try:
        o2 = s3_get_object(Bucket = obj['Bucket'], Key=obj['Key'], Signed=True)
    except botocore.exceptions.ParamValidationError as e:
        logging.error("Bucket=%s Key=%s",obj['Bucket'],obj['Key'])
        raise

    """
    Typical o2:
    {'ResponseMetadata':
      {'RequestId': 'EF6D913C1C48EEF1',
       'HostId': 'CB6TRV/KlxtzU4FbXiYQKb6+PPYztCzvdI1FcXAeAoNeXkiGhm+BwBrrIUqbNyGPy3XsqsKENOU=',
       'HTTPStatusCode': 200,
       'HTTPHeaders':
          {'x-amz-id-2': 'CB6TRV/KlxtzU4FbXiYQKb6+PPYztCzvdI1FcXAeAoNeXkiGhm+BwBrrIUqbNyGPy3XsqsKENOU=',
           'x-amz-request-id': 'EF6D913C1C48EEF1',
           'date': 'Tue, 16 Feb 2021 01:32:14 GMT',
           'last-modified': 'Sat, 21 Nov 2020 23:07:31 GMT',
           'etag': '"3045e3c6a79e791bbacd97a06c27f969"',
           'x-amz-storage-class': 'INTELLIGENT_TIERING',
           'x-amz-version-id': 'kNdAWbQHuj0p_HxvobEGvcjuZKWox7Ct',
           'accept-ranges': 'bytes',
           'content-type': 'audio/mpeg',
           'content-length': '384429',
           'server': 'AmazonS3'},
       'RetryAttempts': 0},
      'AcceptRanges': 'bytes',
      'LastModified': datetime.datetime(2020, 11, 21, 23, 7, 31, tzinfo=tzutc()),
      'ContentLength': 384429,
      'ETag': '"3045e3c6a79e791bbacd97a06c27f969"',
      'VersionId': 'kNdAWbQHuj0p_HxvobEGvcjuZKWox7Ct',
      'ContentType': 'audio/mpeg',
      'Metadata': {},
      'StorageClass': 'INTELLIGENT_TIERING',
      'Body': <botocore.response.StreamingBody object at 0x7f0d5f98ca10>}
    """
    # Download and incrementally hash the object's body
    logging.info("start hashing s3://%s/%s",obj['Bucket'],obj['Key'])
    t0       = time.time()
    body     = o2['Body']
    bytes_hashed = 0
    last_notification = 0
    sha2_256 = hashlib.sha256()
    sha3_256 = hashlib.sha3_256()
    M = 1_000_000
    while True:
        data = body.read(BUFSIZE)
        if len(data)==0:
            break
        sha2_256.update(data)
        sha3_256.update(data)
        bytes_hashed += len(data)
        if bytes_hashed > last_notification + NOTIFICATION_SIZE:
            p = bytes_hashed/obj['Size']
            t = time.time() - t0
            logging.info("%s bytes hashed: %dM out of %dM in %d seconds (%5.2f%%)",obj['Key'],bytes_hashed/M,obj['Size']/M,t,p*100.0)
            last_notification = bytes_hashed
    assert bytes_hashed == o2['ContentLength']
    t1 = time.time()

    # Update the database. Remember, every column except the key may have changed.
    cmd = "update downloadable set ETag=%s, mtime=%s, bytes=%s, sha2_256=%s, sha3_256=%s where s3key=%s"
    vals = (o2['ETag'], o2['LastModified'], bytes_hashed, sha2_256.hexdigest(), sha3_256.hexdigest(), s3key)
    dbsupport.DBMySQL.csfr(auth, cmd, vals)
    logging.info('updated %s.  %d bytes, %6.2f seconds.  (%d Mb/sec)', s3key, bytes_hashed, (t1 -t0), (bytes_hashed /1000000) / (t1 -t0))
    return s3key


REQUIRE_TIME_MATCH = False
def hash_s3prefix(auth, Prefix, *, threads=40, timeout=DEFAULT_TIMEOUT):
    """Find all of the objects with an Prefix that require hashing, then download and hash them all in parallel"""
    logging.info("hash_s3prefix %s",Prefix)
    p = urllib.parse.urlparse(Prefix)

    # First, get all of the keys and etags from the database that match this prefix
    # We no longer require that mtime hasn't been changed because of timezone problems.
    # We need to use our own auth because we don't want it activated
    auth2 = copy.deepcopy(auth)
    lk = p.path +"%"
    rows = dbsupport.DBMySQL.csfr(auth2,
                               """select s3key,etag,mtime from downloadable
                               WHERE s3key LIKE %s AND (sha2_256 IS NOT NULL) AND (sha3_256 IS NOT NULL)
                               """, (lk,))
    logging.info("found %d entries in database with hashes", len(rows))
    hashed = {row[0]: {'ETag': row[1], 'mtime': row[2]} for row in rows}

    already_hashed = 0

    # This is surprisingly fast
    to_hash = []
    for obj in s3_get_objects(Bucket=S3_DATA_BUCKET, Prefix=Prefix, Signed=False):
        s3key = obj['Key']
        try:
            t1 = obj['LastModified'].replace(tzinfo=None)
            t2 = hashed[s3key]['mtime']
            # for now ignore t1==t2 because our time was in local time, and the timezone changed
            # if obj['ETag']==hashed[s3key]['ETag'] and t1==t2:
            if obj['ETag']==hashed[s3key]['ETag']:
                logging.debug('Already hashed in database: %s  ETag: %s', obj['Key'], obj['ETag'])
                already_hashed +=1
                if t1!=t2:
                    logging.info("Updating mtime in database for %s etag %s from %s --> %s ",
                                 obj['Key'], obj['ETag'], t2, t1)
                    dbsupport.DBMySQL.csfr(auth2,
                                        "UPDATE downloadable SET mtime=%s WHERE s3key=%s AND etag=%s",
                                        (t1, obj['Key'], obj['ETag']))
                continue
        # pylint: disable=W0612
        except KeyError as e:
            pass

        logging.info("Need to hash: %s %s",obj['Key'],obj['ETag'])
        obj['auth']   = auth
        obj['Bucket'] = p.netloc if p.netloc else S3_DATA_BUCKET
        obj['timeout'] = timeout
        to_hash.append(obj)

    # Now hash those that need to be hashed
    logging.info("Objects to hash: %d  (already hashed: %d). Threads=%s", len(to_hash), already_hashed, threads)
    if threads==1:
        for obj in to_hash:
            import_s3obj(obj)
        return

    # This is the multiprocessing implementation
    if MULTIPROCESSING:
        with multiprocessing.Pool(threads) as p:
            p.map(import_s3obj, to_hash)
        return

    # This is the threadpool implementation
    q = queue.Queue()
    def worker():
        while True:
            obj = q.get()
            print(f'Working on {obj}')
            import_s3obj(obj)
            print(f'Finished {obj}')
            q.task_done()
    for i in range(threads):
        threading.Thread(target=worker, daemon=True).start()

    for obj in to_hash:
        q.put(obj)
    q.join()
    print('All work completed')
    return



################################################################
### logfile management routines
################################################################


## Insert an object (S3 or Weblog) into the SQL database associated with logs
## Requires updating the downloadable and the user_agent tables as well

seen_dates = set()
ingested_s3key = set()
ingested_user_agent = set()

INGEST_STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS s3_log_ingest_state (
    s3key VARCHAR(768) NOT NULL,
    etag VARCHAR(128) NOT NULL,
    next_byte BIGINT UNSIGNED NOT NULL DEFAULT 0,
    completed TINYINT(1) NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (s3key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


def ensure_ingest_state_schema(auth):
    """Create the small, durable checkpoint table used for S3 access logs."""
    dbsupport.DBMySQL.csfr(auth, INGEST_STATE_SCHEMA)


def cached_db(auth):
    """Return the connection associated with this ingestion worker."""
    try:
        return auth.cache_get()
    except KeyError:
        db = dbsupport.DBMySQL(auth)
        auth.cache_store(db)
        return db


def get_ingest_state(auth, key, etag):
    """Return the committed byte offset for this exact version of an S3 log."""
    db = cached_db(auth)
    cursor = db.cursor()
    try:
        cursor.execute(
            """INSERT INTO s3_log_ingest_state (s3key, etag)
               VALUES (%s, %s)
               ON DUPLICATE KEY UPDATE
                 next_byte=IF(etag=VALUES(etag), next_byte, 0),
                 completed=IF(etag=VALUES(etag), completed, 0),
                 etag=VALUES(etag)""",
            (key, etag))
        cursor.execute("SELECT next_byte, completed FROM s3_log_ingest_state WHERE s3key=%s", (key,))
        next_byte, completed = cursor.fetchone()
        return next_byte, bool(completed)
    finally:
        cursor.close()


def checkpoint_completion_needed(offset, size):
    """Return whether a fully written S3 log needs only finalization.

    ``next_byte`` is committed with each batch of download rows.  A process can
    stop after committing the final batch but before setting ``completed``.  In
    that state, re-reading at ``size`` would make S3 reject the empty range.
    """
    if offset > size:
        raise RuntimeError(f"S3 log checkpoint is beyond object size: {offset} > {size}")
    return offset == size


def lookup_rows(downloads):
    """Return deterministic lookup rows, preferring a known size for each S3 key."""
    downloadable_by_key = {}
    for obj in downloads:
        if obj.key not in downloadable_by_key or (
                downloadable_by_key[obj.key] is None and obj.object_size is not None):
            downloadable_by_key[obj.key] = obj.object_size
    downloadable_rows = sorted(downloadable_by_key.items())
    user_agents = sorted(
        {obj.user_agent for obj in downloads},
        key=lambda agent: (agent is not None, (agent or "").casefold(), agent or ""))
    return downloadable_rows, user_agents


def insert_lookup_rows(cursor, downloads):
    """Populate lookup rows in autocommit statements before a batch transaction."""
    downloadable_rows, user_agents = lookup_rows(downloads)
    if downloadable_rows:
        cursor.execute(
            "INSERT IGNORE INTO downloadable (s3key, bytes) VALUES "
            + ", ".join(["(%s, %s)"] * len(downloadable_rows)),
            [value for row in downloadable_rows for value in row])

    if user_agents:
        cursor.execute(
            "INSERT IGNORE INTO user_agents (user_agent) VALUES "
            + ", ".join(["(%s)"] * len(user_agents)), user_agents)


def insert_download_with_cursor(cursor, obj):
    """Insert one download using lookup rows prepared before the transaction."""
    cursor.execute(
        """INSERT INTO downloads (did, user_agent_id, remote_ipaddr, dtime, bytes_sent)
           SELECT downloadable.id, user_agents.id, %s, %s, %s
           FROM downloadable JOIN user_agents
           WHERE downloadable.s3key=%s AND user_agents.user_agent=%s""",
        (obj.remote_ip, obj.dtime, obj.bytes_sent, obj.key, obj.user_agent))
    logging.debug("%s %s %s bytes_sent=%s", obj.dtime, obj.key, obj.remote_ip, obj.bytes_sent)


def is_retryable_mysql_error(error):
    """Return whether MySQL says this batch can be safely retried."""
    return isinstance(error, pymysql.err.OperationalError) and error.args and \
        error.args[0] in MYSQL_RETRYABLE_ERROR_CODES


def commit_s3_log_batch(auth, key, etag, batch, next_byte):
    """Atomically store downloads and their checkpoint after idempotent lookups."""
    db = cached_db(auth)
    cursor = db.cursor()
    raw_download_lines = []
    downloads = []
    count = 0
    bytes_sent = 0
    try:
        for line in batch:
            try:
                obj = weblog.weblog.S3Log(line)
            except S3LogException:
                continue
            if obj.key in ignore_keys:
                continue
            what = validate_obj(auth, obj)
            stats[STAT_S3_RECORDS] += 1
            if what == DOWNLOAD:
                downloads.append(obj)
                raw_download_lines.append(line)
                stats[STAT_S3_DOWNLOAD_RECORDS] += 1
                stats_update_dtime(obj.dtime)
                bytes_sent += obj.bytes_sent or 0
                count += 1

        for attempt in range(INGEST_TRANSACTION_RETRIES):
            try:
                # Lookup rows are independently committed.  If a later atomic
                # transaction fails, extra lookup rows are harmless and retryable.
                insert_lookup_rows(cursor, downloads)
                with database_write_lock:
                    db.conn.begin()
                    for obj in downloads:
                        insert_download_with_cursor(cursor, obj)
                    cursor.execute(
                        """UPDATE s3_log_ingest_state SET next_byte=%s
                           WHERE s3key=%s AND etag=%s AND completed=0""",
                        (next_byte, key, etag))
                    if cursor.rowcount != 1:
                        raise RuntimeError(f"lost checkpoint for S3 log {key}")
                    db.conn.commit()
                break
            except Exception as error:
                db.conn.rollback()
                if not is_retryable_mysql_error(error) or attempt + 1 == INGEST_TRANSACTION_RETRIES:
                    raise
                delay = 0.05 * (attempt + 1)
                logging.warning("retrying S3 batch after MySQL error %s in %.2fs", error.args[0], delay)
                time.sleep(delay)
    except Exception:
        db.conn.rollback()
        cursor.close()
        raise
    cursor.close()
    progress_reporter.committed(len(batch), count, bytes_sent)
    return count, raw_download_lines


def mark_s3_log_completed(auth, key, etag):
    """Commit completion before deleting the source S3 object."""
    dbsupport.DBMySQL.csfr(
        auth,
        """UPDATE s3_log_ingest_state SET completed=1
           WHERE s3key=%s AND etag=%s""",
        (key, etag), rowcount=1)
def insert_logfile_obj_into_db(auth, obj):
    """ First make sure that it's in downloads and get its ID.
    Note that the downloads are tracked by key, even though the object identified by the key may change.
    This is not very efficient, as it requires (on average) two aborted inserts due to duplicate keys and then an insert with two subselects per object.
    The aborted inserts get accelerated by the MySQL database because the files are indexed, but we can make this faster by only performing each insert once and tracking it in a set.
    We can't get away from the subselects due to threading issues.
    """
    if (obj.key,obj.object_size) not in ingested_s3key:
        dbsupport.DBMySQL.csfr(auth,
                            """INSERT INTO downloadable (s3key, bytes) VALUES (%s,%s) """,
                            (obj.key, obj.object_size), ignore=[1062])
        ingested_s3key.add((obj.key, obj.object_size))

    # Make sure the browser is in the databse
    if obj.user_agent not in ingested_user_agent:
        dbsupport.DBMySQL.csfr(auth,
                            """INSERT INTO user_agents (user_agent) VALUES (%s) """,
                            (obj.user_agent,), ignore=[1062])
        ingested_user_agent.add(obj.user_agent)


    # Now INSERT the file into the table
    dbsupport.DBMySQL.csfr(auth,
                        """
                        INSERT INTO downloads (did, user_agent_id, remote_ipaddr, dtime, bytes_sent)
                        VALUES ((select id from downloadable where s3key=%s),
                                (select id from user_agents where user_agent=%s),
                               %s,%s,%s)
                        """,
                        (obj.key, obj.user_agent, obj.remote_ip, obj.dtime, obj.bytes_sent))
    logging.debug("%s %s %s bytes_sent=%s",obj.dtime,obj.key,obj.remote_ip, obj.bytes_sent)

## s3 logs (a collection of objects in an S3 bucket; each object can have 1 or more S3 logs.)
def s3_logs_info(limit=sys.maxsize):
    """Report information regarding S3 logs that haven't been downloaded"""
    for obj in s3_get_objects( Bucket=S3_LOG_BUCKET, Prefix='', limit=limit, Signed=True):
        stats[STAT_S3_OBJECTS] += 1
        stats_update_dtime(obj['LastModified'])
    print_statistics()

## s3 logs (a collection of objects in an S3 bucket; each object can have 1 or more S3 logs.)
def s3_logs_info(limit=sys.maxsize):
    """Report information regarding S3 logs that haven't been downloaded"""
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

# pylint: disable=R0911
def validate_obj(auth, obj):
    """Write a logfile object to the database"""
    if obj.dtime.date() not in seen_dates:
        # Status report
        logging.info("Ingesting date=%s",obj.dtime.date())
        seen_dates.add(obj.dtime.date())
    if obj.operation in GET_OBJECTS:
        if obj.http_status in [200,206] or obj.http_status is None:
            return DOWNLOAD
        elif obj.http_status in range(300,400):
            return BAD
        elif obj.http_status in range(400,500):
            return BAD
        elif obj.http_status in [500]:
            # internal error
            return BAD
        else:
            # Log that we didn't ingest something, but throw it away
            logging.warning("will not ingest HTTP status %s: %s",obj.http_status, obj.line)
            return BAD
    elif obj.operation in WRITE_OBJECTS:
        if obj.http_status in range(400,500):
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
            insert_logfile_obj_into_db(auth, obj)
        sums[what] += 1
        earliest = obj.dtime if earliest is None else min(earliest,obj.dtime)
        latest = obj.dtime if latest is None else max(latest,obj.dtime)
        if (ct>0) and (ct % 10000)==0:
            logging.info("%s processed (last batch: %s to %s)...",ct,earliest,latest)
            earliest = None
            latest = None
    print("Ingest Status:")
    for (k,v) in sums.items():
        logging.info("%s %s",k,v)

def s3_log_ingest(s3_logfile, s3_logfile_lock, auth, s3_obj):
    """Ingest one S3 access-log object in restartable, atomic batches.

    The database checkpoint is updated in the same transaction as the rows it
    covers.  A timeout can therefore replay at most the current batch.
    :param auth: authentication token to write to the database
    :param s3_obj: object description returned by ``list_objects_v2``
    """
    global threads_started
    key = s3_obj['Key']
    etag = s3_obj['ETag']
    size = s3_obj['Size']
    assert key is not None
    assert isinstance(key, str)
    offset, completed = get_ingest_state(auth, key, etag)
    checkpoint_at_end = checkpoint_completion_needed(offset, size)
    if completed or checkpoint_at_end:
        if not completed:
            logging.info("finalizing fully checkpointed S3 log %s", key)
            mark_s3_log_completed(auth, key, etag)
        logging.info("deleting completed S3 log %s", key)
        s3_delete_object(Bucket=S3_LOG_BUCKET, Key=key)
        return 0

    count = 0
    response = s3_get_object(Bucket=S3_LOG_BUCKET, Key=key, Signed=True,
                             byte_range=f"bytes={offset}-", etag=etag)
    pending = b''
    batch = []
    batch_end = offset

    def commit_batch():
        nonlocal count, batch
        if not batch:
            return
        tally, raw_lines = commit_s3_log_batch(auth, key, etag, batch, batch_end)
        count += tally
        with s3_logfile_lock:
            s3_logfile.writelines(raw_lines)
            s3_logfile.flush()
        batch = []

    while True:
        block = response['Body'].read(64 * 1024)
        if not block:
            break
        pending += block
        while b'\n' in pending:
            raw_line, pending = pending.split(b'\n', 1)
            raw_line += b'\n'
            batch_end += len(raw_line)
            try:
                batch.append(raw_line.decode('utf-8'))
            except UnicodeDecodeError:
                logging.warning("skipping non-UTF-8 S3 log record in %s at byte %s", key, batch_end)
            if len(batch) >= INGEST_BATCH_LINES:
                commit_batch()
    if pending:
        batch_end += len(pending)
        try:
            batch.append(pending.decode('utf-8'))
        except UnicodeDecodeError:
            logging.warning("skipping non-UTF-8 S3 log record in %s at byte %s", key, batch_end)
    commit_batch()
    if batch_end != size:
        raise RuntimeError(f"S3 log {key} ended at byte {batch_end}, expected {size}")
    mark_s3_log_completed(auth, key, etag)

    # It turns out that deleting objects can take a really long time, so we will move this to a work queue
    if DELETE_IN_BACKGROUND:
        try:
            threading.Thread(target=s3_delete_object, kwargs={'Bucket':S3_LOG_BUCKET, 'Key':key}).start()
            threads_started += 1
        except RuntimeError as e:
            # Delete the object manually
            logging.error(f"Error thread start: {e} total threads started: {threads_started} active_count: {threading.active_count()}")
            s3_delete_object(Bucket=S3_LOG_BUCKET, Key=key)
    else:
        s3_delete_object(Bucket=S3_LOG_BUCKET, Key=key)

    return count


DIE_PARENT = "<<DIE PARENT>>"
DIE_THREAD = "<<DIE THREAD>>"     # hopefully no S3Key with this
def s3_logs_download_ingest_and_save(auth, threads=1, limit=sys.maxsize, timeout=DEFAULT_TIMEOUT,
                                     prefix=''):
    """Download an S3 logs and ingest them.
    Runs in the main thread.
    :param auth: authentication token to write to the database.
    :param threads: number of threads to use
    :param prefix: ingest only S3 log objects whose keys start with this prefix
    """
    count = 0
    progress_reporter.reset()
    logging.info("ingestion started for prefix %r; progress reports every %s seconds",
                 prefix, PROGRESS_INTERVAL_SECONDS)
    q  = queue.Queue(maxsize = threads*2)          # forward channel
    bc = queue.Queue()          # backchannel

    logfile_path = S3_LOGFILE_PATH
    if prefix:
        # Parallel prefix workers must not concurrently append to one local audit log.
        prefix_digest = hashlib.sha256(prefix.encode("utf-8")).hexdigest()[:16]
        logfile_path = f"{S3_LOGFILE_PATH}.{prefix_digest}"
    s3_logfile      = open(logfile_path,"a")
    s3_logfile_lock = threading.Lock()
    def worker():
        """Runs in the worker thread"""
        nonlocal count
        # deepcopy assures that each thread has its own copy of the auth object.
        auth2 = copy.deepcopy(auth)
        while True:
            s3_obj = q.get()
            logging.debug("key=%s", s3_obj)
            if s3_obj==DIE_THREAD:
                q.task_done()
                return
            try:
                tally = s3_log_ingest(s3_logfile, s3_logfile_lock, auth2, s3_obj)
                count += tally
            except Exception:
                logging.exception("failed to ingest S3 log %s", s3_obj['Key'])
                bc.put(DIE_PARENT)
            finally:
                q.task_done()
            time.sleep(0)

    # Start the threads
    for _ in range(threads):
        threading.Thread(target=worker, daemon=True).start()
    ensure_ingest_state_schema(auth)
    if True:
        for (ct,obj) in enumerate(s3_get_objects(Bucket=S3_LOG_BUCKET, Prefix=prefix), 1):
            stats[STAT_S3_OBJECTS] += 1
            if count>limit:
                break
            q.put(obj,timeout=timeout)  # if we have blocked more than 30 seconds, something is wrong

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

    # Tell threads to die, then block till they all die.
    for _ in range(threads):
        q.put(DIE_THREAD)
    q.join()


def db_copy( auth ):
    """Copy the downloads from the dev database to the production database.
    This was created because I accidentally committed to the production database.
    There are 17,000 transactions and this ran in less than a minute.
    """
    db = dbsupport.DBMySQL(auth)
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
            insert_logfile_obj_into_db( auth, obj)
            print("Added",s3key,remote_ip,dtime)
    print("total:",count)

def db_stats( auth ):
    db = dbsupport.DBMySQL(auth)
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

def ensure_summary_state_table(cursor):
    """Create the tiny journal that makes large daily summaries resumable."""
    cursor.execute(
        f"CREATE TABLE IF NOT EXISTS {SUMMARY_STATE_TABLE} ("
        "summary_day DATE NOT NULL PRIMARY KEY, "
        "phase VARCHAR(16) NOT NULL, "
        "updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP "
        "ON UPDATE CURRENT_TIMESTAMP) ENGINE=InnoDB")
    cursor.execute("SELECT GET_LOCK('download-summary-schema-migration', 60)")
    if cursor.fetchone()[0] != 1:
        raise RuntimeError("could not acquire download-summary schema migration lock")
    try:
        cursor.execute(f"SHOW COLUMNS FROM {SUMMARY_STATE_TABLE}")
        column_names = {column[0] for column in cursor.fetchall()}
        missing_boundaries = {"processed_through_id", "prepared_through_id"} - column_names
        if missing_boundaries:
            cursor.execute(f"SELECT COUNT(*) FROM {SUMMARY_STATE_TABLE} WHERE phase='prepared'")
            if cursor.fetchone()[0]:
                cursor.execute(f"UPDATE {SUMMARY_STATE_TABLE} SET phase='legacy_prepared' "
                               "WHERE phase='prepared'")
                cursor.connection.commit()
            for name in missing_boundaries:
                cursor.execute(f"ALTER TABLE {SUMMARY_STATE_TABLE} "
                               f"ADD COLUMN {name} BIGINT UNSIGNED NOT NULL DEFAULT 0")
    finally:
        cursor.execute("SELECT RELEASE_LOCK('download-summary-schema-migration')")


def db_summarize_day(auth, day, verbose=False, reset_partial_summary=False):
    """Summarize one stable UTC day without a long, all-row delete statement.

    A journal stores the inclusive raw-ID boundary captured by each pass.  The
    grouped summary and that boundary commit together; later batches delete only
    the captured IDs.  Thus retries cannot delete late arrivals that were not
    aggregated, and a completed day can summarize a later raw-ID range.
    """
    next_day = day + datetime.timedelta(days=1)
    db = dbsupport.DBMySQL(auth)
    cursor = db.cursor()
    lock_name = f"download-summarize-{day:%Y-%m-%d}"
    try:
        cursor.execute("SELECT GET_LOCK(%s, 0)", (lock_name,))
        if cursor.fetchone()[0] != 1:
            raise RuntimeError(f"summary already running for {day:%Y-%m-%d}")
        ensure_summary_state_table(cursor)

        cursor.execute(f"SELECT phase, processed_through_id, prepared_through_id "
                       f"FROM {SUMMARY_STATE_TABLE} WHERE summary_day=%s", (day,))
        row = cursor.fetchone()
        if reset_partial_summary:
            if row:
                raise RuntimeError("cannot reset a journaled summary; resume it without --reset_partial_summary")
            cursor.execute("SELECT 1 FROM downloads WHERE dtime>=%s AND dtime<%s AND summary=0 LIMIT 1",
                           (day, next_day))
            if not cursor.fetchone():
                raise RuntimeError("cannot reset a day with no raw rows")
            db.conn.begin()
            cursor.execute("DELETE FROM downloads WHERE dtime>=%s AND dtime<%s AND summary=1",
                           (day, next_day))
            removed = cursor.rowcount
            db.conn.commit()
            logging.info("removed %s legacy summary rows for %s", removed, day.isoformat())

            row = None

        if row:
            phase, processed_through_id, prepared_through_id = row
        else:
            phase, processed_through_id, prepared_through_id = None, 0, 0

        cursor.execute("SELECT MAX(id) FROM downloads WHERE dtime>=%s AND dtime<%s "
                       "AND summary=0 AND id>%s", (day, next_day, processed_through_id))
        raw_max_id = cursor.fetchone()[0]
        if phase == "complete" and raw_max_id is None:
            return 0
        if phase is None and raw_max_id is None:
            return 0

        if phase is None:
            cursor.execute("SELECT 1 FROM downloads WHERE dtime>=%s AND dtime<%s AND summary=1 LIMIT 1",
                           (day, next_day))
            if cursor.fetchone():
                raise RuntimeError(
                    f"{day:%Y-%m-%d} has both raw and summary rows; "
                    "rerun with --reset_partial_summary after verifying the raw logs")
        if phase in (None, "complete"):
            cmd = ("INSERT INTO downloads (did, remote_ipaddr, user_agent_id, dtime, bytes_sent, summary) "
                   "SELECT did, remote_ipaddr, user_agent_id, DATE(dtime), SUM(bytes_sent), 1 "
                   "FROM downloads WHERE dtime>=%s AND dtime<%s AND summary=0 "
                   "AND id>%s AND id<=%s GROUP BY did, remote_ipaddr, user_agent_id, DATE(dtime)")
            db.conn.begin()
            try:
                cursor.execute(cmd, (day, next_day, processed_through_id, raw_max_id))
                grouped_rows = cursor.rowcount
                if phase is None:
                    cursor.execute(f"INSERT INTO {SUMMARY_STATE_TABLE} "
                                   "(summary_day, phase, processed_through_id, prepared_through_id) "
                                   "VALUES (%s, 'prepared', %s, %s)",
                                   (day, processed_through_id, raw_max_id))
                else:
                    cursor.execute(f"UPDATE {SUMMARY_STATE_TABLE} SET phase='prepared', "
                                   "prepared_through_id=%s WHERE summary_day=%s",
                                   (raw_max_id, day))
                db.conn.commit()
                logging.info("prepared %s summary rows for %s", grouped_rows, day.isoformat())
            except Exception:
                db.conn.rollback()
                raise
            phase = "prepared"
            prepared_through_id = raw_max_id
        if phase != "prepared":
            if phase == "legacy_prepared":
                raise RuntimeError(
                    f"{day:%Y-%m-%d} was prepared by a legacy journal without a raw-ID boundary; "
                    "verify the raw logs and repair it explicitly")
            raise RuntimeError(f"unexpected summary phase {phase!r} for {day:%Y-%m-%d}")

        deleted = 0
        batches = 0
        while True:
            db.conn.begin()
            try:
                cursor.execute(
                    f"DELETE FROM downloads WHERE dtime>=%s AND dtime<%s AND summary=0 "
                    "AND id>%s AND id<=%s "
                    f"LIMIT {SUMMARY_DELETE_BATCH_SIZE}",
                    (day, next_day, processed_through_id, prepared_through_id))
                batch_rows = cursor.rowcount
                db.conn.commit()
            except Exception:
                db.conn.rollback()
                raise
            if batch_rows == 0:
                break
            deleted += batch_rows
            batches += 1
            if batches == 1 or batches % 10 == 0:
                logging.info("summarized %s: deleted %s raw rows in %s batches",
                             day.isoformat(), deleted, batches)

        db.conn.begin()
        try:
            cursor.execute(f"UPDATE {SUMMARY_STATE_TABLE} SET phase='complete', "
                           "processed_through_id=prepared_through_id WHERE summary_day=%s", (day,))
            db.conn.commit()
        except Exception:
            db.conn.rollback()
            raise
        if verbose:
            print(f"summarize {day}: deleted {deleted} raw rows")
        return deleted
    finally:
        try:
            cursor.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
        finally:
            cursor.close()

def db_download_summarize(auth, first, last, verbose=False, max_days=None, optimize=False,
                          reset_partial_summary=False):
    saved = 0
    days = 0
    while first<=last and (max_days is None or days < max_days):
        saved += db_summarize_day(auth, first, verbose=verbose,
                                  reset_partial_summary=reset_partial_summary)
        first += datetime.timedelta(days=1)
        days += 1
    if verbose:
        print("Total saved:",saved)
    if saved and optimize:
        if verbose:
            print("optimizing")
        dbsupport.DBMySQL.csfr(auth, "optimize table downloads")


class TimeoutException(Exception):
    pass

def timeout_handler(num, stack):
    logging.error("TimeoutException")
    raise TimeoutException()

def db_gc( auth, url ):
    db = dbsupport.DBMySQL( auth )
    c = db.cursor()
    c.execute("SELECT s3key, id FROM downloadable")
    s3keys_in_db = {row[0]:row[1] for row in c.fetchall() }
    print("keys in database:",len(s3keys_in_db))

    # Now get the list of objects in S3
    count = 0
    for obj in s3_get_objects( url=url, Signed=True ):
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


def setup_parser():
    import argparse
    parser = argparse.ArgumentParser(description='Import the Digital Corpora logs.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--wipe", help="Wipe database and load a new schema", action='store_true')
    parser.add_argument("--debug", action='store_true')
    parser.add_argument("--verbose", action='store_true')
    parser.add_argument("--threads", "-j", type=int, default=DEFAULT_THREADS)
    parser.add_argument("--limit", type=int, default=sys.maxsize,
                        help="Number of imports when reading from text files or s3 objects when reading from s3")
    parser.add_argument("--s3_log_prefix", default='',
                        help="Only ingest S3 log objects whose keys start with this prefix")

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
    g.add_argument("--optimize_downloads", action='store_true',
                   help='rebuild downloads to reclaim disk space')
    g.add_argument("--copy", action='store_true',
                   help='Copy downloads from test to prod that are not present in prod')
    g.add_argument("--gc", action='store_true', help='Garbage collect the MySQL database')
    g.add_argument("--download_summarize", action='store_true', help='summarize downloads')
    parser.add_argument("--first", help="first date for summarizaiton")
    parser.add_argument("--last", help="last date for summarizaiton")
    parser.add_argument("--year", help="go from Jan 1 to Dec. 31 of this year",type=int)
    parser.add_argument("--max_summarize_days", type=int,
                        help="maximum number of days to summarize, starting with the oldest")
    parser.add_argument("--stable_only", action='store_true',
                        help="do not summarize the current UTC day")
    parser.add_argument("--reset_partial_summary", action='store_true',
                        help="discard legacy summary rows before rebuilding one verified raw day")
    parser.add_argument("--optimize", action='store_true',
                        help="run OPTIMIZE TABLE after summarization")
    parser.add_argument("--timeout", default=3500, type=int, help="Timeout in seconds")
    parser.add_argument("--nolock", action='store_true', help='do not lock dclogtool.py')

    # Tell me how to authenticate ---
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--aws", help="Get database password from aws secrets system", action='store_true')
    g.add_argument("--env", help="Get database password from environment variables", action='store_true')

    # Tell me which database to use
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--prod", help="Use production database", action='store_true')
    g.add_argument("--test", help="Use test database", action='store_true')

    parser.add_argument("--ignore_keys",help="path names to ignore")

    logging_support.add_argument(parser)
    return parser

def main():
    t0 = time.time()
    parser = setup_parser()
    args = parser.parse_args()
    logging_support.setup(args.loglevel,
                          log_format=logging_support.LOG_FORMAT.replace("%(message)s",
                                                                         "%(thread)d %(message)s"))
    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    if args.copy and args.test:
        logging.error("--copy requires --prod")
        sys.exit(1)

    if args.year:
        if args.first or args.last:
            logging.error("--year overwrites --first and --list")
            sys.exit(1)
        args.first=f"{args.year}-01-01"
        args.last =f"{args.year}-12-31"

    if args.reset_partial_summary:
        if not args.download_summarize or not args.first or args.first != args.last:
            parser.error("--reset_partial_summary requires --download_summarize with one --first/--last day")
    if args.s3_log_prefix and not args.s3_logs_download_ingest_and_save:
        parser.error("--s3_log_prefix requires --s3_logs_download_ingest_and_save")


    if args.ignore_keys:
        with open(args.ignore_keys,"r") as f:
            for line in f:
                ignore_keys.add(line.strip())

    database = "dcstats_test" if not args.prod else 'dcstats'
    # Select the authentication approach
    if args.aws:
        s = aws_secrets.get_secret()
        auth = dbsupport.DBMySQLAuth(host=s['host'],
                                  database=database,
                                  user=s['username'],
                                  password=s['password'],
                                  debug=args.debug)

    elif args.env:
        auth = dbsupport.DBMySQLAuth(host=os.environ['DBWRITER_HOSTNAME'],
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
        db = dbsupport.DBMySQL(auth)
        db.create_schema(open("schema.sql", "r").read())

    # Don't allow another copy to run the script
    if not args.nolock:
        locking.lock_script()

    # Do what we are supposed to do
    #signal.signal(signal.SIGALRM,timeout_handler)
    #signal.alarm(args.timeout)
    try:
        if args.apache_logfile_ingest:
            with logfile_opener(args.apache_logfile_ingest) as f:
                logfile_ingest(auth, f, weblog.weblog.Weblog)
        elif args.s3_logfile_ingest:
            with logfile_opener(args.s3_logfile_ingest) as f:
                logfile_ingest( auth, f, weblog.weblog.S3Log)
        elif args.hash_s3prefix:
            hash_s3prefix(auth, args.hash_s3prefix, threads=args.threads, timeout=args.timeout)
        elif args.s3_logs_download_ingest_and_save:
            try:
                s3_logs_download_ingest_and_save(auth, args.threads, args.limit,
                                                  prefix=args.s3_log_prefix)
            except KeyboardInterrupt as e:
                print(e,file=sys.stderr)
            if args.verbose:
                print_statistics()
        elif args.s3_logs_info:
            s3_logs_info(args.limit)
        elif args.copy:
            db_copy( auth )
        elif args.gc:
            db_gc( auth, "s3://" + D3_DATA_BUCKET)
        elif args.db_stats:
            db_stats( auth )
        elif args.optimize_downloads:
            logging.info("optimizing downloads")
            dbsupport.DBMySQL.csfr(auth, "OPTIMIZE TABLE downloads")

        if args.download_summarize:
            stable_last = datetime.datetime.utcnow().date() - datetime.timedelta(days=1)
            if args.first==None:
                rows = dbsupport.DBMySQL.csfr(
                    auth,
                    "SELECT date(dtime) FROM downloads WHERE summary=0 AND dtime<%s ORDER BY dtime LIMIT 1",
                    (stable_last + datetime.timedelta(days=1),))
                if not rows:
                    logging.info("no stable unsummarized downloads")
                    return
                first = rows[0][0]
            else:
                first = datetime.datetime.strptime(args.first, "%Y-%m-%d")
            if args.last==None:
                if args.stable_only:
                    last = stable_last
                else:
                    rows = dbsupport.DBMySQL.csfr(auth, "SELECT date(dtime) FROM downloads WHERE summary=0 ORDER BY dtime DESC LIMIT 1")
                    if not rows:
                        logging.info("no unsummarized downloads")
                        return
                    last = rows[0][0]
            else:
                last = datetime.datetime.strptime(args.last, "%Y-%m-%d")
            if first > last:
                logging.info("no eligible unsummarized downloads")
                return
            db_download_summarize(auth, first, last, verbose=args.verbose,
                                  max_days=args.max_summarize_days, optimize=args.optimize,
                                  reset_partial_summary=args.reset_partial_summary)
            if args.verbose:
                print("Running time1: ",int(time.time() - t0))

    except TimeoutException as e:
        pass
    finally:
        signal.alarm(0)


if __name__=="__main__":
    main()
