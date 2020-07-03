import weblog
import mysql.connector
from datetime import date, datetime, timedelta
from genson import SchemaBuilder

testdb = mysql.connector.connect(
    host="127.0.0.1",
    user="test",
    password="testtest123",
)

cursor = testdb.cursor

# cursor.execute("CREATE TABLE testTable")

# parse log
parse_log = ("INSERT INTO testTable "
            "(ipaddr, ident, user, datetime, request, result, size) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)")

# Ensure data is committed to database
testdb.commit()

# cursor.close()
testdb.close()


builder = SchemaBuilder()
builder.add_schema({"type": "object", "properties":{}})
builder.add_object({"hi": "there"})
builder.add_object({"hi": 5})

builder.to_schema()
{'$schema': "$linktoschema",
"type": "object",
"properties": {
    "hi": {
    "type": [
    "integer",
    "string"
]
}
},
    "required": [
    "hi"
]
}
