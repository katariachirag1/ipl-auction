"""Database abstraction — uses Postgres if DATABASE_URL is set, else SQLite."""

import json
import logging
import os
import sqlite3

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_POSTGRES = DATABASE_URL.startswith("postgres")

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras


class Row(dict):
    """Dict that also supports attribute access and index access like sqlite3.Row."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


def get_connection():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    else:
        db_path = os.path.join(os.path.dirname(__file__), "auction.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn


def execute(conn, sql, params=None):
    """Execute SQL, adapting syntax for Postgres vs SQLite."""
    if USE_POSTGRES:
        # Convert ? placeholders to %s for psycopg2
        sql = sql.replace("?", "%s")
        # Convert SQLite-specific syntax
        sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        sql = sql.replace("INSERT OR IGNORE", "INSERT")
        sql = sql.replace("INSERT OR REPLACE", "INSERT")
    cur = conn.cursor()
    try:
        cur.execute(sql, params or ())
    except Exception as e:
        if USE_POSTGRES and "duplicate key" in str(e).lower():
            conn.rollback()
            return cur
        raise
    return cur


def fetchone(conn, sql, params=None):
    cur = execute(conn, sql, params)
    if USE_POSTGRES:
        row = cur.fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in cur.description]
        return Row(zip(cols, row))
    else:
        return cur.fetchone()


def fetchall(conn, sql, params=None):
    cur = execute(conn, sql, params)
    if USE_POSTGRES:
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        return [Row(zip(cols, r)) for r in rows]
    else:
        return cur.fetchall()


def commit(conn):
    conn.commit()


def close(conn):
    conn.close()
