from weblog.weblog import Weblog,S3Log,REST_GET_OBJECT

import pytest
import datetime
from dateutil.tz import tzutc

"""
This tests the ability of the weblog parser to parse three log lines
"""

LINE1 = '77.88.5.184 - - [21/Jun/2020:10:25:05 -0700] "GET / HTTP/1.1" 401 4110 "-" "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"'
LINE2 = '129.174.125.204 - - [16/Jun/2019:05:18:15 -0400] "GET /downloads/tcpflow/ HTTP/1.1" 200 971 "-" "Anitya 0.15.1 at release-monitoring.org"'
LINE3 = '129.174.125.204 - - [16/Jun/2019:09:06:56 -0400] "GET /corpora/scenarios/2009-m57-patents/ HTTP/1.1" 200 3812 "http://downloads.digitalcorpora.org/corpora/scenarios/2009-m57-patents/drives-redacted/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36"'
LINE4 = '129.174.125.204 - - [16/Jun/2019:05:18:15 -0400] "GET /downloads/tcpflow/tcpflow-1.5.0.tar.gz  HTTP/1.1" 200 460000 "-" "Anitya 0.15.1 at release-monitoring.org"'
LINE5 = '129.174.125.204 - - [16/Jun/2019:09:06:56 -0400] "GET /corpora/drives/nps-2009-patents/drives-redacted/charlie-2009-11-23.E01 HTTP/1.1" 200 4294967296 3812 "http://downloads.digitalcorpora.org/corpora/scenarios/2009-m57-patents/drives-redacted/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36"'
LINE6 = '54.164.96.238 - - [26/Jul/2020:04:13:28 -0400] "HEAD /corpora/files/govdocs1/dump.sql HTTP/1.1" 200 - "-" "Blackboard Safeassign"'
LINE7 = '::1 - - [05/Jul/2020:09:16:44 -0400] "OPTIONS * HTTP/1.0" 200 - "-" "Apache/2.2.15 (CentOS) (internal dummy connection)"'

# And these S3 Logs
S3LOG_LINE1 = '938c42948af97101ff5ecad73349fb9034d92563dede79b306da5fb954759e8b digitalcorpora [19/Feb/2021:18:24:07 +0000] 40.77.139.20 - F16A8299960278B3 REST.GET.OBJECT corpora/scenarios/2012-ngdc/extra/carry-phone-ftk/carry-phone-FTK-2012-07-03.E01 "GET /corpora/scenarios/2012-ngdc/extra/carry-phone-ftk/carry-phone-FTK-2012-07-03.E01 HTTP/1.1" 200 - 12521156 26418161 160 64 "-" "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/534+ (KHTML, like Gecko) BingPreview/1.0b" - U4rMJ58HycslBqLub15OHzBN4bgOeuZJyYKhWIZ7LdRHKQfjxqkA6833llVumhIGJxuKVax0YJ8= - ECDHE-RSA-AES128-GCM-SHA256 - digitalcorpora.s3.amazonaws.com TLSv1.2'

S3LOG_LINE2 = '938c42948af97101ff5ecad73349fb9034d92563dede79b306da5fb954759e8b digitalcorpora [14/Feb/2021:00:51:53 +0000] 157.55.39.153 - 798EA806306853BF REST.GET.OBJECT corpora/scenarios/2009-m57-patents/usb/jo-work-usb-2009-12-11.E01 "GET /corpora/scenarios/2009-m57-patents/usb/jo-work-usb-2009-12-11.E01 HTTP/1.1" 200 - 81729092 118233120 12806 104 "-" "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)" - sDSg7Y8mY9c2syoqd0vYesT5PO0KFIooP8mpABPvto4FMKX5r+5/oM9wob1uf1vB91IppAf4+ic= - ECDHE-RSA-AES128-GCM-SHA256 - digitalcorpora.s3.amazonaws.com TLSv1.2'


def test_line1():
    log = Weblog(LINE1)
    assert log.ipaddr == '77.88.5.184'
    assert log.dtime.year == 2020
    assert log.dtime.month == 6
    assert log.dtime.day == 21
    assert log.method == 'GET'
    assert log.url == '/'
    assert log.result == 401
    assert log.bytes == 4110
    assert log.referrer == '-'
    assert log.agent == "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"
    assert log.is_download() is False


def test_line2():
    log = Weblog(LINE2)
    assert log.ipaddr == '129.174.125.204'
    assert log.dtime.year == 2019
    assert log.dtime.month == 6
    assert log.dtime.day == 16
    assert log.method == 'GET'
    assert log.url == '/downloads/tcpflow/'
    assert log.result == 200
    assert log.bytes == 971
    assert log.referrer == '-'
    assert log.agent == "Anitya 0.15.1 at release-monitoring.org"
    assert log.is_download() is False


def test_line3():
    log = Weblog(LINE3)
    assert log.ipaddr == '129.174.125.204'
    assert log.dtime.year == 2019
    assert log.dtime.month == 6
    assert log.dtime.day == 16
    assert log.method == 'GET'
    assert log.url == '/corpora/scenarios/2009-m57-patents/'
    assert log.result == 200
    assert log.bytes == 3812
    assert log.referrer == 'http://downloads.digitalcorpora.org/corpora/scenarios/2009-m57-patents/drives-redacted/'
    assert log.agent == "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36"
    assert log.is_download() is False


def test_extra():
    log4 = Weblog(LINE4)
    assert log4.is_download()
    assert log4.path == '/downloads/tcpflow/tcpflow-1.5.0.tar.gz'

    log5 = Weblog(LINE5)
    assert log5.is_download()

    log6 = Weblog(LINE6)
    assert log6.is_download() is False

    log7 = Weblog(LINE7)
    assert log7.is_download() is False

def test_s3log():
    s1 = S3Log(S3LOG_LINE1)
    assert s1.bucket_owner == '938c42948af97101ff5ecad73349fb9034d92563dede79b306da5fb954759e8b'
    assert s1.bucket       == 'digitalcorpora'
    assert s1.time         == datetime.datetime(2021,2,19,18,24,7,tzinfo=tzutc())
    assert s1.remote_ip    == '40.77.139.20'
    assert s1.operation    == REST_GET_OBJECT
    assert s1.key          == 'corpora/scenarios/2012-ngdc/extra/carry-phone-ftk/carry-phone-FTK-2012-07-03.E01'
    assert s1.bytes_sent   == 12521156
    assert s1.object_size  == 26418161
    assert s1.user_agent   == 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/534+ (KHTML, like Gecko) BingPreview/1.0b'
