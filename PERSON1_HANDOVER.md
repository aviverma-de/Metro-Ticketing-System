# Person 1 Handover: Automata Engine API & Integration Guide

This document describes every public object and function provided by Person 1 (Automata Engine) for Person 2 (Ticket, Gate & Time Logic) and Person 3 (UI, Integration & Report).

---

## 1. Executive Summary & Design Separation

- **Pure Abstract Automata:** This library knows **nothing** about station IDs, fares, timestamps, HMAC tokens, SQLite, or Streamlit. It models states, symbols, transitions, and language recognition in the abstract.
- **Dedicated Module `journey_automata.py`:** Kept distinct from Person 2's `journey.py` (which contains the sensor classifier, cryptographic signature checks, and hardware logic) so that Person 2 can import the Journey DFA with a single line without circular imports.
- **Plain Data Guarantee:** Every function delivered to Person 3 returns standard Python primitives (`list`, `dict`, `str`, `int`, `bool`) that Streamlit can display directly via `st.table()` or `st.dataframe()`.

---

## 2. Handover to Person 2 (Gate & Classifier Integration)

### Ready-to-Use Journey DFA Object
Person 2 imports the pre-built Journey DFA object and the single-step evaluator with a one-line import:

```python
from journey_automata import JOURNEY_DFA, step
```

### Public Functions and Objects for Person 2

#### `JOURNEY_DFA.step(state: str, symbol: str) -> str`
- **Inputs:**
  - `state` (`str`): Current state (`'J0'`, `'J1'`, `'JE'`, `'J2'`, `'J3'`, or `'JT'`).
  - `symbol` (`str`): Input event symbol (`'E'`, `'D'`, `'X'`, `'O'`, `'T'`, `'P'`, `'W'`, `'R'`).
- **Output:**
  - `next_state` (`str`): Next state according to the frozen contract. Missing or invalid transitions cleanly yield `'JT'`.
- **Usage Example:**
  - `next_st = step("J1", "D")` returns `"J2"`.

#### `JOURNEY_DFA.run(sequence: Union[str, List[str]]) -> Tuple[bool, TraceList]`
- **Inputs:**
  - `sequence`: Compact string (e.g. `"EOP"`) or list of symbols (e.g. `['E', 'O', 'P']`).
- **Outputs:**
  - `accepted` (`bool`): `True` if final state is in `{'J2', 'J3'}`, else `False`.
  - `trace` (`TraceList`): List of step dictionaries. Also provides attributes `.states`, `.final_state`, `.reason`, and `.accepted`.
- **Usage Example:**
  - `accepted, trace = JOURNEY_DFA.run("EOP")` returns `(True, trace)` with `trace.final_state == "J2"`.

#### `get_moore_output(state: str) -> str`
- **Inputs:** `state` (`str`)
- **Output:** Template output text (`str`) for that gate state.
- **Important Note (Issue C):** For state `'JE'`, this function returns the template string `"Gate LOCKED, show Pay excess ₹ or Pay over-time charge ₹"`. Person 2 replaces the template with the dynamically computed rupee amount before presenting it to the user.
- **Usage Example:**
  - `text = get_moore_output("J1")` returns `"Entry gate open"`.

#### `get_mealy_output(state: str, symbol: str) -> str`
- **Inputs:** `state` (`str`), `symbol` (`str`)
- **Output:** Output text (`str`) associated with taking transition `(state, symbol)`. Includes Issue B additions for all trap and repeated-scan transitions.
- **Usage Example:**
  - `text = get_mealy_output("J1", "O")` returns `"Lock gate, show excess fare"`.

---

## 3. Handover to Person 3 (UI, Integration & Automata Viewer)

All functions below return plain Python data ready for Streamlit.

### 3.1 Transition Tables (for Theory & Simulator Tabs)

#### `journey_automata.get_transition_table() -> List[Dict[str, str]]`
- **Inputs:** None.
- **Output:** List of 6 row dictionaries (one per state: `J0`, `J1`, `JE`, `J2`, `J3`, `JT`) with keys `'State'`, `'E'`, `'D'`, `'X'`, `'O'`, `'T'`, `'P'`, `'W'`, `'R'`.
- **Usage Example:**
  - `st.table(journey_automata.get_transition_table())`

#### `booking.get_transition_table() -> List[Dict[str, str]]`
- **Inputs:** None.
- **Output:** List of 8 row dictionaries (one per state: `q0` through `q6`, and `qd`) with keys `'State'`, `'src'`, `'dst'`, `'confirm'`, `'pay_ok'`, `'pay_fail'`, `'gen'`, `'cancel'`.
- **Usage Example:**
  - `st.dataframe(booking.get_transition_table())`

#### `journey_automata.get_moore_table() -> List[Dict[str, str]]`
- **Inputs:** None.
- **Output:** List of state rows with `'State'`, `'Output'`, and all next-state columns.
- **Usage Example:**
  - `st.table(journey_automata.get_moore_table())`

#### `journey_automata.get_mealy_table() -> List[Dict[str, str]]`
- **Inputs:** None.
- **Output:** List of rows with formatted cells `"<next_state> / '<output>'"` for every `(state, symbol)` pair.
- **Usage Example:**
  - `st.table(journey_automata.get_mealy_table())`

---

### 3.2 Pure String Tester (String Evaluation & Rejection Reasons)

#### `JOURNEY_DFA.run(seq)` & `BOOKING_DFA.run(seq)`
- **Trace Structure:**
  Each step in `trace` is a plain dict:
  ```python
  {
      "step": 1,
      "from": "J0",
      "from_state": "J0",
      "symbol": "E",
      "to": "J1",
      "to_state": "J1"
  }
  ```
  Streamlit can pass `trace` directly to `st.table(trace)`.
- **Human-Readable Rejection Reasons:**
  Accessible via `trace.reason` or `dfa.get_rejection_reason()`:
  - `"Accepted"`
  - `"ended in a non-accepting state"` (e.g. `EO` ending in `JE`)
  - `"entered the trap state"` / `"entered the dead state"` (e.g. `EE` entering `JT`)
  - `"Unknown symbol '<sym>' not in alphabet"`

---

### 3.3 Regular Expression Strings & Helpers

- `journey_automata.JOURNEY_REGEX`: `"E (D | X | (O | T)+ P)"`
- `journey_automata.check_journey_regex(seq: Union[str, List[str]]) -> bool`
- `booking.BOOKING_REGEX_AS_WRITTEN`: `"src (src | dst)* dst confirm pay_fail* pay_ok gen"`
- `booking.BOOKING_REGEX_CORRECTED`: `"src (src | dst)* dst confirm confirm pay_fail* pay_ok gen"`
- `booking.check_booking_regex(seq: Union[str, List[str]], corrected: bool = False) -> bool`

**Contract Notice on Issue A:** Person 3 should display both regex strings in the UI, noting that the README regex as written contained 1 confirm, whereas the Kiosk DFA table requires 2 confirms (`q2 -> confirm -> q3 -> confirm -> q4`).

---

### 3.4 Subset Construction (Payment NFA -> DFA Tab)

#### `booking.get_subset_steps() -> Dict[str, Any]`
- **Inputs:** None.
- **Output Dictionary Keys:**
  - `'display_rows'`: Flat list of dicts with columns `'DFA State'`, `'NFA Subset'`, `'Accepting'`, and symbol target columns. Ready for `st.table()`.
  - `'discovery_order'`: List of discovered DFA state names `['D0', 'D1', ...]`.
  - `'name_to_subset'`: Dict mapping DFA state names to lists of NFA states (e.g. `'D0': ['N0', 'N_card', 'N_cash', 'N_upi']`).
  - `'nfa_transition_table'`: Plain rows of the 5-state payment NFA.
  - `'dfa'`: The resulting equivalent DFA object.
- **Usage Example:**
  - `st.table(booking.get_subset_steps()["display_rows"])`

---

### 3.5 Table-Filling Minimization (Redundant Booking DFA Tab)

#### `booking.get_minimization_steps() -> Dict[str, Any]`
- **Inputs:** None.
- **Output Dictionary Keys:**
  - `'before_state_count'`: `8` (explicit states `q0, q1, q2, q3, q4, PaidCash, PaidUPI, q6`).
  - `'after_state_count'`: `7` (minimized states).
  - `'counting_rule'`: String explaining that the implicit dead state is excluded.
  - `'unmarked_pairs'`: `[('PaidCash', 'PaidUPI')]`.
  - `'merged_notes'`: `['PaidCash and PaidUPI merge into PaidCash_PaidUPI']`.
  - `'display_table'`: Plain rows with columns `'Pair'`, `'Distinguishable'`, `'Marked Round'`, `'Reason'`.
  - `'marking_history'`: Ordered list of all marked pairs, round numbers, and justifications.
  - `'minimized_dfa'`: The resulting minimized 7-state DFA object.
- **Usage Example:**
  - `steps = booking.get_minimization_steps()`
  - `st.write(f"Minimized from {steps['before_state_count']} to {steps['after_state_count']} states")`
  - `st.table(steps["display_table"])`

