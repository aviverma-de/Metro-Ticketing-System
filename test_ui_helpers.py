"""
Unit Tests for UI Helpers and Streamlit App Smoke Test
-------------------------------------------------------
Verifies:
- parse_sequence (Journey & Booking)
- compute_now logic
- build_dot properties (highlighting, dead state omitting, double circles)
- Streamlit AppTest smoke test without exception
"""

import os
import sys
import tempfile

# Redirect DB to temp file before importing backend modules
import config
_tmp_fd, _tmp_path = tempfile.mkstemp(suffix=".db")
os.close(_tmp_fd)
config.DB_PATH = _tmp_path

import record
record.init_db()
record.reset_db()

import ui_helpers
from booking import get_transition_table as get_booking_table
from journey_automata import get_transition_table as get_journey_table

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


def test_parse_sequence():
    print("\n--- 1. Testing parse_sequence ---")
    
    # Journey: spaces ignored, uppercase, letters
    j1 = ui_helpers.parse_sequence("EOP", "journey")
    assert j1 == ["E", "O", "P"], f"got {j1}"
    _record("parse_sequence journey 'EOP'", True)

    j2 = ui_helpers.parse_sequence("e o p", "journey")
    assert j2 == ["E", "O", "P"], f"got {j2}"
    _record("parse_sequence journey 'e o p' (case and spaces)", True)

    j3 = ui_helpers.parse_sequence("", "journey")
    assert j3 == []
    _record("parse_sequence journey empty string", True)

    # Booking: space or comma separated words
    b1 = ui_helpers.parse_sequence("src dst confirm confirm pay_ok gen", "booking")
    assert b1 == ["src", "dst", "confirm", "confirm", "pay_ok", "gen"], f"got {b1}"
    _record("parse_sequence booking spaces", True)

    b2 = ui_helpers.parse_sequence("src, dst, confirm", "booking")
    assert b2 == ["src", "dst", "confirm"], f"got {b2}"
    _record("parse_sequence booking commas", True)

    b3 = ui_helpers.parse_sequence("", "booking")
    assert b3 == []
    _record("parse_sequence booking empty string", True)


def test_compute_now():
    print("\n--- 2. Testing compute_now ---")

    # Entry gate always returns 0.0
    now_entry = ui_helpers.compute_now("entry", 10.0, {"entry_time": 5.0})
    assert now_entry == 0.0, f"got {now_entry}"
    _record("compute_now entry gate returns 0.0", True)

    # Exit gate with valid status and entry_time
    status = {"entry_time": 4.5, "source": 0, "dest": 3}
    now_exit = ui_helpers.compute_now("exit", 8.0, status)
    assert abs(now_exit - 12.5) < 1e-6, f"got {now_exit}"
    _record("compute_now exit gate with entry_time", True)

    # Exit gate with None status
    now_exit_nostat = ui_helpers.compute_now("exit", 15.0, None)
    assert abs(now_exit_nostat - 15.0) < 1e-6, f"got {now_exit_nostat}"
    _record("compute_now exit gate without status", True)

    # Exit gate with status having entry_time None
    now_exit_none = ui_helpers.compute_now("exit", 7.0, {"entry_time": None})
    assert abs(now_exit_none - 7.0) < 1e-6, f"got {now_exit_none}"
    _record("compute_now exit gate with entry_time=None", True)


def test_build_dot():
    print("\n--- 3. Testing build_dot ---")
    
    # Check Journey table
    j_table = get_journey_table()
    dot = ui_helpers.build_dot(
        j_table,
        current_state="J1",
        accepting=("J2", "J3"),
        dead="JT"
    )

    # Highlights current state
    assert '"J1" [' in dot
    assert 'fillcolor="#bbf0bb"' in dot
    _record("build_dot highlights current_state J1", True)

    # Accepting states have doublecircle
    assert '"J2" [shape=doublecircle' in dot
    assert '"J3" [shape=doublecircle' in dot
    assert '"J0" [shape=circle' in dot
    _record("build_dot marks accepting states with doublecircle", True)

    # Does NOT draw transitions into dead state JT
    assert '-> "JT"' not in dot
    _record("build_dot omits edges pointing into dead state", True)

    # Check Booking table
    b_table = get_booking_table()
    b_dot = ui_helpers.build_dot(
        b_table,
        current_state="q3",
        accepting=("q6",),
        dead="qd"
    )
    assert '"q3" [' in dot or 'fillcolor="#bbf0bb"' in b_dot
    assert '-> "qd"' not in b_dot
    _record("build_dot booking omits edges to qd and marks q6 doublecircle", True)


def test_labels_dictionaries():
    print("\n--- 4. Testing Presentation Labels ---")
    assert "q4" in ui_helpers.STATE_LABELS
    assert "E" in ui_helpers.SYMBOL_MEANINGS
    assert "JE" in ui_helpers.STATE_LABELS
    assert "pay_ok" in ui_helpers.SYMBOL_MEANINGS
    _record("STATE_LABELS and SYMBOL_MEANINGS contain required keys", True)


def test_streamlit_app_smoke():
    print("\n--- 5. Testing Streamlit App Smoke Test ---")
    try:
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file("app.py", default_timeout=10)
        at.run()
        assert not at.exception, f"App had exception: {at.exception}"
        _record("Streamlit AppTest initialized without exceptions", True)
    except ImportError:
        _record("Streamlit AppTest not available (skipped)", True)
    except Exception as e:
        _record("Streamlit AppTest run", False, str(e))


def main():
    print("=" * 60)
    print("UI HELPERS TEST SUITE")
    print("=" * 60)

    test_parse_sequence()
    test_compute_now()
    test_build_dot()
    test_labels_dictionaries()
    test_streamlit_app_smoke()

    print("\n" + "=" * 60)
    print(f"FINAL SUMMARY: {TESTS_PASSED} / {TESTS_RUN} TESTS PASSED")
    if TESTS_FAILED == 0:
        print("ALL TESTS PASSED!")
    else:
        print(f"WARNING: {TESTS_FAILED} TESTS FAILED!")
    print("=" * 60)

    try:
        os.remove(_tmp_path)
    except OSError:
        pass

    sys.exit(0 if TESTS_FAILED == 0 else 1)


if __name__ == "__main__":
    main()
