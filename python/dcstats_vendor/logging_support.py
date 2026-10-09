# This module configures command-line logging for the DigitalCorpora stats worker.
# It exposes the legacy argument names used by dclogtool without an external module.
# setup() is idempotent so tests and repeated entry-point calls remain safe.
# The worker directs normal progress to stderr or its supervisor's log file.
# Syslog integration is intentionally omitted because this deployment does not use it.

import logging


LOG_FORMAT = "%(asctime)s %(filename)s:%(lineno)d (%(funcName)s) %(message)s"
_configured = False


def add_argument(parser, *, loglevel_default="INFO"):
    """Add the logging options consumed by dclogtool."""
    parser.add_argument("--loglevel", choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
                        default=loglevel_default, help="Set logging level")
    parser.add_argument("--logfilename", help="Output filename for logfile")


def setup(level="INFO", *, filename=None, log_format=LOG_FORMAT, **unused):
    """Configure root logging once, while honoring a stricter later level."""
    del unused
    global _configured
    numeric_level = level if isinstance(level, int) else logging.getLevelName(level)
    root = logging.getLogger()
    if not _configured:
        if root.hasHandlers():
            root.setLevel(numeric_level)
        else:
            logging.basicConfig(filename=filename, format=log_format, level=numeric_level)
        _configured = True
    elif numeric_level < root.getEffectiveLevel():
        root.setLevel(numeric_level)
