# This module is the small MySQL helper required by the DigitalCorpora stats worker.
# It owns database credentials and gives each worker thread its own cached connection.
# DBMySQL.csfr executes simple one-statement operations for maintenance paths.
# Ingestion uses DBMySQL directly when a download batch must share a transaction.
# Connections use PyMySQL autocommit by default; callers explicitly begin atomic batches.

import copy
import logging
import os
import threading

import pymysql


class DBMySQLAuth:
    """Credential and per-thread connection cache for one MySQL database."""

    def __init__(self, *, host, database, user, password, prefix="", debug=False):
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.prefix = prefix
        self.debug = debug
        self.dbcache = {}

    def __deepcopy__(self, memo):
        return type(self)(host=self.host, database=self.database, user=self.user,
                          password=self.password, prefix=self.prefix, debug=self.debug)

    def __repr__(self):
        return f"<DBMySQLAuth:{self.host}:{self.database}:{self.user}:*****:{self.prefix}>"

    def cache_store(self, db):
        self.dbcache[(os.getpid(), threading.get_ident())] = db

    def cache_get(self):
        return self.dbcache[(os.getpid(), threading.get_ident())]

    def cache_clear(self):
        self.dbcache.pop((os.getpid(), threading.get_ident()), None)


class DBMySQL:
    """A PyMySQL connection plus the legacy csfr convenience operation."""

    def __init__(self, auth):
        self.auth = auth
        self.conn = pymysql.connect(host=auth.host, database=auth.database,
                                    user=auth.user, password=auth.password,
                                    autocommit=True)

    def cursor(self, *args, **kwargs):
        return self.conn.cursor(*args, **kwargs)

    def close(self):
        self.conn.close()

    def create_schema(self, schema):
        with self.conn.cursor() as cursor:
            for statement in schema.split(";"):
                if statement.strip():
                    cursor.execute(statement)

    @staticmethod
    def csfr(auth, cmd, vals=None, *, quiet=True, rowcount=None, time_zone=None,
             setup=None, setup_vals=(), get_column_names=None, asDicts=False,
             debug=False, dry_run=False, cache=True, nolog=(), ignore=()):
        """Connect, execute one statement, fetch its rows, and validate rowcount."""
        del quiet, cache
        if dry_run:
            logging.warning("would execute: %s", cmd)
            return None
        try:
            db = auth.cache_get()
        except KeyError:
            db = DBMySQL(auth)
            auth.cache_store(db)
        try:
            with db.cursor() as cursor:
                cursor.execute("SET autocommit=1")
                if time_zone is not None:
                    cursor.execute("SET @@session.time_zone = %s", (time_zone,))
                if setup is not None:
                    cursor.execute(setup, setup_vals)
                cursor.execute(cmd, vals)
                if rowcount is not None and cursor.rowcount != rowcount:
                    raise RuntimeError(f"expected rowcount={rowcount}, got {cursor.rowcount}: {cmd}")
                verb = cmd.lstrip().split(maxsplit=1)[0].upper()
                if verb in {"SELECT", "DESCRIBE", "SHOW"}:
                    rows = cursor.fetchall()
                    if get_column_names is not None:
                        get_column_names[:] = [column[0] for column in cursor.description]
                    if asDicts:
                        return [dict(zip(get_column_names, row)) for row in rows]
                    return rows
                if verb == "INSERT":
                    return cursor.lastrowid
                if verb == "UPDATE":
                    return cursor.rowcount
                return None
        except pymysql.MySQLError as error:
            code = error.args[0] if error.args else None
            if code in ignore:
                return "IGNORED"
            if code not in nolog:
                logging.error("MySQL %s executing %s", code, cmd)
            raise
