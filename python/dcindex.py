#!/usr/bin/env python3
"""
DigitalCorpora index tool. Stores index in dynamodb.
# https://dynobase.dev/dynamodb-python-with-boto3/
# https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/programming-with-python.html
"""

import boto3
import hashlib
from boto3.dynamodb.conditions import Key

dcobjects = boto3.resource('dynamodb').Table('DigitalCorporaObjects')


def list_tables():
    dynamodb = boto3.resource('dynamodb')
    tables = list(dynamodb.tables.all())
    print("tables:",tables)

def put_object(obj):
    dcobjects.put_item( Item=obj )

def empty_object():
    h = hashlib.sha256()
    h.update(b"")
    return {'sha256':h.hexdigest(),
            'notes':'The empty object'}

def scan_table():
    params = {}
    while True:
        response = dcobjects.scan(**params)
        for item in response['Items']:
            print(item)
        if 'LastEvaluatedKey' not in response:
            break
        query_params['ExclusiveStartKey'] = response['LastEvaluatedKey']

if __name__=="__main__":
    list_tables()
    put_object(empty_object())
    scan_table()
