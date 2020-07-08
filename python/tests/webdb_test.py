import weblog
import pymysql
import os
from datetime import date, datetime, timedelta
# from genson import SchemaBuilder

connection = pymysql.connect(
    host=os.environ['TMP_DBWRITER_HOSTNAME'],
    database=os.environ['TMP_DBWRITER_DATABASE'],
    user=os.environ['TMP_DBWRITER_USERNAME'],
    password=os.environ['TMP_DBWRITER_PASSWORD'],
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)

try:
    with connection.cursor() as cursor:
        cursor.execute("CREATE TABLE 'testTable' (
    `ipaddr` int(11) NOT NULL AUTO_INCREMENT,
    `ident` varchar(255) COLLATE utf8_bin NOT NULL,
    `user` varchar(255) COLLATE utf8_bin NOT NULL,
    `datetime` datetime,
    `request` int(11) NOT NULL,
    `result` int(11) NOT NULL,
    `size` int(11) NOT NULL,
    PRIMARY KEY (`user`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin
AUTO_INCREMENT=1 ;
        )
        sql = ("INSERT INTO testTable "
               "(ipaddr, ident, user, datetime, request, result, size) "
               "VALUES (%s, %s, %s, %s, %s, %s, %s)")
        cursor.execute(sql, (weblog.parser))
        # Ensure data is committed to database
    connection.commit()

finally:
    connection.close()
