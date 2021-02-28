#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
The Weblog object parses a log line and returns the weblog object.
"""

import re
import dateutil.parser
from urllib.parse import urlparse


class Weblog(object):
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
        self.dtime  = dateutil.parser.parse(m.group(4).replace(':', ' ', 1))
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
