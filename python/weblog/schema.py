#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Routines for managing the databse schema.
- getting the schema file
- sending it into the datase
- sending a weblog object into the database in a single transaction.
"""

import os
from os.path import dirname,abspath

SCHEMA_FILE = os.path.join(dirname(dirname(abspath(__file__))), "schema.sql")

def get_schema():
    return open(SCHEMA_FILE).read()

def send_schema(cursor):
    for statement in get_schema().split(";"):
        statement = statement.strip()
        if len(statement):
            cursor.execute(statement)


def send_weblog(cursor, obj):
    """ Take a weblog agent and insert it into the digitalcorpora log file"""
    from weblog.weblog import Weblog
    assert isinstance(obj, Weblog)
    if obj.is_download():
        cursor.execute("INSERT INTO downloadable (s3key,bytes) VALUES (%s,%s) ON DUPLICATE KEY UPDATE bytes=bytes",
                       (obj.path, obj.bytes))
        cursor.execute("COMMIT")
        cursor.execute("INSERT INTO downloads (did, ipaddr, dtime) VALUES ((select id from downloadable where s3key=%s), %s, %s)",
                       (obj.path, obj.ipaddr, obj.dtime))
        cursor.execute("COMMIT")
