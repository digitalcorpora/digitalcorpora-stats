#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Routines for managing the databse schema. 
- getting the schema file 
- sending it into the datase
- sending a weblog object into the database in a single transaction.
"""

import os
import weblog

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
    assert isinstance(obj, weblog.Weblog)
    
