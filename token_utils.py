"""
Token Utilities — HMAC-signed Metro Ticket Tokens
--------------------------------------------------
Token format:
  payload = "M1|<txn_id>|<src:02d>|<dst:02d>|<int timestamp>"
  token   = payload + "." + first 8 hex chars of HMAC-SHA256(SECRET_KEY, payload)

Example: M1|T48213abc|03|07|1730500000.9fa3c21b
"""

import hashlib
import hmac
import os
import time

import config
from stations import fare
import record


def _sign(payload: str) -> str:
    """Return first 8 hex chars of HMAC-SHA256(SECRET_KEY, payload)."""
    mac = hmac.new(config.SECRET_KEY, payload.encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()[:8]


def _make_txn_id() -> str:
    """Generate a transaction ID: 'T' + 8 random hex characters."""
    return "T" + os.urandom(4).hex()


def create_token(src: int, dst: int) -> str:
    """
    Create a signed token for a journey from src to dst.
    Also registers the ticket in the shared record (SQLite) in state J0
    with paid_fare = fare(src, dst).
    Returns the token string.
    """
    txn_id = _make_txn_id()
    ts = int(time.time())
    payload = f"M1|{txn_id}|{src:02d}|{dst:02d}|{ts}"
    sig = _sign(payload)
    token = f"{payload}.{sig}"

    # Register in the shared record
    paid = fare(src, dst)
    record.add_ticket(txn_id, src, dst, paid)

    return token


def verify_token(token: str) -> tuple:
    """
    Verify a token's HMAC signature.
    Returns (True, fields_dict) on success, (False, None) on failure.
    fields_dict = {'txn_id': str, 'source': int, 'dest': int, 'timestamp': int}
    Never raises on garbage input.
    """
    try:
        parts = token.rsplit(".", 1)
        if len(parts) != 2:
            return (False, None)
        payload, sig = parts
        expected_sig = _sign(payload)
        if not hmac.compare_digest(sig, expected_sig):
            return (False, None)
        # Parse payload: M1|txn_id|src|dst|timestamp
        fields = payload.split("|")
        if len(fields) != 5 or fields[0] != "M1":
            return (False, None)
        return (True, {
            "txn_id": fields[1],
            "source": int(fields[2]),
            "dest": int(fields[3]),
            "timestamp": int(fields[4]),
        })
    except Exception:
        return (False, None)


def make_qr_image(token: str):
    """
    Generate a QR code image for the token.
    Returns a PIL Image if the qrcode library is installed, otherwise None.
    """
    try:
        import qrcode
    except ImportError:
        return None
    qr = qrcode.make(token)
    return qr
