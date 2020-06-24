import weblog
import mysql.connector
from datetime import date, datetime, timedelta
import credlib
test = mysql.connector.connect(
    host=credlib.hostname,
    user=credlib.username,
    password=credlib.password,
    database='test',)
testcursor = test.cursor()

table_create = """CREATE TABLE testTable (
ipaddr varchar(250) NOT NULL,
ident varchar(250) NOT NULL,
user varchar(250) NOT NULL,
datetime Date NOT NULL,
request int(4) NOT NULL,
result int(4) NOT NULL,
size int(6) NOT NULL,)"""

goal = testcursor.execute(table_create)
print("table created")
#parse log
parse_log = ("INSERT INTO testTable "
"(ipaddr, ident, user, datetime, request, result, size) "
"VALUES (%s, %s, %s, %s, %s, %s, %s)")
#Ensure data is committed to database

test.commit()

testcursor.close()

test.close()
