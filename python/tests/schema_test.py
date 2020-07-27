#!/usr/bin/env python3
"""
Make sure that the schema works.
"""
import pytest
import pymysql
import os

from weblog.weblog import Weblog

MINIMUM_MYSQL_VERSION = '5.7'

# For info on fixtures, see:
# https://docs.pytest.org/en/stable/fixture.html


@pytest.fixture
def db_connection():
    """Get a connection for the temporary database"""
    conn = pymysql.connect(host=os.environ['TMP_DBWRITER_HOSTNAME'],
                           database=os.environ['TMP_DBWRITER_DATABASE'],
                           user=os.environ['TMP_DBWRITER_USERNAME'],
                           password=os.environ['TMP_DBWRITER_PASSWORD'])
    yield conn
    conn.close()


def test_version(db_connection):
    """This tests verifies that MySQL has the minimum schema"""
    cursor = db_connection.cursor()
    cursor.execute('SELECT version();')
    rows = cursor.fetchall()
    assert len(rows) == 1
    assert rows[0][0] >= MINIMUM_MYSQL_VERSION


def test_schema():
    """Tests to make sure that the get_schema function works"""
    from weblog.schema import get_schema
    assert "CREATE TABLE" in get_schema()


def test_send_schema(db_connection):
    """This tests verifies that the schema is correctMySQL has the minimum schema"""
    from weblog.schema import send_schema
    cursor = db_connection.cursor()
    send_schema(cursor)

    # and verify that that each of the tables now have 0 entries
    for table in ['downloadable', 'downloads', 'tags', 'logfile']:
        cursor.execute(f"SELECT count(*) from {table}")
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 0


def test_weblog(db_connection):
    from weblog.schema import send_schema, send_weblog
    from tests.weblog_test import LINE4
    cursor = db_connection.cursor()
    send_schema(cursor)
    log4 = Weblog(LINE4)
    send_weblog(cursor, log4)
    cursor.execute("SELECT count(*) from downloadable")
    rows = cursor.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == 1

    cursor.execute("SELECT count(*) from downloads")
    rows = cursor.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == 1
