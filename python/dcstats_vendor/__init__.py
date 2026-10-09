# This package contains the small, first-party runtime helpers used by dclogtool.
# It replaces the former ctools Git submodule with code deployed in this repository.
# The helpers cover MySQL connection handling, command-line logging, and process locks.
# Keeping them here makes a plain Git checkout self-contained on DreamHost and elsewhere.
# No other ctools modules are imported by the statistics worker.
