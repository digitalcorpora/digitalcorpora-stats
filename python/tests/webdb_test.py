import weblog
import pymysql
import os
# from datetime import date, datetime, timedelta
# from genson import SchemaBuilder

connection = pymysql.connect(
    host='TMP_DBWRITER_HOSTNAME',
    db='TMP_DBWRITER_DATABASE',
    user='TMP_DBWRITER_USERNAME',
    password='TMP_DBWRITER_PASSWORD',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)

try:
    with connection.cursor() as cursor:
        cursor.execute("CREATE TABLE testTable")
        sql = ("INSERT INTO testTable "
               "(ipaddr, ident, user, datetime, request, result, size) "
               "VALUES (%s, %s, %s, %s, %s, %s, %s)")
        cursor.execute(sql, (weblog.parser))
        # Ensure data is committed to database
    connection.commit()

finally:
    connection.close()
