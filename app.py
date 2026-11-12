"""
Streamlit User Interface — Metro Ticketing & Journey Validation System
-----------------------------------------------------------------------
Person 3 Frontend: Connects Person 1's automata engines and Person 2's
gate and ticketing logic to an interactive dashboard.

Rule Zero: The UI has NO logic. All fare, payment, token, classifier,
DFA and time rules live strictly in the backend modules.
"""

import streamlit as st
import config
import stations
import token_utils
import record
import journey
from booking import (
    BOOKING_DFA,
    BOOKING_REGEX_AS_WRITTEN,
    BOOKING_REGEX_CORRECTED,
    check_booking_regex,
    get_transition_table as get_booking_transition_table,
    get_subset_steps,
    get_minimization_steps,
)
from journey_automata import (
    JOURNEY_DFA,
    JOURNEY_REGEX,
    check_journey_regex,
    get_transition_table as get_journey_transition_table,
    get_moore_table,
    get_mealy_table,
)
import ui_helpers

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Metro Automata System",
    page_icon="🚇",
    layout="wide",
)

# Initialize database on startup
record.init_db()

# ---------------------------------------------------------------------------
# Session State Initialization (must run before any widget)
# ---------------------------------------------------------------------------
def _init():
    defaults = {
        # Kiosk
        "booking_state": BOOKING_DFA.start_state,
        "booking_history": [],
        "selected_source": None,
        "selected_dest": None,
        "fare_amount": 0,
        "inserted_total": 0,
        "change_amount": 0,
        "token": None,
        "qr_image": None,
        # Gate
        "gate_token": "",
        "last_scan": None,
        "scan_log": [],
        # String tester
        "tester_sequence": "EOP",
        "tester_dfa_kind": "Journey DFA",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Simulation Settings")
    st.write(f"**Total Stations:** {config.NUM_STATIONS}")
    st.write(f"**Travel Time:** {config.MINUTES_PER_STATION} min/station")
    st.write(f"**Buffer:** {config.BUFFER_MINUTES} min")
    st.write(f"**Time Limit:** {config.TIME_LIMIT} min")
    st.write(f"**Overtime Charge:** Rs {config.OVERTIME_CHARGE}")
    st.write(f"**DB:** `{config.DB_PATH}`")

    st.divider()
    st.subheader("DB Management")

    def _do_reset():
        if st.session_state.get("confirm_reset_chk"):
            record.reset_db()
            st.session_state.update({
                "booking_state": BOOKING_DFA.start_state,
                "booking_history": [],
                "selected_source": None,
                "selected_dest": None,
                "fare_amount": 0,
                "inserted_total": 0,
                "change_amount": 0,
                "token": None,
                "qr_image": None,
                "gate_token": "",
                "last_scan": None,
                "scan_log": [],
            })

    st.checkbox("Confirm reset", key="confirm_reset_chk")
    st.button("Reset demo database", on_click=_do_reset)
    if st.session_state.get("confirm_reset_chk") is False:
        # Only show warning after the button was pressed without confirm—handled silently.
        pass

# ---------------------------------------------------------------------------
# Kiosk Callbacks  (each feeds exactly ONE symbol to BOOKING_DFA)
# ---------------------------------------------------------------------------

def _kiosk_step(symbol: str):
    curr = st.session_state["booking_state"]
    st.session_state["booking_state"] = BOOKING_DFA.step(curr, symbol)
    st.session_state["booking_history"].append(symbol)


def on_source_changed():
    val = st.session_state.get("kiosk_src_select", "")
    if val and val != "Select source":
        st.session_state["selected_source"] = int(val.split(" - ")[0])
        st.session_state["selected_dest"] = None
        _kiosk_step("src")


def on_dest_changed():
    val = st.session_state.get("kiosk_dst_select", "")
    if val and val != "Select destination":
        st.session_state["selected_dest"] = int(val.split(" - ")[0])
        _kiosk_step("dst")


def on_show_fare():
    src = st.session_state["selected_source"]
    dst = st.session_state["selected_dest"]
    try:
        st.session_state["fare_amount"] = stations.fare(src, dst)
        _kiosk_step("confirm")
    except Exception as exc:
        st.session_state["_kiosk_error"] = str(exc)


def on_proceed_pay():
    st.session_state["inserted_total"] = 0
    st.session_state["change_amount"] = 0
    _kiosk_step("confirm")


def on_cash_inserted(amt: int):
    st.session_state["inserted_total"] += amt
    sym, change = stations.check_payment(
        st.session_state["inserted_total"],
        st.session_state["fare_amount"],
    )
    st.session_state["change_amount"] = change
    _kiosk_step(sym)


def on_generate_ticket():
    _kiosk_step("gen")
    tok = token_utils.create_token(
        st.session_state["selected_source"],
        st.session_state["selected_dest"],
    )
    st.session_state["token"] = tok
    st.session_state["qr_image"] = token_utils.make_qr_image(tok)


def on_cancel():
    _kiosk_step("cancel")
    st.session_state["selected_source"] = None
    st.session_state["selected_dest"] = None
    st.session_state["fare_amount"] = 0
    st.session_state["inserted_total"] = 0
    st.session_state["change_amount"] = 0


def on_new_booking():
    st.session_state.update({
        "booking_state": BOOKING_DFA.start_state,
        "booking_history": [],
        "selected_source": None,
        "selected_dest": None,
        "fare_amount": 0,
        "inserted_total": 0,
        "change_amount": 0,
        "token": None,
        "qr_image": None,
    })


def on_send_to_gate():
    tok = st.session_state.get("token")

    if tok:
        st.session_state["gate_token"] = tok
        st.session_state["sent_to_gate"] = True
    else:
        st.session_state["sent_to_gate"] = False


# ---------------------------------------------------------------------------
# Gate callbacks
# ---------------------------------------------------------------------------

def on_scan_gate():
    tok = st.session_state.get("gate_token", "")
    station_idx = st.session_state.get("gate_station_select", 0)
    gtype = st.session_state.get("gate_type_radio", "entry")
    mins = st.session_state.get("gate_minutes", 0.0)
    try:
        status = journey.get_ticket_status(tok)
        now = ui_helpers.compute_now(gtype, mins, status)
        res = journey.process_scan(tok, station_idx, gtype, now)
        st.session_state["last_scan"] = res
        st.session_state["scan_log"].insert(0, {
            "station": station_idx,
            "gate": gtype,
            "symbol": res["symbol"],
            "old_state": res["old_state"],
            "new_state": res["new_state"],
            "gate_result": res["gate"],
            "amount": res["amount"],
        })
    except Exception as exc:
        st.session_state["gate_error"] = str(exc)


def on_pay_excess():
    tok = st.session_state.get("gate_token", "")
    station_idx = st.session_state.get("gate_station_select", 0)
    gtype = st.session_state.get("gate_type_radio", "exit")
    try:
        p_res = journey.pay_excess(tok)
        st.session_state["last_scan"] = p_res
        st.session_state["scan_log"].insert(0, {
            "station": station_idx,
            "gate": gtype,
            "symbol": p_res["symbol"],
            "old_state": p_res["old_state"],
            "new_state": p_res["new_state"],
            "gate_result": p_res["gate"],
            "amount": p_res["amount"],
        })
    except Exception as exc:
        st.session_state["gate_error"] = str(exc)


def on_use_last_ticket():
    if st.session_state.get("token"):
        st.session_state["gate_token"] = st.session_state["token"]


def on_send_to_tester():
    tok = st.session_state.get("gate_token", "")
    t_status = journey.get_ticket_status(tok)
    if t_status:
        st.session_state["tester_sequence"] = t_status["history"]
        st.session_state["tester_dfa_kind"] = "Journey DFA"


# String tester example callbacks
def _set_tester_seq(seq: str, kind: str = "Journey DFA"):
    st.session_state["tester_sequence"] = seq
    st.session_state["tester_dfa_kind"] = kind


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_kiosk, tab_gate, tab_tester, tab_viewer = st.tabs([
    "🎟️ Kiosk",
    "🚪 Gate Simulator",
    "🔤 String Tester",
    "🔍 Automata Viewer",
])

# ===========================================================================
# TAB 1 — KIOSK
# ===========================================================================
with tab_kiosk:
    col_left, col_right = st.columns([1.1, 1], gap="large")

    with col_left:
        st.subheader("Interactive Ticket Kiosk")

        # Show any error produced by a callback
        if "_kiosk_error" in st.session_state:
            st.error(st.session_state.pop("_kiosk_error"))

        b_state = st.session_state["booking_state"]

        # ---- Source selectbox ----
        src_opts = ["Select source"] + [
            f"{i} - {n}" for i, n in enumerate(stations.STATION_NAMES)
        ]
        src_idx = 0
        if st.session_state["selected_source"] is not None:
            src_idx = st.session_state["selected_source"] + 1

        st.selectbox(
            "Source Station",
            options=src_opts,
            index=src_idx,
            disabled=b_state not in ("q0", "q1", "q2"),
            key="kiosk_src_select",
            on_change=on_source_changed,
        )

        # ---- Destination selectbox ----
        dst_opts = ["Select destination"]
        if st.session_state["selected_source"] is not None:
            dst_opts += [
                f"{i} - {n}"
                for i, n in enumerate(stations.STATION_NAMES)
                if i != st.session_state["selected_source"]
            ]
        dst_idx = 0
        if st.session_state["selected_dest"] is not None:
            match = (
                f"{st.session_state['selected_dest']} - "
                f"{stations.STATION_NAMES[st.session_state['selected_dest']]}"
            )
            if match in dst_opts:
                dst_idx = dst_opts.index(match)

        st.selectbox(
            "Destination Station",
            options=dst_opts,
            index=dst_idx,
            disabled=b_state not in ("q1", "q2") or st.session_state["selected_source"] is None,
            key="kiosk_dst_select",
            on_change=on_dest_changed,
        )

        # ---- State-specific controls ----
        if b_state == "q2":
            st.button("Show Fare", on_click=on_show_fare, type="primary")

        if b_state == "q3":
            st.info(f"**Trip Fare:** Rs {st.session_state['fare_amount']}")
            st.button("Proceed to Pay", on_click=on_proceed_pay, type="primary")

        if b_state == "q4":
            fare_amt = st.session_state["fare_amount"]
            ins = st.session_state["inserted_total"]
            st.write(f"### Cash Payment  (Fare: Rs {fare_amt})")
            st.write(f"**Inserted so far:** Rs {ins}")
            remaining = fare_amt - ins
            if remaining > 0:
                st.warning(f"**Rs {remaining} more needed**")
            else:
                st.success(f"**Change to return: Rs {st.session_state['change_amount']}**")

            c1, c2, c3 = st.columns(3)
            c1.button("Insert Rs 10", on_click=on_cash_inserted, args=(10,), key="cash_10")
            c2.button("Insert Rs 20", on_click=on_cash_inserted, args=(20,), key="cash_20")
            c3.button("Insert Rs 50", on_click=on_cash_inserted, args=(50,), key="cash_50")

            with st.expander("Custom amount"):
                st.number_input(
                    "Rs", min_value=1, value=10, step=5,
                    key="kiosk_custom_cash",
                )
                st.button(
                    "Insert custom",
                    on_click=lambda: on_cash_inserted(st.session_state["kiosk_custom_cash"]),
                    key="cash_custom_btn",
                )

        if b_state == "q5":
            st.success(f"Payment done!  Change: Rs {st.session_state['change_amount']}")
            st.button("Generate Ticket", on_click=on_generate_ticket, type="primary")

        if b_state == "q6":
            tok = st.session_state["token"]
            st.success("🎉 Ticket generated!")
            if tok:
                st.write("**Token (copy with the button):**")
                st.code(tok, language="text")
                qr = st.session_state["qr_image"]
                if qr:
                    qr_img = qr.get_image()
                    st.image(qr_img, caption="Scan at the gate", width=180)
                else:
                    st.caption("QR unavailable — `qrcode` library not installed.")

                src_id = st.session_state["selected_source"]
                dst_id = st.session_state["selected_dest"]
                if src_id is not None and dst_id is not None:
                    st.write(
                        f"**Route:** {src_id} {stations.STATION_NAMES[src_id]} → "
                        f"{dst_id} {stations.STATION_NAMES[dst_id]}  |  "
                        f"**Fare:** Rs {st.session_state['fare_amount']}"
                    )

                col_a, col_b = st.columns(2)
                col_a.button("Send to Gate Simulator", on_click=on_send_to_gate)
                col_b.button("New booking", on_click=on_new_booking)

        # Cancel is only valid in q0–q4
        if b_state in ("q0", "q1", "q2", "q3", "q4"):
            st.write("")
            st.button("Cancel", on_click=on_cancel, type="secondary")

    # ---- Right column: live DFA panel ----
    with col_right:
        st.subheader("Live Booking DFA")
        b_state = st.session_state["booking_state"]
        lbl = ui_helpers.STATE_LABELS.get(b_state, b_state)
        st.markdown(f"#### State: `{b_state}` — {lbl}")

        hist = st.session_state["booking_history"]
        trace_str = " → ".join(hist) if hist else "(start)"
        st.caption(f"Trace: `{trace_str}`")

        try:
            dot = ui_helpers.build_dot(
                get_booking_transition_table(),
                current_state=b_state,
                accepting=BOOKING_DFA.final_states,
                dead=BOOKING_DFA.dead_state,
            )
            st.graphviz_chart(dot)
        except Exception as exc:
            st.error(f"Diagram error: {exc}")

        st.caption("All other transitions go to the dead state (`qd`).")
        st.write("**Formal Regular Expression (corrected):**")
        st.code(BOOKING_REGEX_CORRECTED, language="text")

# ===========================================================================
# TAB 2 — GATE SIMULATOR
# ===========================================================================
with tab_gate:
    st.subheader("Metro Gate Simulator")
    col_in, col_out = st.columns([1, 1.3], gap="large")

    with col_in:
        st.selectbox(
            "Station",
            options=range(config.NUM_STATIONS),
            format_func=lambda i: f"Station {i} — {stations.STATION_NAMES[i]}",
            key="gate_station_select",
        )
        st.radio(
            "Gate type",
            options=["entry", "exit"],
            horizontal=True,
            key="gate_type_radio",
        )

        # Token text area uses the session-state key directly
        st.text_area("Ticket Token", key="gate_token", height=80)
        st.button("Use last generated ticket", on_click=on_use_last_ticket)

        # Minutes input (always rendered to keep widget key stable)
        mins_disabled = st.session_state.get("gate_type_radio", "entry") != "exit"
        st.number_input(
            "Minutes since entry",
            min_value=0.0,
            max_value=120.0,
            value=5.0,
            step=1.0,
            disabled=mins_disabled,
            key="gate_minutes",
            help=(
                f"{config.MINUTES_PER_STATION} min/station · "
                f"Time limit: {config.TIME_LIMIT} min · "
                f"Overtime charge: Rs {config.OVERTIME_CHARGE}"
            ),
        )

        st.button("Scan Gate", on_click=on_scan_gate, type="primary")

        if "gate_error" in st.session_state:
            st.error(st.session_state.pop("gate_error"))

    with col_out:
        scan_res = st.session_state.get("last_scan")
        if scan_res:
            # Gate indicator
            if scan_res["gate"] == "OPEN":
                st.success("## 🟢  GATE OPEN")
            else:
                st.error("## 🔴  GATE LOCKED")

            if not scan_res.get("valid", True):
                st.error("❌ **Invalid or forged token**")

            sym = scan_res["symbol"]
            old_s = scan_res["old_state"]
            new_s = scan_res["new_state"]
            st.write(
                f"**Symbol:** `{sym}` — {ui_helpers.SYMBOL_MEANINGS.get(sym, sym)}"
            )
            st.write(
                f"**DFA:** `{old_s}` ({ui_helpers.STATE_LABELS.get(old_s or '', old_s or 'None')}) "
                f"➔ `{new_s}` ({ui_helpers.STATE_LABELS.get(new_s, new_s)})"
            )
            st.info(scan_res["message"])

            c_mo, c_me = st.columns(2)
            c_mo.markdown(
                "<div style='background:#e8f4f8;color:#17202a;padding:10px;border-radius:5px;"
                "border-left:4px solid #0288d1'>"
                f"<b>Moore:</b><br>{scan_res['moore_output']}</div>",
                unsafe_allow_html=True,
            )

            c_me.markdown(
                "<div style='background:#f3e5f5;color:#17202a;padding:10px;border-radius:5px;"
                "border-left:4px solid #7b1fa2'>"
                f"<b>Mealy:</b><br>{scan_res['mealy_output']}</div>",
                unsafe_allow_html=True,
            )

            # Pay button when JE
            if scan_res.get("new_state") == "JE":
                amount = scan_res.get("amount", 0)
                # Also read from pending_amount in case the scan was a re-scan
                tok_tmp = st.session_state.get("gate_token", "")
                if tok_tmp:
                    try:
                        ts = journey.get_ticket_status(tok_tmp)
                        if ts and ts.get("pending_amount"):
                            amount = ts["pending_amount"]
                    except Exception:
                        pass
                st.warning(f"⚠️ Pending charge: **Rs {amount}**")
                st.button(
                    f"Pay Rs {amount}",
                    on_click=on_pay_excess,
                    type="primary",
                    key="pay_excess_btn",
                )

        # Ticket status box
        tok_stat = st.session_state.get("gate_token", "")
        if tok_stat:
            try:
                t_status = journey.get_ticket_status(tok_stat)
            except Exception:
                t_status = None
            if t_status:
                with st.expander("📋 Ticket Status (from database)", expanded=True):
                    st.write(
                        f"**State:** `{t_status['state']}` "
                        f"({ui_helpers.STATE_LABELS.get(t_status['state'], '')})"
                    )
                    st.write(
                        f"**Route:** {t_status['source']} → {t_status['dest']}  |  "
                        f"**Fare paid:** Rs {t_status['paid_fare']}"
                    )
                    st.write(f"**Entry time:** {t_status['entry_time']} min")
                    st.write(f"**Pending amount:** Rs {t_status['pending_amount']}")
                    hist_str = t_status["history"]
                    st.write(f"**Symbols so far:** `{hist_str}`")
                    st.button(
                        "Send to String Tester",
                        on_click=on_send_to_tester,
                        key="gate_send_tester_btn",
                    )

    if st.session_state["scan_log"]:
        st.divider()
        st.subheader("Session Scan Log")
        st.dataframe(st.session_state["scan_log"], use_container_width=True)

# ===========================================================================
# TAB 3 — STRING TESTER
# ===========================================================================
with tab_tester:
    st.subheader("Pure Automata String Evaluation")

    st.radio(
        "Automaton:",
        options=["Journey DFA", "Booking DFA"],
        horizontal=True,
        key="tester_dfa_kind",
    )

    tester_kind = st.session_state["tester_dfa_kind"]

    # Quick example buttons — use on_click so they don't re-trigger on rerun
    st.write("**Quick examples:**")
    if tester_kind == "Journey DFA":
        journey_exs = ["ED", "EX", "EOP", "ETP", "EOOP", "EO", "ET", "EE", "D", "EDR"]
        ex_cols = st.columns(len(journey_exs))
        for col, ex in zip(ex_cols, journey_exs):
            col.button(
                ex,
                key=f"ex_{ex}",
                on_click=_set_tester_seq,
                args=(ex, "Journey DFA"),
            )
    else:
        c1, c2 = st.columns(2)
        c1.button(
            "Valid+retry",
            key="ex_b_valid",
            on_click=_set_tester_seq,
            args=("src dst confirm confirm pay_fail pay_ok gen", "Booking DFA"),
        )
        c2.button(
            "Invalid skip",
            key="ex_b_invalid",
            on_click=_set_tester_seq,
            args=("src confirm pay_ok gen", "Booking DFA"),
        )

    st.text_input("Symbol sequence:", key="tester_sequence")

    if st.button("Run", type="primary"):
        seq_text = st.session_state["tester_sequence"]
        kind_key = "journey" if tester_kind == "Journey DFA" else "booking"
        try:
            symbols = ui_helpers.parse_sequence(seq_text, kind_key)
            target_dfa = JOURNEY_DFA if tester_kind == "Journey DFA" else BOOKING_DFA

            accepted, trace = target_dfa.run(symbols)

            c_res, c_diag = st.columns([1, 1])
            with c_res:
                if accepted:
                    st.success("## ✅ ACCEPTED")
                else:
                    st.error("## ❌ REJECTED")

                st.write(
                    f"**Final state:** `{trace.final_state}` "
                    f"({ui_helpers.STATE_LABELS.get(trace.final_state, '')})"
                )
                st.write(f"**Reason:** {trace.reason}")

                # Regex check
                if tester_kind == "Journey DFA":
                    reg_ok = check_journey_regex(symbols)
                    reg_expr = JOURNEY_REGEX
                else:
                    reg_ok = check_booking_regex(symbols, corrected=True)
                    reg_expr = BOOKING_REGEX_CORRECTED

                st.code(f"Regex: {reg_expr}", language="text")
                st.write(f"**Regex verdict:** {'✅ Accepted' if reg_ok else '❌ Rejected'}")

                unknowns = [s for s in symbols if s not in target_dfa.alphabet]
                if unknowns:
                    st.warning(f"Unknown symbols: {unknowns}")
                elif accepted == reg_ok:
                    st.success("🤝 DFA and regex **AGREE**.")
                else:
                    st.info("ℹ️ DFA and regex disagree on this trace (e.g. cancel paths not in regex).")

                st.write("**Execution trace:**")
                st.table(trace)

            with c_diag:
                st.write("**State diagram (final state highlighted):**")
                t_rows = (
                    get_journey_transition_table()
                    if tester_kind == "Journey DFA"
                    else get_booking_transition_table()
                )
                try:
                    dot = ui_helpers.build_dot(
                        t_rows,
                        current_state=trace.final_state,
                        accepting=target_dfa.final_states,
                        dead=target_dfa.dead_state,
                    )
                    st.graphviz_chart(dot)
                except Exception as exc:
                    st.error(f"Diagram error: {exc}")

        except Exception as exc:
            st.error(f"Error running sequence: {exc}")

# ===========================================================================
# TAB 4 — AUTOMATA VIEWER
# ===========================================================================
with tab_viewer:
    st.subheader("Formal Automata Theory")

    v1, v2, v3, v4, v5 = st.tabs([
        "Journey DFA",
        "Booking DFA",
        "Moore & Mealy",
        "NFA → DFA",
        "Minimization",
    ])

    with v1:
        st.markdown("### Journey Lifecycle DFA")
        st.write("Models the full lifecycle of one metro ticket through gate scans.")
        st.table(get_journey_transition_table())
        st.code(f"Regex: {JOURNEY_REGEX}", language="text")
        c_sl, c_sy = st.columns(2)
        with c_sl:
            st.write("**States:**")
            for s in JOURNEY_DFA.states:
                st.write(f"- `{s}` : {ui_helpers.STATE_LABELS.get(s, s)}")
        with c_sy:
            st.write("**Symbols:**")
            for a in JOURNEY_DFA.alphabet:
                st.write(f"- `{a}` : {ui_helpers.SYMBOL_MEANINGS.get(a, a)}")
        try:
            st.graphviz_chart(ui_helpers.build_dot(
                get_journey_transition_table(),
                accepting=JOURNEY_DFA.final_states,
                dead=JOURNEY_DFA.dead_state,
            ))
        except Exception as exc:
            st.error(str(exc))

    with v2:
        st.markdown("### Kiosk Booking DFA")
        st.write("Models the ticket purchase flow at a kiosk.")
        st.table(get_booking_transition_table())
        st.write("**As written in README (1 confirm):**")
        st.code(BOOKING_REGEX_AS_WRITTEN, language="text")
        st.write("**Corrected (2 confirms):**")
        st.code(BOOKING_REGEX_CORRECTED, language="text")
        st.info(
            "The corrected regex requires two `confirm` symbols because the kiosk "
            "has two distinct steps: showing the fare (q2→q3) and proceeding to pay (q3→q4)."
        )
        try:
            st.graphviz_chart(ui_helpers.build_dot(
                get_booking_transition_table(),
                accepting=BOOKING_DFA.final_states,
                dead=BOOKING_DFA.dead_state,
            ))
        except Exception as exc:
            st.error(str(exc))

    with v3:
        st.markdown("### Moore Machine vs Mealy Machine")
        st.info(
            "**Moore:** output depends only on the *state entered* — same output "
            "regardless of which symbol caused the transition.  "
            "**Mealy:** output depends on the *transition taken* (state + symbol)."
        )
        m1, m2 = st.columns(2)
        m1.markdown("#### Moore (state output)")
        m1.table(get_moore_table())
        m2.markdown("#### Mealy (transition output)")
        m2.table(get_mealy_table())

    with v4:
        st.markdown("### Payment NFA → DFA (Subset Construction)")
        st.info(
            "This NFA models non-deterministic payment method choice "
            "(UPI / card / cash branches via ε-transitions). "
            "The physical kiosk accepts **cash only**; this is a theory demo."
        )
        try:
            subset_data = get_subset_steps()
            st.markdown("#### Payment NFA transition table")
            st.table(subset_data["nfa_transition_table"])
            st.markdown("#### Subset construction table")
            st.table(subset_data["display_rows"])
            st.markdown("#### DFA state → NFA subset")
            st.json(subset_data["name_to_subset"])
        except Exception as exc:
            st.error(str(exc))

    with v5:
        st.markdown("### DFA Minimization (Myhill-Nerode Table-Filling)")
        st.write(
            "The redundant 8-state Booking DFA has two equivalent states "
            "(`PaidCash` and `PaidUPI`) that merge into one, giving a 7-state minimal DFA."
        )
        if st.button("Run Table-Filling Minimization", key="btn_minimize"):
            try:
                min_data = get_minimization_steps()
                st.success(
                    f"Reduced from **{min_data['before_state_count']}** to "
                    f"**{min_data['after_state_count']}** states."
                )
                st.caption(min_data["counting_rule"])

                st.markdown("#### Distinguishability table")
                st.dataframe(min_data["display_table"], use_container_width=True)

                st.markdown("#### Equivalent pairs & merges")
                st.write(f"Unmarked pairs: `{min_data['unmarked_pairs_str']}`")
                for note in min_data["merged_notes"]:
                    st.info(note)

                st.markdown("#### Minimized DFA")
                st.table(min_data["minimized_dfa"].get_transition_table())
            except Exception as exc:
                st.error(str(exc))
