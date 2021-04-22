import weblog.weblog

BAD_DATE = '02/Nov/2019:10:55:30 -0400] "GET /corpora/drives/ H129.174.125.204'

def test_clean_date():
    assert weblog.weblog.clean_date(BAD_DATE)=='02/Nov/2019 10:55:30 -0400'
