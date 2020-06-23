import weblog
import mysql.connector
from datetime import date, datetime, timedelta

testdb = mysql.connector.connect(
host="test"
user=(config['webdb']['username'])
password=(config['smtp']['password'])
)

testcursor = testdb.cursor

testcursor.execute("CREATE TABLE testTable")

#parse log
parse_log = ("INSERT INTO testTable "
            "(ipaddr, ident, user, datetime, request, result, size) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)")

#Ensure data is committed to database
testdb.commit()

testcursor.close()
testdb.close()
