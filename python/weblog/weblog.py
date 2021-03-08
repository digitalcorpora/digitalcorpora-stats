#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
The Weblog object parses a log line and returns the weblog object.

S3Log is a sublcass which can do S3logs.

"""

import re
import dateutil.parser
from urllib.parse import urlparse

REST_GET_OBJECT='REST.GET.OBJECT'

class Weblog:
    """Class that parses an Apache Combined Log File format file and returns tuple.
    See https://httpd.apache.org/docs/2.4/logs.html for log file format
    """
    __slots__  = ['ipaddr', 'ident', 'user', 'dtime', 'request', 'result',
                  'bytes', 'agent', 'referrer', 'method', 'url']
    CLF_REGEX  = r'([(\d\.):]+) ([^ ]+) ([^ ]+) \[(.*)\] "(.*)" (\d+) (\d+|-)( "[^"]*")?( "[^"]*")?'
    CLF_RE     = re.compile(CLF_REGEX)
    WIKIPAGE_PATS = [re.compile(x) for x in [r"index.php\?title=([^ &]*)", "/wiki/([^ &]*)"]]
    DL_PAT     = re.compile(r"(.*)[.](gz|E\d\d|csv|dd|raw|iso)$", re.I)

    def __init__(self, line):
        """Parse a line."""
        m = self.CLF_RE.match(line)
        if not m:
            raise ValueError("invalid logfile line: " + line)
        self.ipaddr    = m.group(1)
        self.ident     = m.group(2)
        self.user      = m.group(3)
        self.dtime     = dateutil.parser.parse(m.group(4).replace(':', ' ', 1))
        self.request   = m.group(5)
        self.result    = int(m.group(6))
        try:
            self.bytes  = int(m.group(7))
        except ValueError:
            self.bytes  = None
        try:
            self.referrer  = m.group(8)[2:-1]  # remove the space and quotes
        except (IndexError, TypeError):
            self.referrer  = None
        try:
            self.agent     = m.group(9)[2:-1]  # remove the quotes
        except (IndexError, TypeError):
            self.agent    = None

        # Now compute the derrived fields
        request_fields = self.request.split(" ")
        self.method = request_fields[0]
        try:
            self.url    = request_fields[1]
        except IndexError:
            self.url    = None

    def wikipage(self):
        """Returns the wikipage referenced, or None"""
        for r in self.WIKIPAGE_PATS:
            m = r.search(self.url)
            if m:
                return m.group(1)
        return None

    @property
    def path(self):
        o = urlparse(self.url)
        return o.path

    def is_download(self):
        """Returns true if the weblog represents a download"""
        if self.url is None:
            return False
        m = self.DL_PAT.search(self.url)
        return m is not None

class S3Log:
    """Class that decodes S3Logs.
    From https://docs.aws.amazon.com/AmazonS3/latest/userguide/LogFormat.html
    We don't decode the all the fields.
    """
    __slots__ = ['bucket_owner','bucket', 'time', 'remote_ip', 'requester', 'request_id',
                 'operation', 'key', 'request_uri', 'http_status', 'error_code', 'bytes_sent', 'object_size',
                 'total_time', 'turn_around_time', 'referer', 'user_agent', 'version_id',
                 'host_id', 'signature_version',
                 'cipher_suite', 'authentication_type', 'host_header', 'tls_version']
    # https://stackoverflow.com/questions/7961316/regex-to-split-columns-of-an-amazon-s3-bucket-log
    S3_REGEX  = r'(?:"([^"]+)")|(?:\[([^\]]+)\])|([^ ]+)'
    S3_RE     = re.compile(S3_REGEX)

    """
    Example output:
0 ('', '', '938c42948af97101ff5ecad73349fb9034d92563dede79b306da5fb954759e8b')
1 ('', '', 'digitalcorpora')
2 ('', '19/Feb/2021:18:24:07 +0000', '')
3 ('', '', '40.77.139.20')
4 ('', '', '-')
5 ('', '', 'F16A8299960278B3')
6 ('', '', 'REST.GET.OBJECT')
7 ('', '', 'corpora/scenarios/2012-ngdc/extra/carry-phone-ftk/carry-phone-FTK-2012-07-03.E01')
8 ('GET /corpora/scenarios/2012-ngdc/extra/carry-phone-ftk/carry-phone-FTK-2012-07-03.E01 HTTP/1.1', '', '')
9 ('', '', '200')
10 ('', '', '-')
11 ('', '', '12521156')
12 ('', '', '26418161')
13 ('', '', '160')
14 ('', '', '64')
15 ('-', '', '')
16 ('Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/534+ (KHTML, like Gecko) BingPreview/1.0b', '', '')
17 ('', '', '-')
18 ('', '', 'U4rMJ58HycslBqLub15OHzBN4bgOeuZJyYKhWIZ7LdRHKQfjxqkA6833llVumhIGJxuKVax0YJ8=')
19 ('', '', '-')
20 ('', '', 'ECDHE-RSA-AES128-GCM-SHA256')
21 ('', '', '-')
22 ('', '', 'digitalcorpora.s3.amazonaws.com')
23 ('', '', 'TLSv1.2')
    """

    def __init__(self, line):
        parts = self.S3_RE.findall(line)
        self.bucket_owner = parts[0][2]
        self.bucket       = parts[1][2]
        self.time         = dateutil.parser.parse(parts[2][1].replace(":"," ",1))
        self.remote_ip    = parts[3][2]
        self.operation    = parts[6][2]
        self.key          = parts[7][2]
        self.bytes_sent   = int(parts[11][2])
        self.object_size  = int(parts[12][2])
        self.user_agent   = parts[16][0]
