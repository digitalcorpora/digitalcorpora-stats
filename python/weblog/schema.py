#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Routines for managing the databse schema.
- getting the schema file
- sending it into the datase
- sending a weblog object into the database in a single transaction.
"""

import os

SCHEMA_FILE = "../schema.sql"


def get_schema():
    with open(os.path.abspath(os.path.join(os.path.dirname(__file__), SCHEMA_FILE))) as f:
        return f.read()


def send_schema(cursor):
    for statement in get_schema().split(";"):
        statement = statement.strip()
        if len(statement):
            cursor.execute(statement)


def send_weblog(cursor, obj):
    from weblog.weblog import Weblog
    assert isinstance(obj, Weblog)
    """ If this is a downloadable request, make sure that the download exists in the dowloadable table, then add it to the download downloads table"""
    if obj.is_download():
        path = obj.path
        dirname  = os.path.dirname(path)
        basename = os.path.basename(path)
        cursor.execute("INSERT INTO downloadable (dirname,basename,size) VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE size=size",
                       (dirname, os.path.basename(path), obj.size))
        cursor.execute("COMMIT")
        cursor.execute("INSERT INTO downloads (did, ipaddr, dtime, request, user, referrer, agent) VALUES ((select id from downloadable where dirname=%s and basename=%s),%s,%s,%s,%s,%s,%s)",
                       (dirname, basename, obj.ipaddr, obj.dtime, obj.request, obj.user, obj.referrer, obj.agent))
        cursor.execute("COMMIT")
