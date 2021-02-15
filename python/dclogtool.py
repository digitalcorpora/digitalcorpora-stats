#!/usr/bin/env python3
"""
digitalcorpora log tool.

"""

import os
import pymysql
import weblog.schema
import weblog.weblog


def import_logfile(logfile, args):
    database = 'dcstats_test" if not args.prod else 'dcstats'

    conn = pymysql.connect(host=os.environ['DBWRITER_HOSTNAME'],
                           database=database,
                           user=os.environ['DBWRITER_USERNAME'],
                           password=os.environ['DBWRITER_PASSWORD'])

    # see if the schema is present. If not, send it with the wipe command
    cursor = conn.cursor()
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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Import the Digital Corpora logs.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--wipe", help="Wipe database", action='store_true')
    parser.add_argument("--prod", help="Use production databsae", action='store_true')
    parser.add_argument("logfile", help="Log file to import")
    args = parser.parse_args()
    import_logfile(args.logfile, args)
