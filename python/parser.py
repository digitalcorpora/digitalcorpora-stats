#!/usr/bin/env python2

import re              
import parser
import os
try:
    import pytest
except ImportError as e:
    pass

with open('digital-corpora-access.log-20190616', 'r') as f:
    data = f.read()

class Weblog(object):
    __slots__ = ['ipaddr','timestamp','request','result','user','agent',
                 'referrer','url','date','time','datetime']
    clf_regex = '([(\d\.)]+) [^ ]+ [^ ]+ \[(.*)\] "(.*)" (\d+) [^ ]+ ("(.*)")? ("(.*)")?'
    clf_parser = re.compile(clf_regex)
    wikipage_pats = [re.compile(x) for x in ["index.php\?title=([^ &]*)", "/wiki/([^ &]*)"]]
    def __init__(self,line):
        m = self.clf_parser.match(line)
        if not m:
            raise ValueError("invalid logfile line: "+line)
        self.ipaddr = m.group(1)
        self.timestamp = m.group(2)
        self.request = m.group(3)
        self.result = int(m.group(4))
        self.user = m.group(5)
        self.referrer = m.group(6) 
        self.agent = m.group(7)
        if self.agent:
            self.agent = self.agent.replace('"','')
        request_fields = self.request.split(" ")
        self.url = request_fields[1] if len(request_fields)>2 else ""
        self.datetime = parser.parse(self.timestamp.replace(":", " ", 1)).isoformat()
        self.date = self.datetime[0:10]
        self.time = self.datetime[11:]

    def wikipage(self):
        for r in self.wikipage_pats:
            m = r.search(self.url)
            if m: return m.group(1)
        return None
        

# test parser.py
def testcase1():
   assert weblog('129.174.125.204 - - [09/Jun/2019:03:18:23 -0400] "GET /downloads/ HTTP/1.1" 200 3340 "-" "portscout/0.8.1"') == '129.174.125.204 - June 09 2019 - 3:18:23 - downloads/http/1.1'
	pass
():
      def testcase2():
         with pytest.raises(TypeError):
       weblog('[06/Jul/2019:02:55:57 -0400] - - 10.173.0.42 - - "GET /netmri/config/userAdmin/login.tdf HTTP/1.1" 500 633')
		pass
	  
	pass

if __name__=="__main__":
   a = Weblog(data)
   print("url: %s  date: %s  time: %s  datetime: %s" % (a.url,a.date,a.time,a.datetime))
   Weblog(data).wikipage()