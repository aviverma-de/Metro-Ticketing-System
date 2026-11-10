"""
Journey — Classifier and Gate Logic
-------------------------------------
The bridge between the physical world (token scans, stations, time)
and Person 1's abstract Journey DFA.

classify() turns each scan into exactly one DFA symbol.
process_scan() feeds that symbol into the DFA and updates the record.
pay_excess() handles the payment step for excess-fare / over-time charges.
get_ticket_status() exposes the ticket record for the UI.
"""

from journey_automata import step, get_moore_output, get_mealy_output, JOURNEY_DFA
from token_utils import verify_token
from stations import distance, fare_for_distance, excess_fare
import config
import record


def classify(token: str, station: int, gate_type: str, now: float) -> str:
    """
    Classify a scan event into exactly one DFA symbol.
    This function is READ-ONLY — it does not write to the record.

    Parameters
    ----------
    token : str       — The scanned ticket token.
    station : int     — The station where the scan occurs.
    gate_type : str   — "entry" or "exit".
    now : float       — Simulated clock in minutes.

    Returns
    -------
    str — One of: "E", "D", "X", "O", "T", "W", "R".
    """
    # (a) Signature invalid, or txn not found in the record -> "W"
    valid, fields = verify_token(token)
    if not valid:
        return "W"
    txn_id = fields["txn_id"]
    ticket = record.get_ticket(txn_id)
    if ticket is None:
        return "W"

    state = ticket["state"]

    # (b) Ticket state J2 or J3 -> "R" (reuse of a closed ticket)
    if state in ("J2", "J3"):
        return "R"

    # (c) Ticket state JT -> "W"
    if state == "JT":
        return "W"

    # (d) Entry gate
    if gate_type == "entry":
        if state == "J0" and station == ticket["source"]:
            return "E"
        else:
            return "W"

    # (e-h) Exit gate
    # (e) If state is not J1 or JE -> "W"
    if state not in ("J1", "JE"):
        return "W"

    source = ticket["source"]
    entry_time = ticket["entry_time"]

    # (f) Over-time check
    if now - entry_time > config.TIME_LIMIT:
        return "T"

    # (g) Correct destination
    if station == ticket["dest"]:
        return "D"

    # (h) Compare fares, not raw distances
    exit_fare = fare_for_distance(distance(source, station))
    paid_fare = ticket["paid_fare"]
    if exit_fare > paid_fare:
        return "O"
    else:
        return "X"


def process_scan(token: str, station: int, gate_type: str, now: float) -> dict:
    """
    Process a gate scan: classify, step the DFA, update the record.

    Returns a dict with keys:
      symbol, old_state, new_state, gate, amount, message,
      moore_output, mealy_output, valid
    """
    # Classify
    symbol = classify(token, station, gate_type, now)

    # Get ticket info (may be None for invalid tokens)
    valid_tok, fields = verify_token(token)
    ticket = None
    if valid_tok:
        ticket = record.get_ticket(fields["txn_id"])

    # If the token is invalid or the txn is unknown: do NOT touch the record
    if not valid_tok or ticket is None:
        return {
            "symbol": "W",
            "old_state": None,
            "new_state": "JT",
            "gate": "LOCKED",
            "amount": 0,
            "message": "Invalid ticket or wrong use. Gate locked.",
            "moore_output": get_moore_output("JT"),
            "mealy_output": "Lock gate, alarm",
            "valid": False,
        }

    old_state = ticket["state"]
    new_state = step(old_state, symbol)

    # Determine gate from Mealy output
    mealy_out = get_mealy_output(old_state, symbol)
    gate = "OPEN" if mealy_out.startswith("Open") else "LOCKED"

    # Compute amount
    amount = 0
    source = ticket["source"]
    paid_fare = ticket["paid_fare"]

    if symbol == "O":
        amount = excess_fare(source, station, paid_fare)
    elif symbol == "T":
        amount = config.OVERTIME_CHARGE

    # Update record
    update_fields = {"state": new_state}

    if symbol == "E":
        update_fields["entry_time"] = now

    if new_state == "JE":
        update_fields["pending_amount"] = amount

    record.update_ticket(fields["txn_id"], **update_fields)
    record.append_history(fields["txn_id"], symbol)

    # Moore output — for JE, replace the template with the real amount
    moore_out = get_moore_output(new_state)
    if new_state == "JE":
        if symbol == "O":
            moore_out = f"Gate LOCKED, show Pay excess Rs {amount}"
        elif symbol == "T":
            moore_out = f"Gate LOCKED, show Pay over-time charge Rs {amount}"
        else:
            # Fallback for O/T self-loops
            moore_out = f"Gate LOCKED, show Pay Rs {amount}"

    # Message by symbol
    messages = {
        "E": "Entry accepted. Gate open.",
        "D": "Thank you. Exit gate open.",
        "X": "Early exit recorded. Exit gate open.",
        "O": f"Pay excess Rs {amount}",
        "T": f"Pay over-time charge Rs {amount}",
        "W": "Invalid ticket or wrong use. Gate locked.",
        "R": "Ticket already used. Gate locked.",
    }
    message = messages.get(symbol, "Unknown event.")

    return {
        "symbol": symbol,
        "old_state": old_state,
        "new_state": new_state,
        "gate": gate,
        "amount": amount,
        "message": message,
        "moore_output": moore_out,
        "mealy_output": mealy_out,
        "valid": True,
    }


def pay_excess(token: str) -> dict:
    """
    Process payment for an excess-fare or over-time charge.
    Feeds "P" into the DFA only if the ticket is in state JE.

    Returns a dict with the same keys as process_scan().
    """
    valid_tok, fields = verify_token(token)
    if not valid_tok:
        return {
            "symbol": None,
            "old_state": None,
            "new_state": None,
            "gate": "LOCKED",
            "amount": 0,
            "message": "No charge pending",
            "moore_output": "",
            "mealy_output": "",
            "valid": False,
        }

    ticket = record.get_ticket(fields["txn_id"])
    if ticket is None:
        return {
            "symbol": None,
            "old_state": None,
            "new_state": None,
            "gate": "LOCKED",
            "amount": 0,
            "message": "No charge pending",
            "moore_output": "",
            "mealy_output": "",
            "valid": False,
        }

    old_state = ticket["state"]

    if old_state != "JE":
        return {
            "symbol": None,
            "old_state": old_state,
            "new_state": old_state,
            "gate": "LOCKED",
            "amount": 0,
            "message": "No charge pending",
            "moore_output": get_moore_output(old_state),
            "mealy_output": "",
            "valid": True,
        }

    # Feed "P" into the DFA
    new_state = step("JE", "P")  # -> J2
    amount = ticket["pending_amount"]

    # Mealy output
    mealy_out = get_mealy_output("JE", "P")
    gate = "OPEN" if mealy_out.startswith("Open") else "LOCKED"

    # Update record
    record.update_ticket(fields["txn_id"], state=new_state, pending_amount=0)
    record.append_history(fields["txn_id"], "P")

    return {
        "symbol": "P",
        "old_state": "JE",
        "new_state": new_state,
        "gate": gate,
        "amount": amount,
        "message": "Charge paid. Exit gate open.",
        "moore_output": get_moore_output(new_state),
        "mealy_output": mealy_out,
        "valid": True,
    }


def get_ticket_status(token: str) -> dict:
    """
    Look up the full ticket record for the UI.
    Returns dict with txn_id, source, dest, paid_fare, state, entry_time,
    pending_amount, history — or None if the token is invalid.
    """
    valid_tok, fields = verify_token(token)
    if not valid_tok:
        return None
    ticket = record.get_ticket(fields["txn_id"])
    return ticket
