"""
app.py - Streamlit UI for the Automata-Based Smart Metro Ticketing System
==========================================================================
Person 3: UI, integration and report.

Run with:   streamlit run app.py

Four screens (chosen from the sidebar):
  1. Kiosk            - books a ticket using the Booking DFA
  2. Gate simulator   - scans tickets using Person 2's process_scan / pay_excess
  3. String tester    - runs any symbol string through a DFA and shows the trace
  4. Automata viewer  - tables, regexes, Moore/Mealy, NFA->DFA, minimization

This file contains NO automata logic of its own. Every state change comes
from Person 1's DFAs; every scan decision comes from Person 2's classifier.
"""

import re

import streamlit as st

import booking
import config
import journey_automata as ja
from journey import get_ticket_status, pay_excess, process_scan
from stations import STATION_NAMES, check_payment, fare
from token_utils import create_token, make_qr_image

st.set_page_config(page_title="Metro Ticketing - Automata", page_icon="🚇", layout="wide")

BOOKING_DFA = booking.BOOKING_DFA


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def station_label(i: int) -> str:
    return f"{i} - {STATION_NAMES[i]}"


def init_kiosk_state() -> None:
    """Create the kiosk's session variables (Streamlit re-runs the script on every click)."""
    defaults = {
        "bk_state": BOOKING_DFA.start_state,
        "bk_symbols": [],
        "bk_src": None,
        "bk_dst": None,
        "bk_inserted": 0,
        "bk_fare": None,
        "bk_change": 0,
        "bk_token": None,
        "bk_msg": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_kiosk() -> None:
    for key in [k for k in st.session_state if k.startswith("bk_")]:
        del st.session_state[key]
    init_kiosk_state()


def bk_feed(symbol: str) -> None:
    """Feed ONE symbol into the Booking DFA and remember it."""
    st.session_state.bk_state = BOOKING_DFA.step(st.session_state.bk_state, symbol)
    st.session_state.bk_symbols.append(symbol)


def dot_diagram(edges, start, accepting, highlight=None, dead=None, rankdir="LR") -> str:
    """
    Build a Graphviz DOT string.
    edges: list of (from_state, label, to_state).  Parallel edges are merged.
    Edges that go into the dead/trap state are left out to keep the picture
    readable (every missing edge goes to the dead state).
    """
    merged = {}
    for a, label, b in edges:
        if dead is not None and b == dead and a != dead:
            continue
        if dead is not None and a == dead:
            continue
        merged.setdefault((a, b), []).append(label)

    nodes = []
    for a, b in merged:
        for n in (a, b):
            if n not in nodes:
                nodes.append(n)
    if start not in nodes:
        nodes.append(start)
    if dead is not None and dead not in nodes:
        nodes.append(dead)

    lines = [f"digraph G {{ rankdir={rankdir}; node [fontname=Helvetica]; edge [fontname=Helvetica, fontsize=10];"]
    lines.append('__start [shape=point, width=0.15];')
    lines.append(f'__start -> "{start}";')
    for n in nodes:
        shape = "doublecircle" if n in accepting else "circle"
        attrs = f'shape={shape}'
        if n == highlight:
            attrs += ', style=filled, fillcolor="#ffd54f", penwidth=3'
        elif n == dead:
            attrs += ', style=dashed, color=gray, fontcolor=gray'
        lines.append(f'"{n}" [{attrs}];')
    for (a, b), labels in merged.items():
        lines.append(f'"{a}" -> "{b}" [label="{", ".join(labels)}"];')
    lines.append("}")
    return "\n".join(lines)


def dfa_edges(dfa):
    return [(s, sym, t) for (s, sym), t in dfa.transitions.items()]


def nfa_edges(nfa):
    edges = []
    for (s, sym), targets in nfa.transitions.items():
        label = sym if sym != nfa.epsilon_symbol else "ε"
        for t in sorted(targets):
            edges.append((s, label, t))
    return edges


def parse_symbols(text: str, dfa_name: str):
    """Turn what the user typed into a list of symbols."""
    text = text.strip()
    if dfa_name == "Journey DFA":
        return [c for c in text.upper() if not c.isspace() and c != ","]
    return [tok for tok in re.split(r"[\s,]+", text) if tok]


def show_trace(accepted: bool, trace) -> None:
    if accepted:
        st.success("ACCEPTED")
    else:
        st.error("REJECTED")
    st.write(f"**Reason:** {trace.reason}")
    st.write(f"**Final state:** `{trace.final_state}`")
    if len(trace) > 0:
        st.table(list(trace))
    else:
        st.info("Empty input: no steps taken. The DFA stays in its start state.")


# ---------------------------------------------------------------------------
# Screen 1: Kiosk
# ---------------------------------------------------------------------------
def screen_kiosk() -> None:
    init_kiosk_state()
    ss = st.session_state
    state = ss.bk_state

    st.header("🎫 Kiosk - book a ticket")
    st.caption("Every click below is one input symbol for the Booking DFA. "
               "The passenger never chooses the payment result: the system decides pay_ok or pay_fail.")

    left, right = st.columns([3, 2])

    with left:
        # --- Stations ---
        c1, c2 = st.columns(2)
        src_choice = c1.selectbox("Source station", range(config.NUM_STATIONS),
                                  format_func=station_label, key="bk_src_choice")
        dst_choice = c2.selectbox("Destination station", range(config.NUM_STATIONS),
                                  index=3, format_func=station_label, key="bk_dst_choice")
        can_pick = state in ("q0", "q1", "q2")
        b1, b2 = st.columns(2)
        if b1.button("Set source  (src)", disabled=not can_pick):
            ss.bk_src = src_choice
            bk_feed("src")
            st.rerun()
        if b2.button("Set destination  (dst)", disabled=not (can_pick and state != "q0")):
            if ss.bk_src is None or dst_choice == ss.bk_src:
                ss.bk_msg = "Source and destination cannot be the same station."
            else:
                ss.bk_dst = dst_choice
                bk_feed("dst")
                ss.bk_msg = ""
            st.rerun()

        if ss.bk_msg:
            st.warning(ss.bk_msg)

        # --- Show fare / proceed ---
        st.divider()
        b3, b4 = st.columns(2)
        if b3.button("Show Fare  (confirm)", disabled=(state != "q2")):
            ss.bk_fare = fare(ss.bk_src, ss.bk_dst)
            bk_feed("confirm")
            st.rerun()
        if ss.bk_fare is not None:
            st.metric("Fare", f"₹{ss.bk_fare}")
        if b4.button("Proceed to Pay  (confirm)", disabled=(state != "q3")):
            bk_feed("confirm")
            st.rerun()

        # --- Cash ---
        st.divider()
        st.subheader("Insert cash")
        st.write(f"Inserted so far: **₹{ss.bk_inserted}**")
        cash_cols = st.columns(4)
        paying = (state == "q4")
        amount_to_add = 0
        for col, amt in zip(cash_cols[:3], (10, 20, 50)):
            if col.button(f"₹{amt}", disabled=not paying, key=f"cash_{amt}"):
                amount_to_add = amt
        if amount_to_add:
            ss.bk_inserted += amount_to_add
            symbol, change = check_payment(ss.bk_inserted, ss.bk_fare)
            bk_feed(symbol)
            ss.bk_change = change
            st.rerun()

        if state == "q4":
            st.info(f"₹{ss.bk_fare - ss.bk_inserted} more needed.")
        if state in ("q5", "q6"):
            st.success(f"Payment complete. Change to return: ₹{ss.bk_change}")

        # --- Generate / cancel ---
        st.divider()
        b5, b6 = st.columns(2)
        if b5.button("Generate Ticket  (gen)", disabled=(state != "q5")):
            bk_feed("gen")
            ss.bk_token = create_token(ss.bk_src, ss.bk_dst)
            st.rerun()
        if b6.button("Cancel  (cancel)", disabled=(state in ("q6", "qd"))):
            bk_feed("cancel")
            # cancel returns the DFA to q0: forget everything about this booking
            ss.bk_src = ss.bk_dst = ss.bk_fare = None
            ss.bk_inserted = 0
            ss.bk_change = 0
            ss.bk_msg = ""
            st.rerun()

        if state == "q6" and ss.bk_token:
            st.success("Ticket generated!")
            st.code(ss.bk_token, language=None)
            st.caption("Copy this token into the Gate simulator.")
            qr = make_qr_image(ss.bk_token)
            if qr is not None:
                st.image(qr.get_image() if hasattr(qr, "get_image") else qr, width=200)

        if state in ("q6", "qd"):
            if st.button("Start a new booking"):
                reset_kiosk()
                st.rerun()

    with right:
        st.subheader("Booking DFA")
        st.markdown(f"Current state: **`{state}`**"
                    + ("  ✅ accepting" if BOOKING_DFA.is_accepting(state) else ""))
        st.graphviz_chart(dot_diagram(dfa_edges(BOOKING_DFA), BOOKING_DFA.start_state,
                                      BOOKING_DFA.final_states, highlight=state,
                                      dead=BOOKING_DFA.dead_state))
        st.caption("Edges into the dead state qd are hidden: every action not shown leads to qd.")
        st.write("**Symbols fed so far:**")
        st.code(" ".join(ss.bk_symbols) if ss.bk_symbols else "(none yet)", language=None)
        if ss.bk_symbols:
            ok, tr = booking.run(ss.bk_symbols)
            st.write(f"Verdict for this sequence: **{'ACCEPTED' if ok else 'not accepted (yet)'}** - {tr.reason}")


# ---------------------------------------------------------------------------
# Screen 2: Gate simulator
# ---------------------------------------------------------------------------
def show_gate_result(res: dict) -> None:
    if res["gate"] == "OPEN":
        st.success("🟢 GATE OPEN")
    else:
        st.error("🔴 GATE LOCKED")
    c1, c2, c3 = st.columns(3)
    c1.metric("Symbol", res["symbol"] if res["symbol"] else "-")
    c2.metric("State change", f"{res['old_state']} → {res['new_state']}")
    c3.metric("Amount", f"₹{res['amount']}")
    st.write(f"**Message:** {res['message']}")
    st.write(f"**Moore output** (what the new state says): {res['moore_output']}")
    st.write(f"**Mealy output** (what the transition says): {res['mealy_output']}")


def screen_gate() -> None:
    st.header("🚪 Gate simulator")
    st.caption("Scan runs Person 2's process_scan: classifier → Journey DFA → record. "
               "Time is a simulated clock, so a 20-minute loop takes two seconds.")

    default_token = st.session_state.get("bk_token") or ""
    token = st.text_area("Token (paste here, stand-in for a camera)", value=default_token, height=70).strip()

    c1, c2, c3 = st.columns(3)
    station = c1.selectbox("Gate is at station", range(config.NUM_STATIONS), format_func=station_label)
    gate_type = c2.radio("Gate type", ["entry", "exit"], horizontal=True)
    minutes = c3.number_input("Minutes since entry (exit gates)", min_value=0.0, value=8.0, step=0.5)

    b1, b2 = st.columns([1, 1])
    if b1.button("Scan", type="primary", disabled=not token):
        status = get_ticket_status(token)
        if gate_type == "entry":
            now = 0.0
        elif status and status.get("entry_time") is not None:
            # process_scan wants an absolute clock: entry_time + minutes inside
            now = status["entry_time"] + minutes
        else:
            now = float(minutes)
        st.session_state.gate_result = process_scan(token, station, gate_type, now)
    res = st.session_state.get("gate_result")

    if res and res["new_state"] == "JE":
        if b2.button(f"Pay ₹{res['amount']}"):
            st.session_state.gate_result = pay_excess(token)
            res = st.session_state.gate_result

    st.divider()
    if res:
        show_gate_result(res)

    status = get_ticket_status(token) if token else None
    if status:
        st.subheader("Ticket status")
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("State", status["state"])
        d2.metric("Route", f"{status['source']} → {status['dest']}")
        d3.metric("Paid fare", f"₹{status['paid_fare']}")
        d4.metric("Pending", f"₹{status['pending_amount']}")
        history = " ".join(status["history"]) if status["history"] else "(none)"
        st.write("**History line** (copy into the String tester):")
        st.code(history, language=None)
    elif token:
        st.warning("This token is not in the record (edited or unknown).")


# ---------------------------------------------------------------------------
# Screen 3: String tester
# ---------------------------------------------------------------------------
def screen_tester() -> None:
    st.header("🔤 String tester (pure automata mode)")
    which = st.radio("Automaton", ["Journey DFA", "Booking DFA"], horizontal=True)

    if which == "Journey DFA":
        st.caption("Type symbols from E D X O T P W R, e.g. `EOP`.")
        default = "EOP"
        dfa, regex = ja.JOURNEY_DFA, ja.JOURNEY_REGEX
    else:
        st.caption("Type symbols separated by spaces: src dst confirm pay_ok pay_fail gen cancel.")
        default = "src dst confirm confirm pay_fail pay_ok gen"
        dfa, regex = booking.BOOKING_DFA, booking.BOOKING_REGEX_CORRECTED

    text = st.text_input("Sequence", value=default, key=f"seq_{which}")
    if st.button("Run", type="primary"):
        symbols = parse_symbols(text, which)
        accepted, trace = dfa.run(symbols)
        show_trace(accepted, trace)

        st.subheader("Second opinion: regular expression")
        if which == "Journey DFA":
            st.write(f"Regex: `{regex}`")
            st.write(f"Regex says: **{'match' if ja.check_journey_regex(symbols) else 'no match'}**")
        else:
            st.write(f"Corrected regex: `{booking.BOOKING_REGEX_CORRECTED}`")
            st.write(f"README regex (as written): `{booking.BOOKING_REGEX_AS_WRITTEN}`")
            st.write(f"Corrected regex says: **{'match' if booking.check_booking_regex(symbols, corrected=True) else 'no match'}**")
            st.write(f"As-written regex says: **{'match' if booking.check_booking_regex(symbols, corrected=False) else 'no match'}**")
            if "cancel" in symbols:
                st.info("The regex does not model `cancel`, so it may disagree with the DFA here.")


# ---------------------------------------------------------------------------
# Screen 4: Automata viewer
# ---------------------------------------------------------------------------
def tab_tables() -> None:
    st.subheader("Journey DFA")
    st.table(ja.get_transition_table())
    st.write(f"Regex: `{ja.JOURNEY_REGEX}`")
    jd = ja.JOURNEY_DFA
    st.graphviz_chart(dot_diagram(dfa_edges(jd), jd.start_state, jd.final_states, dead=jd.dead_state))

    st.subheader("Booking DFA")
    st.table(booking.get_transition_table())
    st.write(f"Regex (corrected, two `confirm`s): `{booking.BOOKING_REGEX_CORRECTED}`")
    st.write(f"Regex (as written in the README): `{booking.BOOKING_REGEX_AS_WRITTEN}`")
    st.warning("**Contract note (Issue A):** the README regex has one `confirm`, but the transition table "
               "needs two (q2→q3 'Show Fare', q3→q4 'Proceed to Pay'). The table was kept as given; "
               "the corrected regex fixes the mismatch.")
    bd = booking.BOOKING_DFA
    st.graphviz_chart(dot_diagram(dfa_edges(bd), bd.start_state, bd.final_states, dead=bd.dead_state))


def tab_moore_mealy() -> None:
    st.subheader("Moore machine (output depends on the state)")
    st.table(ja.get_moore_table())
    st.caption("The JE output is a template; Person 2 fills in the rupee amount.")
    st.subheader("Mealy machine (output depends on state and input)")
    st.table(ja.get_mealy_table())
    st.caption("Only the six valid transitions come from the README. "
               "Outputs for transitions into JT and for JE on O/T are additions (Issue B).")


def tab_nfa() -> None:
    st.subheader("Payment-method NFA (theory demonstration only - the real kiosk accepts cash only)")
    steps = booking.get_subset_steps()
    nfa = booking.PAYMENT_NFA
    st.graphviz_chart(dot_diagram(nfa_edges(nfa), nfa.start_state, nfa.final_states))
    st.write("**NFA transition table**")
    st.table(steps["nfa_transition_table"])
    st.write("**Subset construction: which set of NFA states becomes which DFA state**")
    st.table(steps["display_rows"])
    st.write("Discovery order: " + " → ".join(steps["discovery_order"]))
    dfa = steps["dfa"]
    st.write("**Resulting DFA**")
    st.graphviz_chart(dot_diagram(dfa_edges(dfa), dfa.start_state, dfa.final_states, dead=dfa.dead_state))
    st.success("The NFA and the DFA accept exactly the same strings.")


def tab_minimize() -> None:
    st.subheader("DFA minimization (table-filling / Myhill-Nerode)")
    st.write("A deliberately redundant Booking DFA has two Paid states, PaidCash and PaidUPI, that behave identically.")
    if not st.button("Minimize", type="primary"):
        return
    m = booking.get_minimization_steps()
    c1, c2 = st.columns(2)
    c1.metric("States before", m["before_state_count"])
    c2.metric("States after", m["after_state_count"])
    st.caption(m["counting_rule"])

    before = booking.get_redundant_booking_dfa()
    st.write("**Before (8 states)**")
    st.graphviz_chart(dot_diagram(dfa_edges(before), before.start_state, before.final_states,
                                  dead=before.dead_state))

    st.write("**Marking history, round by round**")
    st.table([{"Round": h["round"], "Pair": h["pair_str"], "Reason": h["reason"]}
              for h in m["marking_history"]])

    st.write("**All pairs**")
    st.table([{k: str(v) for k, v in row.items()} for row in m["display_table"]])

    st.write(f"**Unmarked (equivalent) pairs:** {m['unmarked_pairs_str']}")
    for note in m["merged_notes"]:
        st.info(note)

    after = m["minimized_dfa"]
    st.write("**After (7 states)**")
    st.table(after.get_transition_table())
    st.graphviz_chart(dot_diagram(dfa_edges(after), after.start_state, after.final_states,
                                  dead=after.dead_state))
    st.success("The minimized DFA and the original accept exactly the same strings.")


def screen_viewer() -> None:
    st.header("📚 Automata viewer (the theory)")
    t1, t2, t3, t4 = st.tabs(["Tables & regexes", "Moore & Mealy", "NFA → DFA", "Minimization"])
    with t1:
        tab_tables()
    with t2:
        tab_moore_mealy()
    with t3:
        tab_nfa()
    with t4:
        tab_minimize()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
st.sidebar.title("🚇 Metro Automata")
page = st.sidebar.radio("Screen", ["Kiosk", "Gate simulator", "String tester", "Automata viewer"])
st.sidebar.caption(f"{config.NUM_STATIONS} stations, one-way circular line. "
                   f"Time limit {config.TIME_LIMIT:g} min.")

if page == "Kiosk":
    screen_kiosk()
elif page == "Gate simulator":
    screen_gate()
elif page == "String tester":
    screen_tester()
else:
    screen_viewer()