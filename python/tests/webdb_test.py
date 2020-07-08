import weblog
import pymysql
from datetime import date, datetime, timedelta
from genson import SchemaBuilder

connection = pymysql.connect(
    host='127.0.0.1',
    user='test',
    password='testtest123',
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
