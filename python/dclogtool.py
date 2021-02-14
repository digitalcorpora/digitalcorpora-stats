#!/usr/bin/env python3
"""
digitalcorpora log tool.

"""

import os
import pymysql
import weblog.schema
import weblog.weblog
import boto3
import urllib


def import_logfile(logfile, wipe=False):
    conn = pymysql.connect(host=os.environ['DBWRITER_HOSTNAME'],
                           database=os.environ['DBWRITER_DATABASE'],
                           user=os.environ['DBWRITER_USERNAME'],
                           password=os.environ['DBWRITER_PASSWORD'])

    # see if the schema is present. If not, send it
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT count(*) from downloads")
    except pymysql.err.ProgrammingError:
        wipe = True
    if wipe:
        weblog.schema.send_schema(cursor)
    with open(logfile) as f:
        for line in f:
            obj = weblog.weblog.Weblog(line)
            weblog.schema.send_weblog(cursor, obj)

def s3hash_object(obj):
    """Called to hash an object in S3 if the hash is not in the database for this ETag.
    :param obj: An S3 object to hash. Looks like this:
        {'Key': 'downloads/tcpflow/tcpflow64-1.4.4.exe',
         'LastModified': datetime.datetime(2021, 2, 5, 17, 0, 52, tzinfo=tzlocal()),
         'ETag': '"202ca7776291c746b9cbee97b8334cce-4"',
         'Size': 30295072,
         'StorageClass': 'INTELLIGENT_TIERING'}
    """




def s3hash(s3root):
    p = urllib.parse.urlparse(s3root)
    assert p.scheme=='s3'
    s3 = boto3.client('s3')
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=p.netloc, Prefix=p.path[1:]):
        for obj in page['Contents']:
            if args.verbose:
                print(obj['Key'])
            s3hash_object(obj)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Import the Digital Corpora logs.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--wipe", help="Wipe database", action='store_true')
    parser.add_argument("--logfile", help="Log file to import")
    parser.add_argument("--s3hash", help="Scan s3 objects, hash and import")
    args = parser.parse_args()
    if args.logfile:
        import_logfile(args.logfile, wipe=args.wipe)
    if args.s3hash:
        s3hash(args.s3hash)
