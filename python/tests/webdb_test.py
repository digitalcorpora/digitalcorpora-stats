import sys
import os
import pymysql
import pytest

import weblog
import datetime
# from genson import SchemaBuilder

@pytest.fixture
def db_connection():
    conn = pymysql.connect(host=os.environ['TMP_DBWRITER_HOSTNAME'],
                           database=os.environ['TMP_DBWRITER_DATABASE'],
                           user=os.environ['TMP_DBWRITER_USERNAME'],
                           password=os.environ['TMP_DBWRITER_PASSWORD'])
    yield conn
    conn.close()

def test_insert(db_connection):
    cursor = db_connection.cursor() 

    # First send the schema

    sql = """
    INSERT INTO testTable (ipaddr, ident, user, datetime, request, result, size) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(sql, ("1.1.1.1","test-ident", "test-user", datetime.datetime.now(), "request-1", 400, 10))
    # Ensure data is committed to database
    db_connection.commit()
    db_connection.close()
