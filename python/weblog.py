#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import dateutil.parser


class Weblog(object):
    """Class that parses an Apache Combined Log File format file and returns tuple.
    See https://httpd.apache.org/docs/2.4/logs.html for log file format
    """
    __slots__  = ['ipaddr', 'ident', 'user', 'datetime', 'request', 'result',
                  'size', 'agent', 'referrer', 'method', 'url']
    CLF_REGEX  = r'([(\d\.)]+) ([^ ]+) ([^ ]+) \[(.*)\] "(.*)" (\d+) (\d+)( "[^"]*")?( "[^"]*")?'
    CLF_RE     = re.compile(CLF_REGEX)
    WIKIPAGE_PATS = [re.compile(x) for x in [r"index.php\?title=([^ &]*)", "/wiki/([^ &]*)"]]

    def __init__(self, line):
        """Parse a line."""
        m = self.CLF_RE.match(line)
        if not m:
            raise ValueError("invalid logfile line: " + line)
        self.ipaddr    = m.group(1)
        self.ident     = m.group(2)
        self.user      = m.group(3)
        self.datetime  = dateutil.parser.parse(m.group(4).replace(':', ' ', 1))
        self.request   = m.group(5)
        self.result    = int(m.group(6))
        self.size      = int(m.group(7))
        try:
            self.referrer  = m.group(8)[2:-1]  # remove the space and quotes
        except IndexError:
            self.referrer  = None
        try:
            self.agent     = m.group(9)[2:-1]  # remove the quotes
        except IndexError:
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