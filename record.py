"""
Record — Shared Ticket Store (SQLite)
--------------------------------------
The "central server" for the metro ticketing system. Uses SQLite so that
the Streamlit UI (which re-runs scripts on every click) never loses state.

Table: tickets
  txn_id TEXT PRIMARY KEY,
  source INT,
  dest INT,
  paid_fare INT,
  state TEXT,
  entry_time REAL,
  pending_amount INT,
  history TEXT
"""

import sqlite3

import config


def _connect():
    """Open a connection to config.DB_PATH (read at call time, not import time)."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the tickets table if it does not already exist."""
    conn = _connect()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                txn_id TEXT PRIMARY KEY,
                source INT,
                dest INT,
                paid_fare INT,
                state TEXT,
                entry_time REAL,
                pending_amount INT,
                history TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()


def reset_db():
    """Drop and recreate the tickets table (for tests)."""
    conn = _connect()
    try:
        conn.execute("DROP TABLE IF EXISTS tickets")
        conn.commit()
    finally:
        conn.close()
    init_db()


def add_ticket(txn_id: str, source: int, dest: int, paid_fare: int):
    """Insert a new ticket in state J0 with empty history."""
    init_db()  # ensure table exists
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO tickets (txn_id, source, dest, paid_fare, state, entry_time, pending_amount, history) "
            "VALUES (?, ?, ?, ?, 'J0', NULL, 0, '')",
            (txn_id, source, dest, paid_fare),
        )
        conn.commit()
    finally:
        conn.close()


def get_ticket(txn_id: str) -> dict:
    """
    Look up a ticket by txn_id. Returns a dict or None if not found.
    """
    init_db()  # ensure table exists
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM tickets WHERE txn_id = ?", (txn_id,)).fetchone()
        if row is None:
            return None
        return dict(row)
    finally:
        conn.close()


def update_ticket(txn_id: str, **fields):
    """
    Update arbitrary columns for a ticket.
    Example: update_ticket("T1234abcd", state="J1", entry_time=5.0)
    """
    if not fields:
        return
    init_db()
    conn = _connect()
    try:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [txn_id]
        conn.execute(f"UPDATE tickets SET {set_clause} WHERE txn_id = ?", values)
        conn.commit()
    finally:
        conn.close()


def append_history(txn_id: str, symbol: str):
    """Append a symbol to the ticket's history string."""
    init_db()
    conn = _connect()
    try:
        conn.execute(
            "UPDATE tickets SET history = history || ? WHERE txn_id = ?",
            (symbol, txn_id),
        )
        conn.commit()
    finally:
        conn.close()
