import os
import pymysql
import pytest

#
# this test takes a sample weblog, parses it and writes to the databse
#

from tests.schema_test import db_connection
import tests.weblog_test as weblog_test

def test_weblog(db_connection):
    from weblog.schema import send_schema
    cursor = db_connection.cursor()
    send_schema(cursor)

    # 
