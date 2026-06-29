#!/usr/bin/env python3
"""
MOX Collective — World Cup Bracket  (single app: local + Vercel)

Storage:
  - Local dev:  SQLite file  (no setup; run `python api/index.py`)
  - Vercel:     Postgres      (set POSTGRES_URL — Vercel injects it from a
                              Vercel Postgres store). Photos are stored in the
                              database, so no Blob store is needed.

Vercel uses the `handler` class below as a serverless function (routed via
vercel.json). Running this file directly starts a local server that also serves
the static frontend from ../public.

Env:
  PORT                   local port (default 8000)
  ADMIN_PASSWORD         admin gate (default "mox")
  FOOTBALL_DATA_API_KEY  optional, enables live result sync
  POSTGRES_URL           when present -> Postgres backend (Vercel)
"""
import os, re, json, time, base64, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))      # .../api
ROOT = os.path.dirname(BASE)                            # project root
PUBLIC = os.path.join(BASE, "public")
SEED_PATH = os.path.join(BASE, "tournament.json")
SQLITE_PATH = os.path.join(ROOT, "bracket.db")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "mox")
FD_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "").strip()
PG_URL = (os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL") or "").strip()
IS_PG = bool(PG_URL)

# ----------------------------------------------------------------- storage
_inited = False

def _conn():
    if IS_PG:
        import psycopg2
        dsn = PG_URL
        if "sslmode=" not in dsn:
            dsn += ("&" if "?" in dsn else "?") + "sslmode=require"
        return psycopg2.connect(dsn)
    import sqlite3
    return sqlite3.connect(SQLITE_PATH)

def _q(sql):
    return sql.replace("?", "%s") if IS_PG else sql

def db_all(sql, args=()):
    c = _conn()
    try:
        cur = c.cursor(); cur.execute(_q(sql), args)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall(); c.commit()
        return [dict(zip(cols, r)) for r in rows]
    finally:
        c.close()

def db_one(sql, args=()):
    r = db_all(sql, args); return r[0] if r else None

def db_insert(sql, args=()):
    """INSERT ... RETURNING id  (supported by both Postgres and SQLite >= 3.35)."""
    c = _conn()
    try:
        cur = c.cursor(); cur.execute(_q(sql), args)
        rid = cur.fetchone(); c.commit()
        return rid[0] if rid else None
    finally:
        c.close()

def db_exec(sql, args=()):
    c = _conn()
    try:
        cur = c.cursor(); cur.execute(_q(sql), args); c.commit()
    finally:
        c.close()

def ensure_init():
    global _inited
    if _inited:
        return
    c = _conn()
    try:
        cur = c.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, val TEXT)")
        if IS_PG:
            cur.execute("""CREATE TABLE IF NOT EXISTS players(
                id SERIAL PRIMARY KEY, name TEXT,
                picks TEXT, champion TEXT, tiebreak INTEGER,
                created_at DOUBLE PRECISION, updated_at DOUBLE PRECISION)""")
        else:
            cur.execute("""CREATE TABLE IF NOT EXISTS players(
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT,
                picks TEXT, champion TEXT, tiebreak INTEGER,
                created_at REAL, updated_at REAL)""")
        c.commit()
    finally:
        c.close()
    _inited = True

SEED_B64 = "ew0KICAibmFtZSI6ICJGSUZBIFdvcmxkIEN1cCAyMDI2IOKAlCBLbm9ja291dCIsDQogICJzdWJ0aXRsZSI6ICJSb3VuZCBvZiAzMiDihpIgQ2hhbXBpb24iLA0KICAibG9ja2VkIjogZmFsc2UsDQogICJyb3VuZHMiOiBbDQogICAgew0KICAgICAgImtleSI6ICJSMzIiLA0KICAgICAgIm5hbWUiOiAiUm91bmQgb2YgMzIiLA0KICAgICAgInBvaW50cyI6IDENCiAgICB9LA0KICAgIHsNCiAgICAgICJrZXkiOiAiUjE2IiwNCiAgICAgICJuYW1lIjogIlJvdW5kIG9mIDE2IiwNCiAgICAgICJwb2ludHMiOiAyDQogICAgfSwNCiAgICB7DQogICAgICAia2V5IjogIlFGIiwNCiAgICAgICJuYW1lIjogIlF1YXJ0ZXJmaW5hbHMiLA0KICAgICAgInBvaW50cyI6IDQNCiAgICB9LA0KICAgIHsNCiAgICAgICJrZXkiOiAiU0YiLA0KICAgICAgIm5hbWUiOiAiU2VtaWZpbmFscyIsDQogICAgICAicG9pbnRzIjogOA0KICAgIH0sDQogICAgew0KICAgICAgImtleSI6ICJGIiwNCiAgICAgICJuYW1lIjogIkZpbmFsIiwNCiAgICAgICJwb2ludHMiOiAxNg0KICAgIH0NCiAgXSwNCiAgInRlYW1zIjogew0KICAgICJDQU4iOiB7DQogICAgICAibmFtZSI6ICJDYW5hZGEiDQogICAgfSwNCiAgICAiUlNBIjogew0KICAgICAgIm5hbWUiOiAiU291dGggQWZyaWNhIg0KICAgIH0sDQogICAgIk5FRCI6IHsNCiAgICAgICJuYW1lIjogIk5ldGhlcmxhbmRzIg0KICAgIH0sDQogICAgIk1BUiI6IHsNCiAgICAgICJuYW1lIjogIk1vcm9jY28iDQogICAgfSwNCiAgICAiR0VSIjogew0KICAgICAgIm5hbWUiOiAiR2VybWFueSINCiAgICB9LA0KICAgICJQQVIiOiB7DQogICAgICAibmFtZSI6ICJQYXJhZ3VheSINCiAgICB9LA0KICAgICJGUkEiOiB7DQogICAgICAibmFtZSI6ICJGcmFuY2UiDQogICAgfSwNCiAgICAiU1dFIjogew0KICAgICAgIm5hbWUiOiAiU3dlZGVuIg0KICAgIH0sDQogICAgIlBPUiI6IHsNCiAgICAgICJuYW1lIjogIlBvcnR1Z2FsIg0KICAgIH0sDQogICAgIkNSTyI6IHsNCiAgICAgICJuYW1lIjogIkNyb2F0aWEiDQogICAgfSwNCiAgICAiRVNQIjogew0KICAgICAgIm5hbWUiOiAiU3BhaW4iDQogICAgfSwNCiAgICAiQVVUIjogew0KICAgICAgIm5hbWUiOiAiQXVzdHJpYSINCiAgICB9LA0KICAgICJVU0EiOiB7DQogICAgICAibmFtZSI6ICJVU0EiDQogICAgfSwNCiAgICAiQklIIjogew0KICAgICAgIm5hbWUiOiAiQm9zbmlhICYgSGVyei4iDQogICAgfSwNCiAgICAiQkVMIjogew0KICAgICAgIm5hbWUiOiAiQmVsZ2l1bSINCiAgICB9LA0KICAgICJTRU4iOiB7DQogICAgICAibmFtZSI6ICJTZW5lZ2FsIg0KICAgIH0sDQogICAgIkJSQSI6IHsNCiAgICAgICJuYW1lIjogIkJyYXppbCINCiAgICB9LA0KICAgICJKUE4iOiB7DQogICAgICAibmFtZSI6ICJKYXBhbiINCiAgICB9LA0KICAgICJDSVYiOiB7DQogICAgICAibmFtZSI6ICJJdm9yeSBDb2FzdCINCiAgICB9LA0KICAgICJOT1IiOiB7DQogICAgICAibmFtZSI6ICJOb3J3YXkiDQogICAgfSwNCiAgICAiTUVYIjogew0KICAgICAgIm5hbWUiOiAiTWV4aWNvIg0KICAgIH0sDQogICAgIkVDVSI6IHsNCiAgICAgICJuYW1lIjogIkVjdWFkb3IiDQogICAgfSwNCiAgICAiRU5HIjogew0KICAgICAgIm5hbWUiOiAiRW5nbGFuZCINCiAgICB9LA0KICAgICJDT0QiOiB7DQogICAgICAibmFtZSI6ICJEUiBDb25nbyINCiAgICB9LA0KICAgICJBUkciOiB7DQogICAgICAibmFtZSI6ICJBcmdlbnRpbmEiDQogICAgfSwNCiAgICAiQ1BWIjogew0KICAgICAgIm5hbWUiOiAiQ2FwZSBWZXJkZSINCiAgICB9LA0KICAgICJBVVMiOiB7DQogICAgICAibmFtZSI6ICJBdXN0cmFsaWEiDQogICAgfSwNCiAgICAiRUdZIjogew0KICAgICAgIm5hbWUiOiAiRWd5cHQiDQogICAgfSwNCiAgICAiU1VJIjogew0KICAgICAgIm5hbWUiOiAiU3dpdHplcmxhbmQiDQogICAgfSwNCiAgICAiQUxHIjogew0KICAgICAgIm5hbWUiOiAiQWxnZXJpYSINCiAgICB9LA0KICAgICJDT0wiOiB7DQogICAgICAibmFtZSI6ICJDb2xvbWJpYSINCiAgICB9LA0KICAgICJHSEEiOiB7DQogICAgICAibmFtZSI6ICJHaGFuYSINCiAgICB9DQogIH0sDQogICJtYXRjaGVzIjogWw0KICAgIHsNCiAgICAgICJpZCI6ICJNMSIsDQogICAgICAicm91bmQiOiAiUjMyIiwNCiAgICAgICJhIjogew0KICAgICAgICAidGVhbSI6ICJDQU4iDQogICAgICB9LA0KICAgICAgImIiOiB7DQogICAgICAgICJ0ZWFtIjogIlJTQSINCiAgICAgIH0sDQogICAgICAid2lubmVyIjogbnVsbA0KICAgIH0sDQogICAgew0KICAgICAgImlkIjogIk0yIiwNCiAgICAgICJyb3VuZCI6ICJSMzIiLA0KICAgICAgImEiOiB7DQogICAgICAgICJ0ZWFtIjogIk5FRCINCiAgICAgIH0sDQogICAgICAiYiI6IHsNCiAgICAgICAgInRlYW0iOiAiTUFSIg0KICAgICAgfSwNCiAgICAgICJ3aW5uZXIiOiBudWxsDQogICAgfSwNCiAgICB7DQogICAgICAiaWQiOiAiTTMiLA0KICAgICAgInJvdW5kIjogIlIzMiIsDQogICAgICAiYSI6IHsNCiAgICAgICAgInRlYW0iOiAiR0VSIg0KICAgICAgfSwNCiAgICAgICJiIjogew0KICAgICAgICAidGVhbSI6ICJQQVIiDQogICAgICB9LA0KICAgICAgIndpbm5lciI6IG51bGwNCiAgICB9LA0KICAgIHsNCiAgICAgICJpZCI6ICJNNCIsDQogICAgICAicm91bmQiOiAiUjMyIiwNCiAgICAgICJhIjogew0KICAgICAgICAidGVhbSI6ICJGUkEiDQogICAgICB9LA0KICAgICAgImIiOiB7DQogICAgICAgICJ0ZWFtIjogIlNXRSINCiAgICAgIH0sDQogICAgICAid2lubmVyIjogbnVsbA0KICAgIH0sDQogICAgew0KICAgICAgImlkIjogIk01IiwNCiAgICAgICJyb3VuZCI6ICJSMzIiLA0KICAgICAgImEiOiB7DQogICAgICAgICJ0ZWFtIjogIlBPUiINCiAgICAgIH0sDQogICAgICAiYiI6IHsNCiAgICAgICAgInRlYW0iOiAiQ1JPIg0KICAgICAgfSwNCiAgICAgICJ3aW5uZXIiOiBudWxsDQogICAgfSwNCiAgICB7DQogICAgICAiaWQiOiAiTTYiLA0KICAgICAgInJvdW5kIjogIlIzMiIsDQogICAgICAiYSI6IHsNCiAgICAgICAgInRlYW0iOiAiRVNQIg0KICAgICAgfSwNCiAgICAgICJiIjogew0KICAgICAgICAidGVhbSI6ICJBVVQiDQogICAgICB9LA0KICAgICAgIndpbm5lciI6IG51bGwNCiAgICB9LA0KICAgIHsNCiAgICAgICJpZCI6ICJNNyIsDQogICAgICAicm91bmQiOiAiUjMyIiwNCiAgICAgICJhIjogew0KICAgICAgICAidGVhbSI6ICJVU0EiDQogICAgICB9LA0KICAgICAgImIiOiB7DQogICAgICAgICJ0ZWFtIjogIkJJSCINCiAgICAgIH0sDQogICAgICAid2lubmVyIjogbnVsbA0KICAgIH0sDQogICAgew0KICAgICAgImlkIjogIk04IiwNCiAgICAgICJyb3VuZCI6ICJSMzIiLA0KICAgICAgImEiOiB7DQogICAgICAgICJ0ZWFtIjogIkJFTCINCiAgICAgIH0sDQogICAgICAiYiI6IHsNCiAgICAgICAgInRlYW0iOiAiU0VOIg0KICAgICAgfSwNCiAgICAgICJ3aW5uZXIiOiBudWxsDQogICAgfSwNCiAgICB7DQogICAgICAiaWQiOiAiTTkiLA0KICAgICAgInJvdW5kIjogIlIzMiIsDQogICAgICAiYSI6IHsNCiAgICAgICAgInRlYW0iOiAiQlJBIg0KICAgICAgfSwNCiAgICAgICJiIjogew0KICAgICAgICAidGVhbSI6ICJKUE4iDQogICAgICB9LA0KICAgICAgIndpbm5lciI6IG51bGwNCiAgICB9LA0KICAgIHsNCiAgICAgICJpZCI6ICJNMTAiLA0KICAgICAgInJvdW5kIjogIlIzMiIsDQogICAgICAiYSI6IHsNCiAgICAgICAgInRlYW0iOiAiQ0lWIg0KICAgICAgfSwNCiAgICAgICJiIjogew0KICAgICAgICAidGVhbSI6ICJOT1IiDQogICAgICB9LA0KICAgICAgIndpbm5lciI6IG51bGwNCiAgICB9LA0KICAgIHsNCiAgICAgICJpZCI6ICJNMTEiLA0KICAgICAgInJvdW5kIjogIlIzMiIsDQogICAgICAiYSI6IHsNCiAgICAgICAgInRlYW0iOiAiTUVYIg0KICAgICAgfSwNCiAgICAgICJiIjogew0KICAgICAgICAidGVhbSI6ICJFQ1UiDQogICAgICB9LA0KICAgICAgIndpbm5lciI6IG51bGwNCiAgICB9LA0KICAgIHsNCiAgICAgICJpZCI6ICJNMTIiLA0KICAgICAgInJvdW5kIjogIlIzMiIsDQogICAgICAiYSI6IHsNCiAgICAgICAgInRlYW0iOiAiRU5HIg0KICAgICAgfSwNCiAgICAgICJiIjogew0KICAgICAgICAidGVhbSI6ICJDT0QiDQogICAgICB9LA0KICAgICAgIndpbm5lciI6IG51bGwNCiAgICB9LA0KICAgIHsNCiAgICAgICJpZCI6ICJNMTMiLA0KICAgICAgInJvdW5kIjogIlIzMiIsDQogICAgICAiYSI6IHsNCiAgICAgICAgInRlYW0iOiAiQVJHIg0KICAgICAgfSwNCiAgICAgICJiIjogew0KICAgICAgICAidGVhbSI6ICJDUFYiDQogICAgICB9LA0KICAgICAgIndpbm5lciI6IG51bGwNCiAgICB9LA0KICAgIHsNCiAgICAgICJpZCI6ICJNMTQiLA0KICAgICAgInJvdW5kIjogIlIzMiIsDQogICAgICAiYSI6IHsNCiAgICAgICAgInRlYW0iOiAiQVVTIg0KICAgICAgfSwNCiAgICAgICJiIjogew0KICAgICAgICAidGVhbSI6ICJFR1kiDQogICAgICB9LA0KICAgICAgIndpbm5lciI6IG51bGwNCiAgICB9LA0KICAgIHsNCiAgICAgICJpZCI6ICJNMTUiLA0KICAgICAgInJvdW5kIjogIlIzMiIsDQogICAgICAiYSI6IHsNCiAgICAgICAgInRlYW0iOiAiU1VJIg0KICAgICAgfSwNCiAgICAgICJiIjogew0KICAgICAgICAidGVhbSI6ICJBTEciDQogICAgICB9LA0KICAgICAgIndpbm5lciI6IG51bGwNCiAgICB9LA0KICAgIHsNCiAgICAgICJpZCI6ICJNMTYiLA0KICAgICAgInJvdW5kIjogIlIzMiIsDQogICAgICAiYSI6IHsNCiAgICAgICAgInRlYW0iOiAiQ09MIg0KICAgICAgfSwNCiAgICAgICJiIjogew0KICAgICAgICAidGVhbSI6ICJHSEEiDQogICAgICB9LA0KICAgICAgIndpbm5lciI6IG51bGwNCiAgICB9LA0KICAgIHsNCiAgICAgICJpZCI6ICJNMTciLA0KICAgICAgInJvdW5kIjogIlIxNiIsDQogICAgICAiYSI6IHsNCiAgICAgICAgImZyb20iOiAiTTEiDQogICAgICB9LA0KICAgICAgImIiOiB7DQogICAgICAgICJmcm9tIjogIk0yIg0KICAgICAgfSwNCiAgICAgICJ3aW5uZXIiOiBudWxsDQogICAgfSwNCiAgICB7DQogICAgICAiaWQiOiAiTTE4IiwNCiAgICAgICJyb3VuZCI6ICJSMTYiLA0KICAgICAgImEiOiB7DQogICAgICAgICJmcm9tIjogIk0zIg0KICAgICAgfSwNCiAgICAgICJiIjogew0KICAgICAgICAiZnJvbSI6ICJNNCINCiAgICAgIH0sDQogICAgICAid2lubmVyIjogbnVsbA0KICAgIH0sDQogICAgew0KICAgICAgImlkIjogIk0xOSIsDQogICAgICAicm91bmQiOiAiUjE2IiwNCiAgICAgICJhIjogew0KICAgICAgICAiZnJvbSI6ICJNNSINCiAgICAgIH0sDQogICAgICAiYiI6IHsNCiAgICAgICAgImZyb20iOiAiTTYiDQogICAgICB9LA0KICAgICAgIndpbm5lciI6IG51bGwNCiAgICB9LA0KICAgIHsNCiAgICAgICJpZCI6ICJNMjAiLA0KICAgICAgInJvdW5kIjogIlIxNiIsDQogICAgICAiYSI6IHsNCiAgICAgICAgImZyb20iOiAiTTciDQogICAgICB9LA0KICAgICAgImIiOiB7DQogICAgICAgICJmcm9tIjogIk04Ig0KICAgICAgfSwNCiAgICAgICJ3aW5uZXIiOiBudWxsDQogICAgfSwNCiAgICB7DQogICAgICAiaWQiOiAiTTIxIiwNCiAgICAgICJyb3VuZCI6ICJSMTYiLA0KICAgICAgImEiOiB7DQogICAgICAgICJmcm9tIjogIk05Ig0KICAgICAgfSwNCiAgICAgICJiIjogew0KICAgICAgICAiZnJvbSI6ICJNMTAiDQogICAgICB9LA0KICAgICAgIndpbm5lciI6IG51bGwNCiAgICB9LA0KICAgIHsNCiAgICAgICJpZCI6ICJNMjIiLA0KICAgICAgInJvdW5kIjogIlIxNiIsDQogICAgICAiYSI6IHsNCiAgICAgICAgImZyb20iOiAiTTExIg0KICAgICAgfSwNCiAgICAgICJiIjogew0KICAgICAgICAiZnJvbSI6ICJNMTIiDQogICAgICB9LA0KICAgICAgIndpbm5lciI6IG51bGwNCiAgICB9LA0KICAgIHsNCiAgICAgICJpZCI6ICJNMjMiLA0KICAgICAgInJvdW5kIjogIlIxNiIsDQogICAgICAiYSI6IHsNCiAgICAgICAgImZyb20iOiAiTTEzIg0KICAgICAgfSwNCiAgICAgICJiIjogew0KICAgICAgICAiZnJvbSI6ICJNMTQiDQogICAgICB9LA0KICAgICAgIndpbm5lciI6IG51bGwNCiAgICB9LA0KICAgIHsNCiAgICAgICJpZCI6ICJNMjQiLA0KICAgICAgInJvdW5kIjogIlIxNiIsDQogICAgICAiYSI6IHsNCiAgICAgICAgImZyb20iOiAiTTE1Ig0KICAgICAgfSwNCiAgICAgICJiIjogew0KICAgICAgICAiZnJvbSI6ICJNMTYiDQogICAgICB9LA0KICAgICAgIndpbm5lciI6IG51bGwNCiAgICB9LA0KICAgIHsNCiAgICAgICJpZCI6ICJNMjUiLA0KICAgICAgInJvdW5kIjogIlFGIiwNCiAgICAgICJhIjogew0KICAgICAgICAiZnJvbSI6ICJNMTciDQogICAgICB9LA0KICAgICAgImIiOiB7DQogICAgICAgICJmcm9tIjogIk0xOCINCiAgICAgIH0sDQogICAgICAid2lubmVyIjogbnVsbA0KICAgIH0sDQogICAgew0KICAgICAgImlkIjogIk0yNiIsDQogICAgICAicm91bmQiOiAiUUYiLA0KICAgICAgImEiOiB7DQogICAgICAgICJmcm9tIjogIk0xOSINCiAgICAgIH0sDQogICAgICAiYiI6IHsNCiAgICAgICAgImZyb20iOiAiTTIwIg0KICAgICAgfSwNCiAgICAgICJ3aW5uZXIiOiBudWxsDQogICAgfSwNCiAgICB7DQogICAgICAiaWQiOiAiTTI3IiwNCiAgICAgICJyb3VuZCI6ICJRRiIsDQogICAgICAiYSI6IHsNCiAgICAgICAgImZyb20iOiAiTTIxIg0KICAgICAgfSwNCiAgICAgICJiIjogew0KICAgICAgICAiZnJvbSI6ICJNMjIiDQogICAgICB9LA0KICAgICAgIndpbm5lciI6IG51bGwNCiAgICB9LA0KICAgIHsNCiAgICAgICJpZCI6ICJNMjgiLA0KICAgICAgInJvdW5kIjogIlFGIiwNCiAgICAgICJhIjogew0KICAgICAgICAiZnJvbSI6ICJNMjMiDQogICAgICB9LA0KICAgICAgImIiOiB7DQogICAgICAgICJmcm9tIjogIk0yNCINCiAgICAgIH0sDQogICAgICAid2lubmVyIjogbnVsbA0KICAgIH0sDQogICAgew0KICAgICAgImlkIjogIk0yOSIsDQogICAgICAicm91bmQiOiAiU0YiLA0KICAgICAgImEiOiB7DQogICAgICAgICJmcm9tIjogIk0yNSINCiAgICAgIH0sDQogICAgICAiYiI6IHsNCiAgICAgICAgImZyb20iOiAiTTI2Ig0KICAgICAgfSwNCiAgICAgICJ3aW5uZXIiOiBudWxsDQogICAgfSwNCiAgICB7DQogICAgICAiaWQiOiAiTTMwIiwNCiAgICAgICJyb3VuZCI6ICJTRiIsDQogICAgICAiYSI6IHsNCiAgICAgICAgImZyb20iOiAiTTI3Ig0KICAgICAgfSwNCiAgICAgICJiIjogew0KICAgICAgICAiZnJvbSI6ICJNMjgiDQogICAgICB9LA0KICAgICAgIndpbm5lciI6IG51bGwNCiAgICB9LA0KICAgIHsNCiAgICAgICJpZCI6ICJNMzEiLA0KICAgICAgInJvdW5kIjogIkYiLA0KICAgICAgImEiOiB7DQogICAgICAgICJmcm9tIjogIk0yOSINCiAgICAgIH0sDQogICAgICAiYiI6IHsNCiAgICAgICAgImZyb20iOiAiTTMwIg0KICAgICAgfSwNCiAgICAgICJ3aW5uZXIiOiBudWxsDQogICAgfQ0KICBdDQp9"

# Tournament seed is embedded (base64 of the original tournament.json) so it
# always ships inside the function bundle — no external file to trace/include.
def load_seed():
    return json.loads(base64.b64decode(SEED_B64).decode("utf-8"))

def get_tournament():
    row = db_one("SELECT val FROM kv WHERE key='tournament'")
    if not row:
        doc = load_seed(); save_tournament(doc); return doc
    return json.loads(row["val"])

def save_tournament(doc):
    db_exec("INSERT INTO kv(key,val) VALUES('tournament',?) "
            "ON CONFLICT (key) DO UPDATE SET val=EXCLUDED.val", (json.dumps(doc),))

def players_raw():
    return db_all("SELECT id,name,picks,champion,tiebreak,created_at,updated_at "
                  "FROM players ORDER BY id")

def player_dict(r):
    return {
        "id": r["id"], "name": r["name"],
        "picks": json.loads(r["picks"]), "champion": r["champion"],
        "tiebreak": r["tiebreak"], "created_at": r["created_at"], "updated_at": r["updated_at"],
    }

# ----------------------------------------------------------------- bracket logic
def round_points(doc): return {r["key"]: r["points"] for r in doc["rounds"]}
def match_map(doc): return {m["id"]: m for m in doc["matches"]}

def resolve_actual_slot(doc, mm, slot):
    if "team" in slot: return slot["team"]
    src = mm.get(slot["from"]); return src["winner"] if src else None

def actual_match_teams(doc, mm, m):
    return resolve_actual_slot(doc, mm, m["a"]), resolve_actual_slot(doc, mm, m["b"])

def prune_invalid_winners(doc):
    mm = match_map(doc)
    for m in sorted(doc["matches"], key=lambda x: int(x["id"][1:])):
        if m.get("winner"):
            ta, tb = actual_match_teams(doc, mm, m)
            if m["winner"] not in (ta, tb):
                m["winner"] = None

def score_bracket(doc, picks):
    mm = match_map(doc); pts = round_points(doc)
    eliminated = set()
    for m in doc["matches"]:
        if m.get("winner"):
            ta, tb = actual_match_teams(doc, mm, m)
            for t in (ta, tb):
                if t and t != m["winner"]:
                    eliminated.add(t)
    points = correct = decided = 0
    per_round = {r["key"]: {"correct": 0, "total": 0, "points": 0} for r in doc["rounds"]}
    still_possible = 0
    for m in doc["matches"]:
        rk = m["round"]; per_round[rk]["total"] += 1
        pick = picks.get(m["id"]); actual_w = m.get("winner")
        if actual_w:
            decided += 1
            if pick and pick == actual_w:
                points += pts[rk]; correct += 1
                per_round[rk]["correct"] += 1; per_round[rk]["points"] += pts[rk]
        else:
            ta, tb = actual_match_teams(doc, mm, m)
            if pick:
                if ta and tb:
                    if pick in (ta, tb): still_possible += pts[rk]
                else:
                    still_possible += pts[rk]
    champ_pick = picks.get("M31"); champ_actual = mm["M31"]["winner"]
    return {
        "points": points, "correct": correct, "decided": decided, "per_round": per_round,
        "max_possible": points + still_possible, "champion": champ_pick,
        "champion_correct": bool(champ_actual and champ_pick == champ_actual),
        "champion_decided": bool(champ_actual),
        "champion_alive": bool(champ_pick) and champ_pick not in eliminated,
    }

def leaderboard():
    doc = get_tournament(); out = []
    for r in players_raw():
        p = player_dict(r); s = score_bracket(doc, p["picks"])
        out.append({"id": p["id"], "name": p["name"],
                    "champion": p["champion"], "tiebreak": p["tiebreak"], **s})
    out.sort(key=lambda x: (-x["points"], -x["max_possible"], x["name"].lower()))
    rank = 0; last = None
    for i, p in enumerate(out):
        key = (p["points"], p["max_possible"])
        if key != last: rank = i + 1; last = key
        p["rank"] = rank
    return out

# ----------------------------------------------------------------- live sync
FD_STAGE_TO_ROUND = {
    "LAST_32": "R32", "ROUND_OF_32": "R32", "LAST_16": "R16", "ROUND_OF_16": "R16",
    "QUARTER_FINALS": "QF", "QUARTER_FINAL": "QF", "SEMI_FINALS": "SF", "SEMI_FINAL": "SF",
    "FINAL": "F",
}
def _norm(name): return re.sub(r"[^a-z]", "", (name or "").lower())

def sync_from_api():
    if not FD_KEY:
        return {"ok": False, "error": "No FOOTBALL_DATA_API_KEY configured.", "updated": 0}
    url = "https://api.football-data.org/v4/competitions/WC/matches"
    req = urllib.request.Request(url, headers={"X-Auth-Token": FD_KEY})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": "API request failed: %s" % e, "updated": 0}
    doc = get_tournament(); mm = match_map(doc)
    name2code = {}
    for code, t in doc["teams"].items():
        name2code[_norm(t["name"])] = code; name2code[_norm(code)] = code
    updated = 0
    for fm in payload.get("matches", []):
        if fm.get("status") != "FINISHED": continue
        stage = FD_STAGE_TO_ROUND.get(fm.get("stage", ""))
        if not stage: continue
        home = name2code.get(_norm((fm.get("homeTeam") or {}).get("name")))
        away = name2code.get(_norm((fm.get("awayTeam") or {}).get("name")))
        if not home or not away: continue
        w = fm.get("score", {}).get("winner")
        if w == "HOME_TEAM": win = home
        elif w == "AWAY_TEAM": win = away
        else: continue
        for m in doc["matches"]:
            if m["round"] != stage: continue
            ta, tb = actual_match_teams(doc, mm, m)
            if ta and tb and {ta, tb} == {home, away}:
                if m.get("winner") != win:
                    m["winner"] = win; updated += 1
                break
    if updated:
        prune_invalid_winners(doc); save_tournament(doc)
    return {"ok": True, "updated": updated}

# ----------------------------------------------------------------- http handler
MIME = {".html":"text/html; charset=utf-8",".js":"text/javascript; charset=utf-8",
    ".css":"text/css; charset=utf-8",".json":"application/json; charset=utf-8",
    ".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg",".webp":"image/webp",
    ".svg":"image/svg+xml",".otf":"font/otf",".ttf":"font/ttf",".woff":"font/woff",
    ".woff2":"font/woff2",".ico":"image/x-icon"}
def guess_type(p): return MIME.get(os.path.splitext(p)[1].lower(), "application/octet-stream")

class handler(BaseHTTPRequestHandler):
    server_version = "MoxBracket/2.0"
    def log_message(self, fmt, *a): pass

    # helpers
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n <= 0: return {}
        try: return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception: return {}

    def _admin(self): return self.headers.get("X-Admin-Password", "") == ADMIN_PASSWORD
    def _path(self): return self.path.split("?", 1)[0]
    def _query(self):
        q = self.path.split("?", 1)
        out = {}
        if len(q) > 1:
            for pair in q[1].split("&"):
                if "=" in pair: k, v = pair.split("=", 1); out[k] = v
        return out

    # routing
    def do_GET(self):
        ensure_init()
        p = self._path()
        if p == "/api/tournament": return self._json(get_tournament())
        if p == "/api/leaderboard": return self._json({"players": leaderboard()})
        m = re.match(r"^/api/players/(\d+)$", p)
        if m: return self.get_player(int(m.group(1)))
        if p == "/api/players": return self._json({"players": [player_dict(r) for r in players_raw()]})
        return self.serve_static(p)

    def do_POST(self):
        ensure_init()
        p = self._path()
        if p == "/api/players": return self.create_player()
        if p == "/api/admin/result": return self.admin_result()
        if p == "/api/admin/lock": return self.admin_lock()
        if p == "/api/admin/sync": return self.admin_sync()
        if p == "/api/admin/reset-results": return self.admin_reset()
        return self._json({"error": "not found"}, 404)

    def do_DELETE(self):
        ensure_init()
        m = re.match(r"^/api/players/(\d+)$", self._path())
        if m: return self.delete_player(int(m.group(1)))
        return self._json({"error": "not found"}, 404)

    # players
    def get_player(self, pid):
        r = db_one("SELECT id,name,picks,champion,tiebreak,created_at,updated_at "
                   "FROM players WHERE id=?", (pid,))
        if not r: return self._json({"error": "not found"}, 404)
        p = player_dict(r); p["score"] = score_bracket(get_tournament(), p["picks"])
        return self._json(p)

    def create_player(self):
        doc = get_tournament()
        if doc.get("locked"):
            return self._json({"error": "Brackets are locked — the tournament has started."}, 403)
        b = self._body()
        name = (b.get("name") or "").strip()[:40]
        picks = b.get("picks") or {}
        tiebreak = int(b.get("tiebreak") or 0)
        if not name: return self._json({"error": "Name is required."}, 400)
        ids = {m["id"] for m in doc["matches"]}
        if set(picks.keys()) != ids:
            return self._json({"error": "Bracket is incomplete — pick every matchup."}, 400)
        champion = picks.get("M31")
        now = time.time()
        pid = db_insert(
            "INSERT INTO players(name,picks,champion,tiebreak,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?) RETURNING id",
            (name, json.dumps(picks), champion, tiebreak, now, now))
        return self._json({"ok": True, "id": pid})

    def delete_player(self, pid):
        if not self._admin(): return self._json({"error": "admin only"}, 403)
        db_exec("DELETE FROM players WHERE id=?", (pid,))
        return self._json({"ok": True})

    # admin
    def admin_result(self):
        if not self._admin(): return self._json({"error": "Wrong admin password."}, 403)
        b = self._body(); match_id = b.get("match"); winner = b.get("winner")
        doc = get_tournament(); mm = match_map(doc)
        if match_id not in mm: return self._json({"error": "unknown match"}, 400)
        m = mm[match_id]
        if winner is not None:
            ta, tb = actual_match_teams(doc, mm, m)
            if winner not in (ta, tb):
                return self._json({"error": "winner must be one of the two teams currently in this match"}, 400)
        m["winner"] = winner
        prune_invalid_winners(doc); save_tournament(doc)
        return self._json({"ok": True})

    def admin_lock(self):
        if not self._admin(): return self._json({"error": "Wrong admin password."}, 403)
        b = self._body(); doc = get_tournament()
        doc["locked"] = bool(b.get("locked", True)); save_tournament(doc)
        return self._json({"ok": True, "locked": doc["locked"]})

    def admin_reset(self):
        if not self._admin(): return self._json({"error": "Wrong admin password."}, 403)
        doc = get_tournament()
        for m in doc["matches"]: m["winner"] = None
        save_tournament(doc); return self._json({"ok": True})

    def admin_sync(self):
        if not self._admin(): return self._json({"error": "Wrong admin password."}, 403)
        return self._json(sync_from_api())

    # frontend: one self-contained file (CSS/JS/fonts/images inlined), bundled
    # next to this module so it always ships inside the function. Hash-routed SPA,
    # so every non-API path returns the same shell.
    def serve_static(self, path):
        if path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        try:
            with open(os.path.join(BASE, "frontend.html"), "rb") as f:
                data = f.read()
        except OSError:
            return self._json({"error": "not found"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers(); self.wfile.write(data)

# ----------------------------------------------------------------- local server
if __name__ == "__main__":
    ensure_init()
    port = int(os.environ.get("PORT", "8000"))
    print("=" * 56)
    print("  MOX Collective — World Cup Bracket")
    print("  http://localhost:%d" % port)
    print("  Storage: %s" % ("Postgres" if IS_PG else "SQLite (%s)" % SQLITE_PATH))
    print("  Admin password: %s" % ADMIN_PASSWORD)
    print("  Live sync: %s" % ("ENABLED" if FD_KEY else "manual only"))
    print("=" * 56)
    ThreadingHTTPServer(("0.0.0.0", port), handler).serve_forever()
