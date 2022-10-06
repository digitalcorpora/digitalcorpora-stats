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
