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

def import_logfile(auth, logfile, args):
    # see if the schema is present. If not, send it with the wipe command
    db = ctools.dbfile.CBMySQL(auth)
    cursor = db.cursor()
    try:
        cursor.execute("SELECT count(*) from downloads")
    except pymysql.err.ProgrammingError:
        args.wipe = True
    if args.wipe:
        weblog.schema.send_schema(cursor)
    with open(logfile) as f:
        for line in f:
            obj = weblog.weblog.Weblog(line)
            weblog.schema.send_weblog(cursor, obj)


def import_s3(auth, s3prefix):
    p = urllib.parse.parse(s3prefix)

    s3client  = boto3.client('s3', config=Config(signature_version=UNSIGNED))
    paginator = s3client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=p.netloc, Prefix=p.path[1:])
    for page in pages:
        for obj in page.get('Contents'):
            print(obj)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Import the Digital Corpora logs.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--wipe", help="Wipe database", action='store_true')
    parser.add_argument("--prod", help="Use production databsae", action='store_true')
    parser.add_argument("--logfile", help="Log file to import")
    parser.add_argument("--aws", help="Get database password from aws secrets system", action='store_true')
    parser.add_argument("--env", help="Get database password from environment varialbes file")
    parser.add_argument("--debug", action='store_true')
    parser.add_argument("--s3prefix", help="Scan an S3 prefix")
    args = parser.parse_args()


    if args.aws:
        s = aws_secrets.get_secret()
        print("s=",s)
        auth = ctools.dbfile.DBMySQLAuth(host=s['host'],
                                         database=s['dbname'],
                                         user=s['username'],
                                         password=s['password'],
                                         debug=args.debug)

    elif args.env:
        database = "dcstats_test" if not args.prod else 'dcstats'
        auth = ctools.dbfile.DBMySQLAuth(host=os.environ['DBWRITER_HOSTNAME'],
                                         database=database,
                                         user=os.environ['DBWRITER_USERNAME'],
                                         password=os.environ['DBWRITER_PASSWORD'])

    if args.logfile:
        import_logfile(auth, args.logfile, args)

    if args.s3prefix:
        import_s3(auth, args.s3prefix)
