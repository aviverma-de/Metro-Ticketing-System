"""
UI Helpers for Metro Ticketing System
--------------------------------------
Pure helper functions with NO Streamlit calls, allowing 100% test coverage.
"""

from typing import Any, Dict, List, Optional, Sequence, Union


# Friendly state presentation labels
STATE_LABELS: Dict[str, str] = {
    # Booking DFA States
    "q0": "Idle",
    "q1": "Source selected",
    "q2": "Destination selected",
    "q3": "Fare displayed",
    "q4": "Payment pending",
    "q5": "Paid",
    "q6": "Ticket generated (Accepting)",
    "qd": "Dead / Cancelled",
    # Journey DFA States
    "J0": "Issued",
    "J1": "Inside",
    "JE": "Excess/Over-time pending",
    "J2": "Exited normally (Accepting)",
    "J3": "Exited early (Accepting)",
    "JT": "Rejected (Trap)",
}

# Friendly symbol presentation labels
SYMBOL_MEANINGS: Dict[str, str] = {
    # Booking Symbols
    "src": "Select source station",
    "dst": "Select destination station",
    "confirm": "Confirm selection / proceed",
    "pay_ok": "Payment successful",
    "pay_fail": "Payment insufficient / retry",
    "gen": "Generate ticket",
    "cancel": "Cancel transaction",
    # Journey Symbols
    "E": "Valid entry scan",
    "D": "Exit at destination",
    "X": "Early exit (fare slab <= paid)",
    "O": "Exit with excess fare due",
    "T": "Over-time violation",
    "P": "Pay pending excess/over-time charge",
    "W": "Wrong gate / wrong station / invalid",
    "R": "Reuse of closed ticket",
}


def build_dot(
    table_rows: List[Dict[str, str]],
    current_state: Optional[str] = None,
    accepting: Sequence[str] = (),
    dead: Optional[str] = None,
) -> str:
    """
    Builds a Graphviz DOT string from transition table rows.
    
    table_rows: list of dicts with 'State' key and one key per symbol.
    current_state: state to highlight/fill.
    accepting: collection of accepting states (rendered with shape=doublecircle).
    dead: dead/trap state name. Transitions to this state are omitted from edges.
    """
    lines = [
        'digraph DFA {',
        '  rankdir=LR;',
        '  node [fontname="Helvetica", fontsize=11];',
        '  edge [fontname="Helvetica", fontsize=10];',
    ]

    accepting_set = set(accepting)

    # Collect all states and transition mappings
    # mapping: (src, dst) -> list of symbols
    edge_map: Dict[tuple, List[str]] = {}
    all_states: List[str] = []

    for row in table_rows:
        src = row.get("State")
        if not src:
            continue
        all_states.append(src)
        for sym, dst in row.items():
            if sym == "State":
                continue
            # Do not draw edges leading into the dead/trap state
            if dead is not None and dst == dead:
                continue
            # If src is dead state, do not draw self loops or dead moves
            if dead is not None and src == dead:
                continue
            pair = (src, dst)
            if pair not in edge_map:
                edge_map[pair] = []
            edge_map[pair].append(sym)

    # Define nodes
    for st in all_states:
        attrs = []
        is_acc = st in accepting_set
        is_curr = (st == current_state)

        shape = "doublecircle" if is_acc else "circle"
        attrs.append(f'shape={shape}')

        if is_curr:
            attrs.append('style=filled, fillcolor="#bbf0bb", color="#1b5e20", penwidth=2.5')
        elif st == dead:
            attrs.append('color="#e57373", fontcolor="#b71c1c"')
        else:
            attrs.append('color="#37474f"')

        lines.append(f'  "{st}" [{", ".join(attrs)}];')

    # Define edges (grouped by label)
    for (src, dst), syms in edge_map.items():
        label = ",".join(syms)
        lines.append(f'  "{src}" -> "{dst}" [label="{label}"];')

    lines.append('}')
    return "\n".join(lines)


def parse_sequence(text: str, dfa_kind: str) -> List[str]:
    """
    Parse a user sequence string into a list of symbols.
    
    dfa_kind: 'journey' or 'booking'
    Journey: single letters, spaces ignored, uppercase ("EOP" or "E O P" -> ['E', 'O', 'P'])
    Booking: words separated by spaces or commas ("src dst confirm" -> ['src', 'dst', 'confirm'])
    """
    if not text:
        return []

    kind = dfa_kind.strip().lower()
    if kind == "journey":
        clean = "".join(text.split()).upper()
        return list(clean)
    else:
        # booking: split on commas and whitespace
        parts = text.replace(",", " ").split()
        return [p.strip() for p in parts if p.strip()]


def compute_now(gate_type: str, minutes: float, status: Optional[Dict[str, Any]]) -> float:
    """
    Compute current simulation time in minutes.
    - Entry gate: returns 0.0
    - Exit gate: returns status['entry_time'] + minutes if status exists and entry_time is not None,
      otherwise returns minutes.
    """
    g_type = gate_type.strip().lower()
    if g_type == "entry":
        return 0.0

    if status is not None and status.get("entry_time") is not None:
        return float(status["entry_time"]) + float(minutes)

    return float(minutes)
