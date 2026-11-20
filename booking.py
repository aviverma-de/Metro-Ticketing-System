"""
Booking Automata Definitions
----------------------------
Implements:
1. Standard Booking DFA (frozen contract table)
2. Regex definitions (handling Issue A: single confirm vs double confirm)

Educational, strictly typed, standard library only.
"""

import re
from typing import Dict, List, Tuple, Union
from automata import DFA, TraceList

# ---------------------------------------------------------------------------
# 1. Booking DFA (Frozen Shared Contract)
# ---------------------------------------------------------------------------

BOOKING_STATES: List[str] = ["q0", "q1", "q2", "q3", "q4", "q5", "q6", "qd"]
BOOKING_ALPHABET: List[str] = ["src", "dst", "confirm", "pay_ok", "pay_fail", "gen", "cancel"]
BOOKING_START_STATE: str = "q0"
BOOKING_ACCEPTING_STATES: List[str] = ["q6"]
BOOKING_DEAD_STATE: str = "qd"

BOOKING_TRANSITIONS: Dict[Tuple[str, str], str] = {}

# Initialize all transitions to qd
for st in BOOKING_STATES:
    for sym in BOOKING_ALPHABET:
        BOOKING_TRANSITIONS[(st, sym)] = "qd"

# Specific transitions according to contract table:
# q0: src -> q1, cancel -> q0
BOOKING_TRANSITIONS[("q0", "src")] = "q1"
BOOKING_TRANSITIONS[("q0", "cancel")] = "q0"

# q1: src -> q1, dst -> q2, cancel -> q0
BOOKING_TRANSITIONS[("q1", "src")] = "q1"
BOOKING_TRANSITIONS[("q1", "dst")] = "q2"
BOOKING_TRANSITIONS[("q1", "cancel")] = "q0"

# q2: src -> q1, dst -> q2, confirm -> q3, cancel -> q0
BOOKING_TRANSITIONS[("q2", "src")] = "q1"
BOOKING_TRANSITIONS[("q2", "dst")] = "q2"
BOOKING_TRANSITIONS[("q2", "confirm")] = "q3"
BOOKING_TRANSITIONS[("q2", "cancel")] = "q0"

# q3: confirm -> q4, cancel -> q0
BOOKING_TRANSITIONS[("q3", "confirm")] = "q4"
BOOKING_TRANSITIONS[("q3", "cancel")] = "q0"

# q4: pay_ok -> q5, pay_fail -> q4, cancel -> q0
BOOKING_TRANSITIONS[("q4", "pay_ok")] = "q5"
BOOKING_TRANSITIONS[("q4", "pay_fail")] = "q4"
BOOKING_TRANSITIONS[("q4", "cancel")] = "q0"

# q5: gen -> q6
BOOKING_TRANSITIONS[("q5", "gen")] = "q6"

# q6 & qd loop to qd (already initialized)

# Pre-built Booking DFA
BOOKING_DFA = DFA(
    states=BOOKING_STATES,
    alphabet=BOOKING_ALPHABET,
    transitions=BOOKING_TRANSITIONS,
    start_state=BOOKING_START_STATE,
    final_states=BOOKING_ACCEPTING_STATES,
    dead_state=BOOKING_DEAD_STATE,
)

# ---------------------------------------------------------------------------
# 2. Regular Expressions (Issue A Handling)
# ---------------------------------------------------------------------------

# As written in the README (Notice: contains only one confirm)
BOOKING_REGEX_AS_WRITTEN: str = "src (src | dst)* dst confirm pay_fail* pay_ok gen"

# Corrected regex matching the DFA table (q2 -> confirm -> q3 -> confirm -> q4)
BOOKING_REGEX_CORRECTED: str = "src (src | dst)* dst confirm confirm pay_fail* pay_ok gen"

# Compiled token matchers (sequences excluding cancel)
_BOOKING_RE_WRITTEN = re.compile(
    r"^src\s+(?:(?:src|dst)\s+)*dst\s+confirm\s+(?:pay_fail\s+)*pay_ok\s+gen$"
)
_BOOKING_RE_CORRECTED = re.compile(
    r"^src\s+(?:(?:src|dst)\s+)*dst\s+confirm\s+confirm\s+(?:pay_fail\s+)*pay_ok\s+gen$"
)


def check_booking_regex(sequence: Union[str, List[str]], corrected: bool = False) -> bool:
    """
    Checks if a sequence matches the booking regex.
    Note: Cancel is excluded from regex comparisons because the regex models
    only successful ticket purchases without abortion/reset.

    - If corrected=False: checks against README regex as written (1 confirm).
    - If corrected=True: checks against corrected regex (2 confirms).
    """
    if isinstance(sequence, str):
        tokens = sequence.split()
    else:
        tokens = list(sequence)

    seq_str = " ".join(tokens)
    pattern = _BOOKING_RE_CORRECTED if corrected else _BOOKING_RE_WRITTEN
    return bool(pattern.match(seq_str))


# ---------------------------------------------------------------------------
# 3. Public Functions for Person 3 and Integration
# ---------------------------------------------------------------------------


def step(state: str, symbol: str) -> str:
    """Takes one step on the Booking DFA."""
    return BOOKING_DFA.step(state, symbol)


def run(sequence: Union[str, List[str]]) -> Tuple[bool, TraceList]:
    """Runs a sequence of symbols on the Booking DFA. Returns (accepted, trace)."""
    return BOOKING_DFA.run(sequence)


def get_transition_table() -> List[Dict[str, str]]:
    """Returns the Booking DFA transition table as plain rows for Streamlit."""
    return BOOKING_DFA.get_transition_table()


def get_booking_dfa() -> DFA:
    """Returns the pre-configured Booking DFA instance."""
    return BOOKING_DFA