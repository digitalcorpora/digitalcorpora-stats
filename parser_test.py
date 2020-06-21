import weblog

LINE1 = '77.88.5.184 - - [21/Jun/2020:10:25:05 -0700] "GET / HTTP/1.1" 401 4110 "-" "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"'
LINE2 = '129.174.125.204 - - [16/Jun/2019:05:18:15 -0400] "GET /downloads/tcpflow/ HTTP/1.1" 200 971 "-" "Anitya 0.15.1 at release-monitoring.org"'
LINE3 = '129.174.125.204 - - [16/Jun/2019:09:06:56 -0400] "GET /corpora/scenarios/2009-m57-patents/ HTTP/1.1" 200 3812 "http://downloads.digitalcorpora.org/corpora/scenarios/2009-m57-patents/drives-redacted/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36"

def test_line1():
    log = weblog.Weblog(LINE1)
    assert log.ipaddr == '77.88.5.184'
    assert log.datetime.year == 2020
    assert log.datetime.month == 6
    assert log.datetime.day == 21
    assert log.method == 'GET'
    assert log.url == '/'
    assert log.result == 401
    assert log.size == 4110
    assert log.referrer == '-'
    assert log.agent == "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)"

def test_line2():
    log = weblog.Weblog(LINE2)
    assert log.ipaddr == '129.174.125.204'
    assert log.datetime.year == 2019
    assert log.datetime.month == 6
    assert log.datetime.day == 16
    assert log.method == 'GET'
    assert log.url == '/downloads/tcpflow/'
    assert log.result == 200
    assert log.size == 971
    assert log.referrer == '-'
    assert log.agent == "Anitya 0.15.1 at release-monitoring.org"

def test_line3():
    log = weblog.Weblog(LINE3)
    assert log.ipaddr == '129.174.125.204'
    assert log.datetime.year == 2019
    assert log.datetime.month == 6
    assert log.datetime.day == 16
    assert log.method == 'GET'
    assert log.url == '/corpora/scenarios/2009-m57-patents/'
    assert log.result == 200
    assert log.size == 3812
    assert log.referrer == 'http://downloads.digitalcorpora.org/corpora/scenarios/2009-m57-patents/drives-redacted/'
    assert log.agent == "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36"
