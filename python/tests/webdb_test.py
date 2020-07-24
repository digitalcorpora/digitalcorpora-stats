import sys
import os
import pymysql
import pytest

import weblog
import datetime

#
# this test takes a sample weblog, parses it and writes to the databse
#

@pytest.fixture
def db_connection():
    conn = pymysql.connect(host=os.environ['TMP_DBWRITER_HOSTNAME'],
                           database=os.environ['TMP_DBWRITER_DATABASE'],
                           user=os.environ['TMP_DBWRITER_USERNAME'],
                           password=os.environ['TMP_DBWRITER_PASSWORD'])
    yield conn
    conn.close()

