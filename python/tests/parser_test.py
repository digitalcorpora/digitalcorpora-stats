import pytest
import dateutil.tz
import datetime        

import weblog 

LINE1='77.88.5.184 - - [21/Jun/2020:10:25:05 -0700] "GET / HTTP/1.1" 401 4110 "-" "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"'

def test_line1():
    log = weblog.Weblog(LINE1)
    assert log.ipaddr=='77.88.5.184'
    assert log.datetime.year==2020
    assert log.datetime.month==6
    assert log.datetime.day==21
    assert log.method=='GET'
    assert log.url=='/'
    assert log.result==401
    assert log.size==4110
    assert log.referrer=='-'
    assert log.agent=="Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"
    
