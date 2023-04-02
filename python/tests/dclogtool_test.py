#!/usr/bin/env python3
"""
Test individual functions in dclogtool.
"""

import os
import sys
import urllib

from os.path import abspath,dirname,basename
sys.path.append( dirname(dirname( abspath( __file__ ))))

import datetime
from dateutil.tz import tzutc
import pytest
import dclogtool

S3TEST_URL = 's3://digitalcorpora/tests/'

"""
These are the objects that were present on Oct. 15, 2023:
"""
S3TEST_OBJS = [
    {'Key': 'tests/file1.txt', 'LastModified': datetime.datetime(2021, 2, 1, 22, 40, 1, tzinfo=tzutc()), 'ETag': '"ab9d88bdde67485fda0b926b278823cd"', 'Size': 15, 'StorageClass': 'STANDARD'},
    {'Key': 'tests/file2.txt', 'LastModified': datetime.datetime(2021, 2, 1, 22, 40, 9, tzinfo=tzutc()), 'ETag': '"31ecb003dd40f89f4281e3e19a817960"', 'Size': 15, 'StorageClass': 'STANDARD'},
    {'Key': 'tests/hello_world.txt', 'LastModified': datetime.datetime(2022, 1, 16, 14, 23, 31, tzinfo=tzutc()), 'ETag': '"59ca0efa9f5633cb0371bbc0355478d8"', 'Size': 13, 'StorageClass': 'STANDARD'},
    {'Key': 'tests/subdir with-space/file4.txt', 'LastModified': datetime.datetime(2021, 2, 1, 23, 35, 20, tzinfo=tzutc()), 'ETag': '"1e0a9234edd9cf9b0676578d1f7f8b8a"', 'Size': 15, 'StorageClass': 'STANDARD'},
    {'Key': 'tests/subdir1/file3.txt', 'LastModified': datetime.datetime(2021, 2, 1, 22, 40, 23, tzinfo=tzutc()), 'ETag': '"1f43315a764f970a988b31cb6454e476"', 'Size': 15, 'StorageClass': 'STANDARD'}
]

def test_s3_get_objects():
    # Take the test objects and make them findable by key
    objs = { obj['Key']:obj for obj in S3TEST_OBJS}

    found = 0
    for obj in dclogtool.s3_get_objects( url = S3TEST_URL):
        key = obj['Key']
        if key in objs:
            assert objs[key] == obj
            found += 1
        else:
            print("New object:",obj)
    # make sure we found at least two objects
    assert found > 2
