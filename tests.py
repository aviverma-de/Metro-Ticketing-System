"""
Automata Engine Test Suite
--------------------------
Comprehensive unit and integration test suite verifying:
- Task 1 & 2: Journey DFA (all 10 canonical sequences + verdict & reasons)
- Task 2: Booking DFA (normal path, cancellation, step skips, Issue A detection)
- Task 2: Regex vs DFA Cross-Validation (exhaustive + targeted length checks)
- Task 3: Moore and Mealy Gate Machines (gate outputs for ED, EX, EOP, ETP, EE)
- Task 4: Payment NFA & Subset Construction (hand-derived table + equivalence)
- Task 5: DFA Minimization (table-filling 8 -> 7 states, round history, equivalence)

Exits with code 0 on success.
"""

import sys
import itertools
from typing import List, Tuple, Any

from automata import DFA, NFA, MooreMachine, MealyMachine, subset_construction, minimize_dfa_table_filling
from journey_automata import (
    JOURNEY_DFA,
    JOURNEY_MOORE,
    JOURNEY_MEALY,
    JOURNEY_REGEX,
    check_journey_regex,
    get_transition_table as get_journey_transition_table,
    get_moore_table,
    get_mealy_table,
)
from booking import (
    BOOKING_DFA,
    REDUNDANT_BOOKING_DFA,
    PAYMENT_NFA,
    BOOKING_REGEX_AS_WRITTEN,
    BOOKING_REGEX_CORRECTED,
    check_booking_regex,
    get_subset_steps,
    get_minimization_steps,
    get_transition_table as get_booking_transition_table,
)

# Test tally counters
TESTS_RUN = 0
TESTS_PASSED = 0
TESTS_FAILED = 0


def record_result(test_name: str, passed: bool, detail: str = "") -> None:
    global TESTS_RUN, TESTS_PASSED, TESTS_FAILED
    TESTS_RUN += 1
    if passed:
        TESTS_PASSED += 1
        print(f"  [PASS] {test_name}")
    else:
        TESTS_FAILED += 1
        print(f"  [FAIL] {test_name}: {detail}")


def test_journey_dfa_ten_sequences() -> None:
    print("\n--- 1. Journey DFA: 10 Contract Sequences ---")

    # (sequence, expected_verdict, expected_final_state, expected_reason_keyword)
    test_cases: List[Tuple[str, bool, str, str]] = [
        ("ED", True, "J2", "Accepted"),
        ("EX", True, "J3", "Accepted"),
        ("EOP", True, "J2", "Accepted"),
        ("ETP", True, "J2", "Accepted"),
        ("EOOP", True, "J2", "Accepted"),
        ("EO", False, "JE", "ended in a non-accepting state"),
        ("ET", False, "JE", "ended in a non-accepting state"),
        ("EE", False, "JT", "trap state"),
        ("D", False, "JT", "trap state"),
        ("EDR", False, "JT", "trap state"),
    ]

    for seq, exp_verdict, exp_final, exp_reason_kw in test_cases:
        accepted, trace = JOURNEY_DFA.run(seq)
        final_st = trace.final_state
        reason = trace.reason

        passed_verdict = (accepted == exp_verdict)
        passed_final = (final_st == exp_final)
        passed_reason = (exp_reason_kw.lower() in reason.lower())

        all_ok = passed_verdict and passed_final and passed_reason
        detail = (
            f"Got verdict={accepted} (exp {exp_verdict}), "
            f"final={final_st} (exp {exp_final}), "
            f"reason='{reason}' (expected keyword '{exp_reason_kw}')"
        )
        record_result(f"Journey Sequence '{seq}'", all_ok, detail)


def test_booking_dfa() -> None:
    print("\n--- 2. Booking DFA Execution ---")

    # 1. Normal successful booking with two confirms and pay retries
    normal_seq = ["src", "dst", "confirm", "confirm", "pay_fail", "pay_fail", "pay_ok", "gen"]
    acc, trace = BOOKING_DFA.run(normal_seq)
    record_result(
        "Booking DFA: Normal booking with retries",
        acc and trace.final_state == "q6",
        f"final_state={trace.final_state}, accepted={acc}",
    )

    # 2. Cancel returning to q0 from q1, q2, q3, q4
    cancel_tests = [
        ("Cancel from q1", ["src", "cancel"]),
        ("Cancel from q2", ["src", "dst", "cancel"]),
        ("Cancel from q3", ["src", "dst", "confirm", "cancel"]),
        ("Cancel from q4", ["src", "dst", "confirm", "confirm", "cancel"]),
    ]
    for label, seq in cancel_tests:
        acc, trace = BOOKING_DFA.run(seq)
        record_result(
            f"Booking DFA: {label}",
            (not acc) and trace.final_state == "q0",
            f"final_state={trace.final_state}, accepted={acc}",
        )

    # 3. Skipping steps -> dead state (qd)
    skip_seq = ["src", "confirm"]
    acc, trace = BOOKING_DFA.run(skip_seq)
    record_result(
        "Booking DFA: Skipping steps (src -> confirm) goes to qd",
        (not acc) and trace.final_state == "qd" and "dead state" in trace.reason.lower(),
        f"final_state={trace.final_state}, reason={trace.reason}",
    )

    # 4. Generating ticket before payment -> dead state (qd)
    early_gen = ["src", "dst", "confirm", "confirm", "gen"]
    acc, trace = BOOKING_DFA.run(early_gen)
    record_result(
        "Booking DFA: Generate ticket before payment goes to qd",
        (not acc) and trace.final_state == "qd",
        f"final_state={trace.final_state}",
    )

    # 5. Single confirm attempt (Issue A demonstration)
    single_confirm_seq = ["src", "dst", "confirm", "pay_ok", "gen"]
    acc, trace = BOOKING_DFA.run(single_confirm_seq)
    record_result(
        "Booking DFA: Single confirm attempt correctly rejected by table",
        (not acc) and trace.final_state == "qd",
        f"final_state={trace.final_state}",
    )


def test_moore_and_mealy_machines() -> None:
    print("\n--- 3. Moore and Mealy Gate Machines ---")

    test_seqs = ["ED", "EX", "EOP", "ETP", "EE"]

    expected_moore = {
        "ED": ["Entry gate open", "Exit gate open, Thank you"],
        "EX": ["Entry gate open", "Exit gate open, Early exit recorded"],
        "EOP": [
            "Entry gate open",
            "Gate LOCKED, show Pay excess ₹ or Pay over-time charge ₹",
            "Exit gate open, Thank you",
        ],
        "ETP": [
            "Entry gate open",
            "Gate LOCKED, show Pay excess ₹ or Pay over-time charge ₹",
            "Exit gate open, Thank you",
        ],
        "EE": ["Entry gate open", "Gate LOCKED, alarm"],
    }

    expected_mealy = {
        "ED": ["Open entry gate, record entry time", "Open exit gate"],
        "EX": ["Open entry gate, record entry time", "Open exit gate, record early exit"],
        "EOP": [
            "Open entry gate, record entry time",
            "Lock gate, show excess fare",
            "Open exit gate",
        ],
        "ETP": [
            "Open entry gate, record entry time",
            "Lock gate, show over-time charge",
            "Open exit gate",
        ],
        "EE": ["Open entry gate, record entry time", "Lock gate, alarm"],
    }

    for seq in test_seqs:
        moore_out = JOURNEY_MOORE.run(seq)
        mealy_out = JOURNEY_MEALY.run(seq)

        # Equal length check (one output per symbol)
        len_ok = len(moore_out) == len(seq) and len(mealy_out) == len(seq)
        record_result(
            f"Gate Machines: Output lengths match input length for '{seq}'",
            len_ok,
            f"moore={len(moore_out)}, mealy={len(mealy_out)}, seq={len(seq)}",
        )

        # Moore output accuracy
        moore_ok = (moore_out == expected_moore[seq])
        record_result(
            f"Moore outputs for '{seq}'",
            moore_ok,
            f"got {moore_out}, exp {expected_moore[seq]}",
        )

        # Mealy output accuracy
        mealy_ok = (mealy_out == expected_mealy[seq])
        record_result(
            f"Mealy outputs for '{seq}'",
            mealy_ok,
            f"got {mealy_out}, exp {expected_mealy[seq]}",
        )


def test_payment_nfa_and_subset_construction() -> None:
    print("\n--- 4. NFA & Subset Construction ---")

    # 1. Inspect subset steps
    steps = get_subset_steps()
    dfa: DFA = steps["dfa"]
    name_to_subset = steps["name_to_subset"]

    # Verify initial state subset D0 = {N0, N_card, N_cash, N_upi}
    d0_subset = sorted(name_to_subset["D0"])
    exp_d0 = ["N0", "N_card", "N_cash", "N_upi"]
    record_result(
        "Subset construction: D0 epsilon-closure matches hand derivation",
        d0_subset == exp_d0,
        f"got {d0_subset}, exp {exp_d0}",
    )

    # Verify D1 subset = {Paid}
    d1_subset = sorted(name_to_subset.get("D1", []))
    exp_d1 = ["Paid"]
    record_result(
        "Subset construction: D1 subset is {Paid} and accepting",
        d1_subset == exp_d1 and dfa.is_accepting("D1"),
        f"got {d1_subset}, accepting={dfa.is_accepting('D1')}",
    )

    # 2. Equivalence test between NFA and resulting DFA across all symbol combos up to length 3
    alphabet = PAYMENT_NFA.alphabet
    all_test_strings = [[]]
    for length in range(1, 4):
        for prod in itertools.product(alphabet, repeat=length):
            all_test_strings.append(list(prod))

    mismatches = 0
    for test_seq in all_test_strings:
        nfa_acc, _ = PAYMENT_NFA.run(test_seq)
        dfa_acc, _ = dfa.run(test_seq)
        if nfa_acc != dfa_acc:
            mismatches += 1

    record_result(
        f"NFA vs DFA Equivalence (all {len(all_test_strings)} strings up to len 3)",
        mismatches == 0,
        f"{mismatches} mismatches found",
    )


def test_dfa_minimization_table_filling() -> None:
    print("\n--- 5. DFA Minimization (Myhill-Nerode Table-Filling) ---")

    step_details = get_minimization_steps()
    before_count = step_details["before_state_count"]
    after_count = step_details["after_state_count"]
    unmarked_pairs = step_details["unmarked_pairs"]
    minimized_dfa: DFA = step_details["minimized_dfa"]

    # 1. State reduction check: strictly 8 -> 7
    count_ok = (before_count == 8 and after_count == 7)
    record_result(
        "Minimization: Redundant Booking DFA reduces from 8 to 7 states",
        count_ok,
        f"before={before_count}, after={after_count}",
    )

    # 2. Exactly one equivalent pair: (PaidCash, PaidUPI)
    exp_unmarked = [("PaidCash", "PaidUPI")]
    pair_ok = (unmarked_pairs == exp_unmarked)
    record_result(
        "Minimization: Exactly (PaidCash, PaidUPI) left unmarked (equivalent)",
        pair_ok,
        f"got {unmarked_pairs}, exp {exp_unmarked}",
    )

    # 3. Equivalence test between redundant DFA and minimized DFA
    sample_sequences = [
        [],
        ["src"],
        ["src", "dst"],
        ["src", "dst", "confirm"],
        ["src", "dst", "confirm", "confirm"],
        ["src", "dst", "confirm", "confirm", "pay_fail"],
        ["src", "dst", "confirm", "confirm", "pay_ok"],
        ["src", "dst", "confirm", "confirm", "pay_ok", "gen"],
        ["src", "cancel"],
        ["src", "dst", "cancel"],
        ["src", "dst", "confirm", "cancel"],
        ["src", "dst", "confirm", "confirm", "pay_fail", "cancel"],
        ["pay_ok"],
        ["gen"],
        ["src", "pay_ok"],
    ]

    mismatches = 0
    for seq in sample_sequences:
        orig_acc, _ = REDUNDANT_BOOKING_DFA.run(seq)
        min_acc, _ = minimized_dfa.run(seq)
        if orig_acc != min_acc:
            mismatches += 1

    record_result(
        f"Minimization Equivalence: original vs minimized across sample sequences",
        mismatches == 0,
        f"{mismatches} mismatches found",
    )


def test_regex_cross_validation() -> None:
    print("\n--- 6. Regex vs DFA Cross-Validation (Issue A Verification) ---")

    # A. Journey DFA vs Regex
    # Test all sequences up to length 4 over all 8 symbols (8^1 + 8^2 + 8^3 + 8^4 = 4680 sequences)
    # plus targeted length 5 and 6 sequences
    journey_syms = JOURNEY_DFA.alphabet
    exhaustive_lengths = [1, 2, 3, 4]
    journey_mismatches = 0
    total_journey_tested = 0

    for L in exhaustive_lengths:
        for seq_tuple in itertools.product(journey_syms, repeat=L):
            total_journey_tested += 1
            seq = "".join(seq_tuple)
            dfa_acc, _ = JOURNEY_DFA.run(seq)
            reg_acc = check_journey_regex(seq)
            if dfa_acc != reg_acc:
                journey_mismatches += 1

    # Targeted length 5 and 6 sequences
    targeted_journey = [
        "EOOOP", "ETTOP", "EOOTP", "ETETP", "EEEEE", "DDDDD",
        "EOOOOP", "ETTETP", "EOPDRW", "EEEEEE", "JJJJJJ"
    ]
    for seq in targeted_journey:
        total_journey_tested += 1
        dfa_acc, _ = JOURNEY_DFA.run(seq)
        reg_acc = check_journey_regex(seq)
        if dfa_acc != reg_acc:
            journey_mismatches += 1

    record_result(
        f"Journey Regex vs DFA Cross-Validation ({total_journey_tested} sequences tested)",
        journey_mismatches == 0,
        f"{journey_mismatches} mismatches found",
    )

    # B. Booking DFA vs Regex (Issue A: Single confirm vs Double confirm)
    # Exclude cancel from comparison
    booking_syms = [s for s in BOOKING_DFA.alphabet if s != "cancel"]

    # Canonical sequence with 2 confirms
    seq_2conf = ["src", "dst", "confirm", "confirm", "pay_ok", "gen"]
    dfa_2conf, _ = BOOKING_DFA.run(seq_2conf)
    reg_2conf_corrected = check_booking_regex(seq_2conf, corrected=True)
    reg_2conf_written = check_booking_regex(seq_2conf, corrected=False)

    record_result(
        "Booking Cross-Validation: 2-confirm sequence matches DFA and corrected regex",
        dfa_2conf is True and reg_2conf_corrected is True,
        f"dfa={dfa_2conf}, corrected_regex={reg_2conf_corrected}",
    )

    record_result(
        "Booking Issue A Detection: 2-confirm sequence fails README regex 'as written'",
        reg_2conf_written is False,
        f"as_written_regex={reg_2conf_written}",
    )

    # Sequence with 1 confirm
    seq_1conf = ["src", "dst", "confirm", "pay_ok", "gen"]
    dfa_1conf, _ = BOOKING_DFA.run(seq_1conf)
    reg_1conf_written = check_booking_regex(seq_1conf, corrected=False)
    reg_1conf_corrected = check_booking_regex(seq_1conf, corrected=True)

    record_result(
        "Booking Issue A Detection: 1-confirm sequence matches README regex but fails DFA table",
        dfa_1conf is False and reg_1conf_written is True and reg_1conf_corrected is False,
        f"dfa={dfa_1conf}, written_regex={reg_1conf_written}, corrected_regex={reg_1conf_corrected}",
    )


def test_plain_data_contract() -> None:
    print("\n--- 7. Person 3 Plain Data Display Contract ---")

    # Verify that every getter returns plain Python data (list, dict, str, int, bool)
    tables = [
        ("Journey Transition Table", get_journey_transition_table()),
        ("Booking Transition Table", get_booking_transition_table()),
        ("Moore Table", get_moore_table()),
        ("Mealy Table", get_mealy_table()),
        ("Subset Display Rows", get_subset_steps()["display_rows"]),
        ("Minimization Display Rows", get_minimization_steps()["display_table"]),
    ]

    for name, data in tables:
        is_plain = isinstance(data, list) and all(isinstance(row, dict) for row in data)
        record_result(f"Plain Data Contract for '{name}'", is_plain, f"type={type(data)}")


def main() -> None:
    print("==========================================================")
    print("PERSON 1 AUTOMATA ENGINE: FORMAL VERIFICATION & TEST SUITE")
    print("==========================================================")

    test_journey_dfa_ten_sequences()
    test_booking_dfa()
    test_moore_and_mealy_machines()
    test_payment_nfa_and_subset_construction()
    test_dfa_minimization_table_filling()
    test_regex_cross_validation()
    test_plain_data_contract()

    print("\n==========================================================")
    print(f"FINAL SUMMARY: {TESTS_PASSED} / {TESTS_RUN} TESTS PASSED")
    if TESTS_FAILED == 0:
        print("ALL TESTS PASSED PERFECTLY!")
        print("==========================================================")
        sys.exit(0)
    else:
        print(f"WARNING: {TESTS_FAILED} TESTS FAILED!")
        print("==========================================================")
        sys.exit(1)


if __name__ == "__main__":
    main()

