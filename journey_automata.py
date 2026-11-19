"""
Journey Automata Definitions (Contract Core)
--------------------------------------------
Implements the Journey DFA and regular expression validation strictly
according to the shared contract.

Module Choice Rationale:
------------------------
This module is isolated as `journey_automata.py` so that Person 2's
`journey.py` (which contains the classifier, HMAC signature checks,
and gate hardware logic) can import the pure theoretical automata
with a clean, zero-dependency one-line import:
    `from journey_automata import JOURNEY_DFA, step`
without circular dependencies or coupling to kiosk or UI code.
"""

import re
from typing import Dict, List, Tuple, Union
from automata import DFA, TraceList

# ---------------------------------------------------------------------------
# 1. State and Symbol Definitions (Frozen Contract)
# ---------------------------------------------------------------------------

JOURNEY_STATES: List[str] = ["J0", "J1", "JE", "J2", "J3", "JT"]
JOURNEY_ALPHABET: List[str] = ["E", "D", "X", "O", "T", "P", "W", "R"]
JOURNEY_START_STATE: str = "J0"
JOURNEY_ACCEPTING_STATES: List[str] = ["J2", "J3"]
JOURNEY_DEAD_STATE: str = "JT"

# ---------------------------------------------------------------------------
# 2. Journey DFA Transition Table
# ---------------------------------------------------------------------------

JOURNEY_TRANSITIONS: Dict[Tuple[str, str], str] = {}

# J0: E -> J1; every other symbol -> JT
for sym in JOURNEY_ALPHABET:
    JOURNEY_TRANSITIONS[("J0", sym)] = "J1" if sym == "E" else "JT"

# J1: D -> J2, X -> J3, O -> JE, T -> JE; E, P, W, R -> JT
for sym in JOURNEY_ALPHABET:
    if sym == "D":
        JOURNEY_TRANSITIONS[("J1", sym)] = "J2"
    elif sym == "X":
        JOURNEY_TRANSITIONS[("J1", sym)] = "J3"
    elif sym in ("O", "T"):
        JOURNEY_TRANSITIONS[("J1", sym)] = "JE"
    else:
        JOURNEY_TRANSITIONS[("J1", sym)] = "JT"

# JE: O -> JE, T -> JE, P -> J2; E, D, X, W, R -> JT
for sym in JOURNEY_ALPHABET:
    if sym in ("O", "T"):
        JOURNEY_TRANSITIONS[("JE", sym)] = "JE"
    elif sym == "P":
        JOURNEY_TRANSITIONS[("JE", sym)] = "J2"
    else:
        JOURNEY_TRANSITIONS[("JE", sym)] = "JT"

# J2: every symbol -> JT (ticket closed after normal exit)
for sym in JOURNEY_ALPHABET:
    JOURNEY_TRANSITIONS[("J2", sym)] = "JT"

# J3: every symbol -> JT (ticket closed after early exit)
for sym in JOURNEY_ALPHABET:
    JOURNEY_TRANSITIONS[("J3", sym)] = "JT"

# JT: every symbol -> JT (trap state loops)
for sym in JOURNEY_ALPHABET:
    JOURNEY_TRANSITIONS[("JT", sym)] = "JT"

# Pre-built Journey DFA instance
JOURNEY_DFA = DFA(
    states=JOURNEY_STATES,
    alphabet=JOURNEY_ALPHABET,
    transitions=JOURNEY_TRANSITIONS,
    start_state=JOURNEY_START_STATE,
    final_states=JOURNEY_ACCEPTING_STATES,
    dead_state=JOURNEY_DEAD_STATE,
)

# ---------------------------------------------------------------------------
# 3. Regular Expression of Accepted Journeys
# ---------------------------------------------------------------------------

JOURNEY_REGEX: str = "E (D | X | (O | T)+ P)"
_JOURNEY_REGEX_COMPILED = re.compile(r"^E(D|X|(O|T)+P)$")


def check_journey_regex(sequence: Union[str, List[str]]) -> bool:
    """
    Checks if a journey sequence matches the formal regular expression:
    E(D | X | (O | T)+ P).
    Provides an independent second opinion to verify the Journey DFA.
    """
    if isinstance(sequence, list):
        seq_str = "".join(sequence)
    else:
        seq_str = sequence.replace(" ", "")
    return bool(_JOURNEY_REGEX_COMPILED.match(seq_str))


# ---------------------------------------------------------------------------
# 4. Public Convenience Functions for Person 2 and Person 3
# ---------------------------------------------------------------------------


def step(state: str, symbol: str) -> str:
    """
    Takes one step on the Journey DFA.
    Delivers the single-call contract for Person 2.
    """
    return JOURNEY_DFA.step(state, symbol)


def run(sequence: Union[str, List[str]]) -> Tuple[bool, TraceList]:
    """Runs a sequence on the Journey DFA. Returns (accepted, trace)."""
    return JOURNEY_DFA.run(sequence)


def get_transition_table() -> List[Dict[str, str]]:
    """Returns the Journey DFA transition table as plain rows for Streamlit."""
    return JOURNEY_DFA.get_transition_table()


def get_journey_dfa() -> DFA:
    """Returns the pre-configured Journey DFA instance."""
    return JOURNEY_DFA