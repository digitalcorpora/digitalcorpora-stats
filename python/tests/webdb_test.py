import weblog
import pymysql
import os
from datetime import date, datetime
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
        sql = ("INSERT INTO testTable "
               "(ipaddr, ident, user, datetime, request, result, size) "
               "VALUES (%s, %s, %s, %s, %s, %s, %s)")
        cursor.execute(sql, (weblog.parser))
        # Ensure data is committed to database
    connection.commit()

finally:
    connection.close()


# builderA = SchemaBuilder()
# builderA.add_schema({"type": "object", "properties": {}})
# builderA.add_object({"hi": "there"})
# builderA.add_object({"hi": 5})

# builderA.to_schema()
# {'$schema': "$linktoschema",
 # "type": "object",
 # "properties": {
#     "hi": {
    #     "type": [
    #        "integer",
    #        "string"
    #     ]
#     }
 # },
#    "required": [
#    "hi"
 # ]
 # }
