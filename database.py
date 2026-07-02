import sqlite3
import json
import datetime
import os

DB_NAME = "audits.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            url TEXT NOT NULL,
            report_data TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def save_audit(url: str, report_data: dict):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()
    c.execute('''
        INSERT INTO audits (timestamp, url, report_data)
        VALUES (?, ?, ?)
    ''', (timestamp, url, json.dumps(report_data)))
    conn.commit()
    conn.close()

def get_last_audit(url: str) -> dict | None:
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT report_data FROM audits
        WHERE url = ?
        ORDER BY timestamp DESC
        LIMIT 1
    ''', (url,))
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None

def get_previous_audit(url: str) -> dict | None:
    # Gets the audit before the last one
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT report_data FROM audits
        WHERE url = ?
        ORDER BY timestamp DESC
        LIMIT 1 OFFSET 1
    ''', (url,))
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None
