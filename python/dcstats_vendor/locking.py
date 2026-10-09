# This module provides the one-process lock used by dclogtool command invocations.
# It opens the executing script and holds a non-blocking advisory flock for process life.
# A second invocation therefore fails immediately rather than writing the same log objects.
# The ingestion command can opt out with --nolock only for deliberately partitioned runs.
# It has no dependency on the removed ctools submodule.

import fcntl
import os
import sys


def lock_script(lockfile=sys.argv[0]):
    """Acquire and retain a non-blocking exclusive lock on the script file."""
    try:
        descriptor = os.open(lockfile, os.O_RDONLY)
    except FileNotFoundError as error:
        raise FileNotFoundError(f"could not find script at {lockfile}") from error
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        os.close(descriptor)
        raise RuntimeError(f"could not acquire lock on {lockfile}") from error
    return descriptor
