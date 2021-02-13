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
        path = obj.path
        prefix  = os.path.dirname(path)
        basename = os.path.basename(path)
        cursor.execute("INSERT INTO downloadable (prefix,basename,size) VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE size=size",
                       (prefix, os.path.basename(path), obj.size))
        cursor.execute("COMMIT")
        cursor.execute("INSERT INTO downloads (did, ipaddr, dtime) VALUES ((select id from downloadable where prefix=%s and basename=%s), %s, %s)",
                       (prefix, basename, obj.ipaddr, obj.dtime))
        cursor.execute("COMMIT")
