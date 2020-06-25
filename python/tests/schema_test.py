#!/usr/bin/env python3
"""
Make sure that the schema works.
"""


import pytest
import pymysql
import os

MINIMUM_MYSQL_VERSION = '5.7'

# For info on fixtures, see:
# https://docs.pytest.org/en/stable/fixture.html


@pytest.fixture
def db_connection():
    conn = pymysql.connect(host=os.environ['TMP_DBWRITER_HOSTNAME'],
                           database=os.environ['TMP_DBWRITER_DATABASE'],
                           user=os.environ['TMP_DBWRITER_USERNAME'],
                           password=os.environ['TMP_DBWRITER_PASSWORD'])
    yield conn
    conn.close()


def test_version(db_connection):
    cursor = db_connection.cursor()
    cursor.execute('SELECT version();')
    rows = cursor.fetchall()
    assert len(rows) == 1
    assert rows[0][0] >= MINIMUM_MYSQL_VERSION
