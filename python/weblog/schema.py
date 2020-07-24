#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Return the schema in ../schema.sql

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
