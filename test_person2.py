"""
Person 2 Test Suite — Metro Ticketing & Journey Validation
-----------------------------------------------------------
Plain assert-based tests. Works with both:
  python test_person2.py    (main runner prints PASS/FAIL per test)
  pytest test_person2.py    (pytest discovers test_* functions)

Uses a temporary DB file so the real metro.db is never touched.
"""

import os
import sys
import tempfile

# --- Setup: redirect DB to a temp file BEFORE importing our modules ---
import config

_tmp_fd, _tmp_path = tempfile.mkstemp(suffix=".db")
os.close(_tmp_fd)
config.DB_PATH = _tmp_path

import record
from stations import distance, fare, fare_for_distance, excess_fare, check_payment
from token_utils import create_token, verify_token
from journey import classify, process_scan, pay_excess, get_ticket_status
from journey_automata import JOURNEY_DFA


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

TESTS_RUN = 0
TESTS_PASSED = 0
TESTS_FAILED = 0


def _record(name: str, passed: bool, detail: str = ""):
    global TESTS_RUN, TESTS_PASSED, TESTS_FAILED
    TESTS_RUN += 1
    if passed:
        TESTS_PASSED += 1
        print(f"  [PASS] {name}")
    else:
        TESTS_FAILED += 1
        print(f"  [FAIL] {name}: {detail}")


def _fresh_db():
    """Reset the DB for a clean test."""
    record.reset_db()


def _enter(token, station, now):
    """Shortcut: enter at station with now."""
    return process_scan(token, station, "entry", now)


def _exit(token, station, now):
    """Shortcut: exit at station with now."""
    return process_scan(token, station, "exit", now)


def _check_history_consistency(token, test_label):
    """
    After a scenario, the ticket's history string must give the same
    accept/reject result in JOURNEY_DFA.run(history) as the final state implies.
    """
    status = get_ticket_status(token)
    if status is None:
        return  # can't check invalid tokens
    history = status["history"]
    final_state = status["state"]
    accepted, trace = JOURNEY_DFA.run(history) if history else (False, None)
    dfa_accepts = final_state in ("J2", "J3")
    ok = (accepted == dfa_accepts)
    _record(f"  History consistency: '{history}' -> DFA={accepted}, state={final_state} ({test_label})", ok,
            f"history='{history}', accepted={accepted}, final_state={final_state}")


# ---------------------------------------------------------------------------
# Fare / distance tests
# ---------------------------------------------------------------------------

def test_fare_slabs():
    print("\n--- Fare Slabs ---")
    # 1-2 stops -> 10
    assert fare_for_distance(1) == 10
    assert fare_for_distance(2) == 10
    _record("1-2 stops -> Rs 10", True)

    # 3-5 stops -> 20
    assert fare_for_distance(3) == 20
    assert fare_for_distance(4) == 20
    assert fare_for_distance(5) == 20
    _record("3-5 stops -> Rs 20", True)

    # 6-7 stops -> 30
    assert fare_for_distance(6) == 30
    assert fare_for_distance(7) == 30
    _record("6-7 stops -> Rs 30", True)

    # 0 stops -> 0
    assert fare_for_distance(0) == 0
    _record("0 stops -> Rs 0", True)

    # fare(3, 3) raises ValueError
    try:
        fare(3, 3)
        _record("fare(3, 3) raises ValueError", False, "No exception raised")
    except ValueError:
        _record("fare(3, 3) raises ValueError", True)


# ---------------------------------------------------------------------------
# Token tests
# ---------------------------------------------------------------------------

def test_token_verify():
    print("\n--- Token Create & Verify ---")
    _fresh_db()

    tok = create_token(3, 7)
    ok, fields = verify_token(tok)
    assert ok is True
    assert fields["source"] == 3
    assert fields["dest"] == 7
    _record("verify_token accepts what create_token makes", True)

    # Reject any single changed character
    for i in range(len(tok)):
        c = tok[i]
        # Change one character
        new_c = chr(ord(c) + 1) if c != 'z' else 'a'
        tampered = tok[:i] + new_c + tok[i+1:]
        if tampered == tok:
            continue
        ok_t, _ = verify_token(tampered)
        if ok_t:
            _record(f"Reject tampered token (pos {i})", False, f"tampered={tampered}")
            return
    _record("Reject any single changed character", True)


# ---------------------------------------------------------------------------
# Normal journey: ticket 0 -> 3 (paid Rs 20)
# ---------------------------------------------------------------------------

def test_normal_exit_at_destination():
    """Exit at station 3, now=8 -> symbol D, state J2, gate OPEN."""
    print("\n--- Normal Exit at Destination ---")
    _fresh_db()
    tok = create_token(0, 3)
    _enter(tok, 0, 0)
    r = _exit(tok, 3, 8)
    assert r["symbol"] == "D"
    assert r["new_state"] == "J2"
    assert r["gate"] == "OPEN"
    _record("Exit at dest: D, J2, OPEN", True)
    _check_history_consistency(tok, "normal exit")


def test_early_exit():
    """Exit at station 2, now=5 -> X, J3, OPEN."""
    print("\n--- Early Exit ---")
    _fresh_db()
    tok = create_token(0, 3)
    _enter(tok, 0, 0)
    r = _exit(tok, 2, 5)
    assert r["symbol"] == "X"
    assert r["new_state"] == "J3"
    assert r["gate"] == "OPEN"
    _record("Early exit at 2: X, J3, OPEN", True)
    _check_history_consistency(tok, "early exit")


def test_excess_fare_then_pay():
    """Exit at station 6, now=15 -> O, amount 10, JE, LOCKED. Then pay_excess -> J2, OPEN."""
    print("\n--- Excess Fare Then Pay ---")
    _fresh_db()
    tok = create_token(0, 3)
    _enter(tok, 0, 0)
    r = _exit(tok, 6, 15)
    assert r["symbol"] == "O", f"expected O, got {r['symbol']}"
    assert r["amount"] == 10, f"expected amount 10, got {r['amount']}"
    assert r["new_state"] == "JE"
    assert r["gate"] == "LOCKED"
    _record("Excess at 6: O, amount=10, JE, LOCKED", True)

    # Pay excess
    p = pay_excess(tok)
    assert p["new_state"] == "J2"
    assert p["gate"] == "OPEN"
    assert p["amount"] == 10
    _record("pay_excess: J2, OPEN, amount=10", True)
    _check_history_consistency(tok, "excess then pay")


def test_excess_fare_double_exit_then_pay():
    """Exit at 6 twice before paying -> JE stays, LOCKED. Then pay_excess -> J2."""
    print("\n--- Double Excess Exit Then Pay ---")
    _fresh_db()
    tok = create_token(0, 3)
    _enter(tok, 0, 0)
    r1 = _exit(tok, 6, 15)
    assert r1["symbol"] == "O"
    assert r1["new_state"] == "JE"
    _record("First exit at 6: O, JE", True)

    # Second exit scan while in JE
    r2 = _exit(tok, 6, 16)
    assert r2["new_state"] == "JE", f"expected JE, got {r2['new_state']}"
    assert r2["gate"] == "LOCKED"
    _record("Second exit at 6: JE stays, LOCKED", True)

    # Pay
    p = pay_excess(tok)
    assert p["new_state"] == "J2"
    assert p["gate"] == "OPEN"
    _record("pay_excess after double exit: J2, OPEN", True)
    _check_history_consistency(tok, "double excess then pay")


def test_overtime_then_pay():
    """Exit at station 0, now=20 -> T, amount 20, JE, LOCKED. Then pay_excess -> J2."""
    print("\n--- Overtime Then Pay ---")
    _fresh_db()
    tok = create_token(0, 3)
    _enter(tok, 0, 0)
    r = _exit(tok, 0, 20)
    assert r["symbol"] == "T", f"expected T, got {r['symbol']}"
    assert r["amount"] == 20
    assert r["new_state"] == "JE"
    assert r["gate"] == "LOCKED"
    _record("Overtime at 0: T, amount=20, JE, LOCKED", True)

    p = pay_excess(tok)
    assert p["new_state"] == "J2"
    assert p["gate"] == "OPEN"
    _record("pay_excess after overtime: J2, OPEN", True)
    _check_history_consistency(tok, "overtime then pay")


def test_overtime_at_destination():
    """Exit at station 3, now=25 -> T (too long, even at the destination)."""
    print("\n--- Overtime at Destination ---")
    _fresh_db()
    tok = create_token(0, 3)
    _enter(tok, 0, 0)
    r = _exit(tok, 3, 25)
    assert r["symbol"] == "T", f"expected T, got {r['symbol']}"
    _record("Overtime at dest: T (even at correct station)", True)
    _check_history_consistency(tok, "overtime at dest")


def test_exit_at_same_station():
    """Exit at station 0, now=1 -> X (entered and left at once), OPEN."""
    print("\n--- Exit at Same Station (Quick) ---")
    _fresh_db()
    tok = create_token(0, 3)
    _enter(tok, 0, 0)
    r = _exit(tok, 0, 1)
    # distance(0,0) = 0 => fare_for_distance(0) = 0 <= paid_fare 20 => X
    assert r["symbol"] == "X", f"expected X, got {r['symbol']}"
    assert r["gate"] == "OPEN"
    _record("Exit same station: X, OPEN", True)
    _check_history_consistency(tok, "exit same station")


def test_exit_same_fare_slab():
    """Exit at station 4, now=10 -> X (same Rs 20 slab, nothing owed)."""
    print("\n--- Exit Same Fare Slab ---")
    _fresh_db()
    tok = create_token(0, 3)
    _enter(tok, 0, 0)
    r = _exit(tok, 4, 10)
    # distance(0,4) = 4 => fare_for_distance(4) = 20 => 20 <= 20 => X
    assert r["symbol"] == "X", f"expected X, got {r['symbol']}"
    assert r["gate"] == "OPEN"
    _record("Exit at 4 (same slab): X, OPEN", True)
    _check_history_consistency(tok, "same fare slab")


# ---------------------------------------------------------------------------
# Wrap-around ticket 6 -> 1 (3 stops, Rs 20)
# ---------------------------------------------------------------------------

def test_wraparound_normal():
    """Ticket 6->1 (3 stops): exit at 1, now=8 -> D."""
    print("\n--- Wrap-around Normal ---")
    _fresh_db()
    tok = create_token(6, 1)
    _enter(tok, 6, 0)
    r = _exit(tok, 1, 8)
    assert r["symbol"] == "D"
    assert r["new_state"] == "J2"
    assert r["gate"] == "OPEN"
    _record("Wrap 6->1 exit at 1: D, J2, OPEN", True)
    _check_history_consistency(tok, "wraparound normal")


def test_wraparound_early():
    """Ticket 6->1: fresh one, exit at 7, now=3 -> X."""
    print("\n--- Wrap-around Early Exit ---")
    _fresh_db()
    tok = create_token(6, 1)
    _enter(tok, 6, 0)
    r = _exit(tok, 7, 3)
    # distance(6,7) = 1 => fare = 10 <= paid_fare 20 => X
    assert r["symbol"] == "X", f"expected X, got {r['symbol']}"
    assert r["gate"] == "OPEN"
    _record("Wrap 6->1 exit at 7: X, OPEN", True)
    _check_history_consistency(tok, "wraparound early")


# ---------------------------------------------------------------------------
# Misuse tests
# ---------------------------------------------------------------------------

def test_edited_token():
    """Edited token (changed destination digits) -> W, valid False, LOCKED, record untouched."""
    print("\n--- Edited Token ---")
    _fresh_db()
    tok = create_token(0, 3)
    original_status = get_ticket_status(tok)

    # Tamper: change the destination digits in the payload
    parts = tok.rsplit(".", 1)
    payload = parts[0]
    # Change |03| to |05|
    tampered_payload = payload.replace("|03|", "|05|")
    tampered_tok = tampered_payload + "." + parts[1]

    r = process_scan(tampered_tok, 0, "entry", 0)
    assert r["symbol"] == "W"
    assert r["valid"] is False
    assert r["gate"] == "LOCKED"
    _record("Edited token: W, valid=False, LOCKED", True)

    # Record untouched
    after_status = get_ticket_status(tok)
    assert after_status["state"] == original_status["state"]
    assert after_status["history"] == original_status["history"]
    _record("Record untouched after edited token", True)


def test_entry_wrong_station():
    """Entry at the wrong station -> W, ticket goes to JT."""
    print("\n--- Entry Wrong Station ---")
    _fresh_db()
    tok = create_token(0, 3)
    r = _enter(tok, 5, 0)  # wrong station
    assert r["symbol"] == "W"
    assert r["new_state"] == "JT"
    _record("Entry wrong station: W, JT", True)
    _check_history_consistency(tok, "wrong station entry")


def test_double_entry():
    """Second entry scan on a ticket already inside -> W."""
    print("\n--- Double Entry ---")
    _fresh_db()
    tok = create_token(0, 3)
    _enter(tok, 0, 0)
    r = _enter(tok, 0, 1)
    assert r["symbol"] == "W"
    assert r["new_state"] == "JT"
    _record("Double entry: W, JT", True)
    _check_history_consistency(tok, "double entry")


def test_exit_without_entry():
    """Exit scan on a ticket that never entered -> W."""
    print("\n--- Exit Without Entry ---")
    _fresh_db()
    tok = create_token(0, 3)
    r = _exit(tok, 3, 5)
    assert r["symbol"] == "W"
    assert r["new_state"] == "JT"
    _record("Exit without entry: W, JT", True)
    _check_history_consistency(tok, "exit without entry")


def test_scan_after_exit():
    """Any scan after a normal exit -> R."""
    print("\n--- Scan After Exit ---")
    _fresh_db()
    tok = create_token(0, 3)
    _enter(tok, 0, 0)
    _exit(tok, 3, 8)  # now in J2
    # Try another entry
    r = _enter(tok, 0, 10)
    assert r["symbol"] == "R"
    _record("Entry after exit: R", True)
    # Try another exit
    _fresh_db()
    tok2 = create_token(0, 3)
    _enter(tok2, 0, 0)
    _exit(tok2, 3, 8)
    r2 = _exit(tok2, 3, 10)
    assert r2["symbol"] == "R"
    _record("Exit after exit: R", True)
    _check_history_consistency(tok2, "scan after exit")


def test_garbage_token():
    """Garbage string as token -> W, no exception."""
    print("\n--- Garbage Token ---")
    _fresh_db()
    r = process_scan("this-is-garbage!!!", 0, "entry", 0)
    assert r["symbol"] == "W"
    assert r["valid"] is False
    _record("Garbage token: W, no exception", True)


def test_pay_excess_wrong_state():
    """pay_excess on a ticket in J1 -> state unchanged, 'No charge pending'."""
    print("\n--- Pay Excess Wrong State ---")
    _fresh_db()
    tok = create_token(0, 3)
    _enter(tok, 0, 0)
    status_before = get_ticket_status(tok)
    assert status_before["state"] == "J1"

    p = pay_excess(tok)
    assert p["message"] == "No charge pending"
    assert p["gate"] == "LOCKED"

    status_after = get_ticket_status(tok)
    assert status_after["state"] == "J1", f"state changed to {status_after['state']}"
    _record("pay_excess in J1: state unchanged, 'No charge pending'", True)


# ---------------------------------------------------------------------------
# check_payment tests
# ---------------------------------------------------------------------------

def test_check_payment():
    print("\n--- check_payment ---")
    sym, change = check_payment(25, 20)
    assert sym == "pay_ok" and change == 5
    _record("check_payment(25, 20) -> pay_ok, change=5", True)

    sym2, change2 = check_payment(10, 20)
    assert sym2 == "pay_fail" and change2 == 0
    _record("check_payment(10, 20) -> pay_fail, change=0", True)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

ALL_TESTS = [
    test_fare_slabs,
    test_token_verify,
    test_normal_exit_at_destination,
    test_early_exit,
    test_excess_fare_then_pay,
    test_excess_fare_double_exit_then_pay,
    test_overtime_then_pay,
    test_overtime_at_destination,
    test_exit_at_same_station,
    test_exit_same_fare_slab,
    test_wraparound_normal,
    test_wraparound_early,
    test_edited_token,
    test_entry_wrong_station,
    test_double_entry,
    test_exit_without_entry,
    test_scan_after_exit,
    test_garbage_token,
    test_pay_excess_wrong_state,
    test_check_payment,
]


def main():
    print("=" * 60)
    print("PERSON 2: METRO TICKETING & JOURNEY VALIDATION TEST SUITE")
    print("=" * 60)

    for test_fn in ALL_TESTS:
        try:
            test_fn()
        except AssertionError as e:
            global TESTS_RUN, TESTS_FAILED
            TESTS_RUN += 1
            TESTS_FAILED += 1
            print(f"  [FAIL] {test_fn.__name__}: AssertionError: {e}")
        except Exception as e:
            TESTS_RUN += 1
            TESTS_FAILED += 1
            print(f"  [FAIL] {test_fn.__name__}: Exception: {e}")

    print("\n" + "=" * 60)
    print(f"FINAL SUMMARY: {TESTS_PASSED} / {TESTS_RUN} TESTS PASSED")
    if TESTS_FAILED == 0:
        print("ALL TESTS PASSED!")
    else:
        print(f"WARNING: {TESTS_FAILED} TESTS FAILED!")
    print("=" * 60)

    # Clean up temp file
    try:
        os.remove(_tmp_path)
    except OSError:
        pass

    sys.exit(0 if TESTS_FAILED == 0 else 1)


if __name__ == "__main__":
    main()
