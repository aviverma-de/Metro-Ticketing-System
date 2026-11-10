"""
Automata Theory Core Engine
---------------------------
Implements pure, abstract automata theory models and algorithms:
- Deterministic Finite Automaton (DFA)
- Nondeterministic Finite Automaton (NFA) with epsilon transitions
- Subset Construction (NFA to DFA conversion)
- DFA Minimization using the Myhill-Nerode table-filling algorithm
- Moore Machine (state-dependent outputs)
- Mealy Machine (transition-dependent outputs)

Educational, strictly typed, standard library only.
"""

from typing import Any, Dict, List, Optional, Set, Tuple, Union


class TraceList(list):
    """
    A list subclass for execution traces that remains 100% compatible with
    standard Python lists and Streamlit display, while providing convenient
    attributes for viva explanation and UI summary.
    """
    def __init__(
        self,
        iterable: Optional[List[Dict[str, Any]]] = None,
        reason: str = "",
        final_state: str = "",
        states: Optional[List[str]] = None,
        accepted: bool = False,
    ):
        super().__init__(iterable or [])
        self.reason: str = reason
        self.final_state: str = final_state
        self.states: List[str] = states or []
        self.accepted: bool = accepted


class DFA:
    """
    Deterministic Finite Automaton (DFA) defined as a 5-tuple:
    (Q, Sigma, delta, q0, F)
    where:
      - Q: Finite set of states
      - Sigma: Finite set of input symbols (alphabet)
      - delta: Transition function Q x Sigma -> Q
      - q0: Start state (in Q)
      - F: Set of accepting / final states (subset of Q)
    """

    def __init__(
        self,
        states: Union[Set[str], List[str]],
        alphabet: Union[Set[str], List[str]],
        transitions: Dict[Tuple[str, str], str],
        start_state: str,
        final_states: Union[Set[str], List[str]],
        dead_state: Optional[str] = None,
    ) -> None:
        self.states: List[str] = list(dict.fromkeys(states))
        self.alphabet: List[str] = list(dict.fromkeys(alphabet))
        self.transitions: Dict[Tuple[str, str], str] = dict(transitions)
        self.start_state: str = start_state
        self.final_states: Set[str] = set(final_states)

        # Detect or assign dead state name
        if dead_state is not None:
            self.dead_state: str = dead_state
        elif "qd" in self.states:
            self.dead_state = "qd"
        elif "JT" in self.states:
            self.dead_state = "JT"
        else:
            self.dead_state = "_DEAD_"

        # Ensure dead state is in states list
        if self.dead_state not in self.states:
            self.states.append(self.dead_state)

        # Ensure dead state loops on every symbol in alphabet
        for sym in self.alphabet:
            self.transitions.setdefault((self.dead_state, sym), self.dead_state)

        # Execution memory for last run
        self.last_accepted: Optional[bool] = None
        self.last_trace: Optional[TraceList] = None
        self.last_reason: str = ""
        self.last_final_state: str = ""

    def step(self, state: str, symbol: str) -> str:
        """
        Takes one step from `state` reading `symbol`.
        Returns the next state. Unknown symbols or missing transitions
        cleanly transition to the dead state.
        """
        if symbol not in self.alphabet:
            return self.dead_state
        return self.transitions.get((state, symbol), self.dead_state)

    def is_accepting(self, state: str) -> bool:
        """Returns True if `state` is an accepting state."""
        return state in self.final_states

    def run(self, sequence: Union[str, List[str]]) -> Tuple[bool, TraceList]:
        """
        Simulates the DFA on an input sequence.
        Accepts:
          - A list of symbols, e.g. ['src', 'dst', 'confirm']
          - A compact string for single-char alphabets, e.g. "EOP"
        Returns:
          (accepted, trace)
        """
        # Normalize compact string vs symbol list
        if isinstance(sequence, str):
            # If all symbols in alphabet are length 1, treat string as chars
            all_single_char = all(len(s) == 1 for s in self.alphabet)
            if all_single_char:
                symbols: List[str] = list(sequence)
            else:
                # If sequence has whitespace, allow split, else single item
                symbols = sequence.split() if " " in sequence else [sequence]
        else:
            symbols = list(sequence)

        curr_state = self.start_state
        states_visited: List[str] = [curr_state]
        trace_steps: List[Dict[str, Any]] = []
        dead_state_entered = False
        unknown_symbol_encountered: Optional[str] = None

        for idx, sym in enumerate(symbols, start=1):
            from_st = curr_state
            if sym not in self.alphabet:
                unknown_symbol_encountered = sym
                to_st = self.dead_state
                dead_state_entered = True
            else:
                to_st = self.transitions.get((from_st, sym), self.dead_state)
                if to_st == self.dead_state and from_st != self.dead_state:
                    dead_state_entered = True

            trace_steps.append({
                "step": idx,
                "from": from_st,
                "from_state": from_st,
                "symbol": sym,
                "to": to_st,
                "to_state": to_st,
            })
            curr_state = to_st
            states_visited.append(curr_state)

        accepted = self.is_accepting(curr_state)

        # Determine human-readable reason
        if accepted:
            reason = "Accepted"
        elif unknown_symbol_encountered is not None:
            reason = f"Unknown symbol '{unknown_symbol_encountered}' not in alphabet"
        elif curr_state == self.dead_state or dead_state_entered:
            # Match contract phrasing: "entered the dead or trap state"
            if self.dead_state == "JT":
                reason = "entered the trap state"
            else:
                reason = "entered the dead state"
        else:
            reason = "ended in a non-accepting state"

        result_trace = TraceList(
            trace_steps,
            reason=reason,
            final_state=curr_state,
            states=states_visited,
            accepted=accepted,
        )

        self.last_accepted = accepted
        self.last_trace = result_trace
        self.last_reason = reason
        self.last_final_state = curr_state

        return accepted, result_trace

    def get_rejection_reason(self) -> str:
        """Returns the reason for the last rejection or acceptance."""
        return self.last_reason

    def get_transition_table(self) -> List[Dict[str, str]]:
        """
        Returns the transition table formatted as a list of dictionaries,
        one dictionary per state, ideal for display in Streamlit tables.
        """
        rows: List[Dict[str, str]] = []
        for st in self.states:
            row: Dict[str, str] = {"State": st}
            for sym in self.alphabet:
                row[sym] = self.transitions.get((st, sym), self.dead_state)
            rows.append(row)
        return rows

    def __repr__(self) -> str:
        return (
            f"DFA(states={self.states}, alphabet={self.alphabet}, "
            f"start_state='{self.start_state}', final_states={sorted(self.final_states)})"
        )


class NFA:
    """
    Nondeterministic Finite Automaton (NFA) with epsilon transitions:
    (Q, Sigma, delta, q0, F)
    where delta: Q x (Sigma union {epsilon}) -> 2^Q
    """

    def __init__(
        self,
        states: Union[Set[str], List[str]],
        alphabet: Union[Set[str], List[str]],
        transitions: Dict[Tuple[str, str], Union[Set[str], List[str]]],
        start_state: str,
        final_states: Union[Set[str], List[str]],
        epsilon_symbol: str = "",
    ) -> None:
        self.states: List[str] = list(dict.fromkeys(states))
        self.alphabet: List[str] = list(dict.fromkeys(alphabet))
        self.start_state: str = start_state
        self.final_states: Set[str] = set(final_states)
        self.epsilon_symbol: str = epsilon_symbol

        # Standardize transitions: (state, symbol) -> set of next states
        self.transitions: Dict[Tuple[str, str], Set[str]] = {}
        for (st, sym), targets in transitions.items():
            self.transitions[(st, sym)] = set(targets)

    def epsilon_closure(self, states: Union[Set[str], List[str]]) -> Set[str]:
        """
        Computes the epsilon-closure of a set of states: all states reachable
        via zero or more epsilon transitions.
        """
        closure: Set[str] = set(states)
        stack: List[str] = list(closure)

        while stack:
            st = stack.pop()
            # Check epsilon moves
            next_states = self.transitions.get((st, self.epsilon_symbol), set())
            for nxt in next_states:
                if nxt not in closure:
                    closure.add(nxt)
                    stack.append(nxt)
        return closure

    def step(self, current_states: Union[Set[str], List[str]], symbol: str) -> Set[str]:
        """
        Moves from a set of states on `symbol`, followed by epsilon-closure.
        """
        next_states: Set[str] = set()
        for st in current_states:
            targets = self.transitions.get((st, symbol), set())
            next_states.update(targets)
        return self.epsilon_closure(next_states)

    def run(self, sequence: Union[str, List[str]]) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Simulates the NFA on an input sequence.
        Returns (accepted, trace_steps).
        """
        if isinstance(sequence, str):
            all_single_char = all(len(s) == 1 for s in self.alphabet)
            symbols = list(sequence) if all_single_char else sequence.split()
        else:
            symbols = list(sequence)

        curr_states = self.epsilon_closure({self.start_state})
        trace: List[Dict[str, Any]] = [{
            "step": 0,
            "symbol": "START",
            "active_states": sorted(curr_states),
        }]

        for idx, sym in enumerate(symbols, start=1):
            curr_states = self.step(curr_states, sym)
            trace.append({
                "step": idx,
                "symbol": sym,
                "active_states": sorted(curr_states),
            })

        accepted = bool(curr_states & self.final_states)
        return accepted, trace

    def get_transition_table(self) -> List[Dict[str, str]]:
        """Returns plain display rows for the NFA's transition table."""
        columns = list(self.alphabet) + ["ε"]
        rows: List[Dict[str, str]] = []
        for st in self.states:
            row: Dict[str, str] = {"State": st}
            for sym in self.alphabet:
                targets = self.transitions.get((st, sym), set())
                row[sym] = "{" + ", ".join(sorted(targets)) + "}" if targets else "∅"
            eps_targets = self.transitions.get((st, self.epsilon_symbol), set())
            row["ε"] = "{" + ", ".join(sorted(eps_targets)) + "}" if eps_targets else "∅"
            rows.append(row)
        return rows


def subset_construction(nfa: NFA) -> Tuple[DFA, Dict[str, Any]]:
    """
    Converts an NFA with epsilon transitions into an equivalent DFA using
    the subset construction algorithm.

    Returns:
      (dfa, steps_data)
      where steps_data contains full step-by-step intermediate details,
      discovery order, and display-friendly tables.
    """
    initial_subset = frozenset(nfa.epsilon_closure({nfa.start_state}))

    dfa_state_names: Dict[frozenset, str] = {initial_subset: "D0"}
    subset_to_name: Dict[frozenset, str] = {initial_subset: "D0"}
    name_to_subset: Dict[str, List[str]] = {"D0": sorted(initial_subset)}

    discovery_order: List[str] = ["D0"]
    queue: List[frozenset] = [initial_subset]

    dfa_transitions: Dict[Tuple[str, str], str] = {}
    subset_steps: List[Dict[str, Any]] = []

    state_counter = 1

    while queue:
        current_subset = queue.pop(0)
        current_name = dfa_state_names[current_subset]
        is_acc = bool(current_subset & nfa.final_states)

        step_record: Dict[str, Any] = {
            "dfa_state": current_name,
            "nfa_subset": sorted(current_subset),
            "nfa_subset_str": "{" + ", ".join(sorted(current_subset)) + "}",
            "transitions": {},
            "is_accepting": is_acc,
        }

        for sym in nfa.alphabet:
            # Compute move and epsilon-closure
            move_states: Set[str] = set()
            for st in current_subset:
                move_states.update(nfa.transitions.get((st, sym), set()))
            next_subset = frozenset(nfa.epsilon_closure(move_states))

            if not next_subset:
                # Target is the empty set (dead state)
                target_name = "DEAD"
            else:
                if next_subset not in dfa_state_names:
                    target_name = f"D{state_counter}"
                    state_counter += 1
                    dfa_state_names[next_subset] = target_name
                    name_to_subset[target_name] = sorted(next_subset)
                    discovery_order.append(target_name)
                    queue.append(next_subset)
                else:
                    target_name = dfa_state_names[next_subset]

            dfa_transitions[(current_name, sym)] = target_name
            step_record["transitions"][sym] = {
                "target_dfa_state": target_name,
                "target_nfa_subset": sorted(next_subset),
                "target_nfa_subset_str": "{" + ", ".join(sorted(next_subset)) + "}" if next_subset else "∅",
            }

        subset_steps.append(step_record)

    # Build DFA state list and final states
    dfa_states = list(discovery_order)
    if any(tgt == "DEAD" for tgt in dfa_transitions.values()):
        if "DEAD" not in dfa_states:
            dfa_states.append("DEAD")
            for sym in nfa.alphabet:
                dfa_transitions[("DEAD", sym)] = "DEAD"

    dfa_final_states = [
        name for name, subset in name_to_subset.items()
        if bool(set(subset) & nfa.final_states)
    ]

    dfa = DFA(
        states=dfa_states,
        alphabet=nfa.alphabet,
        transitions=dfa_transitions,
        start_state="D0",
        final_states=dfa_final_states,
        dead_state="DEAD",
    )

    # Display-friendly flat rows for Streamlit
    display_rows: List[Dict[str, str]] = []
    for step in subset_steps:
        row: Dict[str, str] = {
            "DFA State": step["dfa_state"],
            "NFA Subset": step["nfa_subset_str"],
            "Accepting": "Yes" if step["is_accepting"] else "No",
        }
        for sym in nfa.alphabet:
            tgt_info = step["transitions"][sym]
            row[sym] = f"{tgt_info['target_dfa_state']} {tgt_info['target_nfa_subset_str']}"
        display_rows.append(row)

    steps_data: Dict[str, Any] = {
        "discovery_order": discovery_order,
        "name_to_subset": name_to_subset,
        "subset_steps": subset_steps,
        "display_rows": display_rows,
        "nfa_transition_table": nfa.get_transition_table(),
        "dfa": dfa,
    }

    return dfa, steps_data


def minimize_dfa_table_filling(dfa: DFA) -> Tuple[DFA, Dict[str, Any]]:
    """
    Minimizes a DFA using the Myhill-Nerode table-filling algorithm.
    Does not pre-prune unreachable states (as required by the contract
    so the 8-state redundant kiosk automaton demo strictly demonstrates 8 -> 7).

    Returns:
      (minimized_dfa, step_details)
    """
    # Exclude implicit dead state from explicit state counting if present
    explicit_states = [s for s in dfa.states if s != dfa.dead_state]
    states = sorted(explicit_states)
    n = len(states)

    # All distinct unordered pairs {p, q} with p < q
    all_pairs: List[Tuple[str, str]] = [
        (states[i], states[j])
        for i in range(n)
        for j in range(i + 1, n)
    ]

    marked_pairs: Dict[Tuple[str, str], Dict[str, Any]] = {}
    marking_history: List[Dict[str, Any]] = []

    # Round 0: Mark pairs of one accepting and one non-accepting state
    round_0_marks: List[Dict[str, Any]] = []
    for p, q in all_pairs:
        p_acc = dfa.is_accepting(p)
        q_acc = dfa.is_accepting(q)
        if p_acc != q_acc:
            reason = f"One state is accepting ({q if q_acc else p}) and the other is non-accepting"
            marked_pairs[(p, q)] = {"round": 0, "symbol": None, "reason": reason}
            mark_info = {"round": 0, "pair": (p, q), "pair_str": f"({p}, {q})", "reason": reason}
            round_0_marks.append(mark_info)
            marking_history.append(mark_info)

    # Iterative rounds: repeatedly mark pairs whose transitions lead to an already marked pair
    current_round = 1
    while True:
        round_marks: List[Dict[str, Any]] = []
        for p, q in all_pairs:
            pair = (p, q)
            if pair in marked_pairs:
                continue

            # Check every symbol in alphabet
            for sym in dfa.alphabet:
                p_next = dfa.transitions.get((p, sym), dfa.dead_state)
                q_next = dfa.transitions.get((q, sym), dfa.dead_state)

                if p_next == q_next:
                    continue

                # Distinguishable if one goes to dead state and the other to an active state,
                # or if (p_next, q_next) is already marked
                distinguishable = False
                reason = ""

                # If one is dead state and the other is not dead state
                if (p_next == dfa.dead_state) != (q_next == dfa.dead_state):
                    active_st = p_next if p_next != dfa.dead_state else q_next
                    distinguishable = True
                    reason = f"on symbol '{sym}' {p} -> {p_next} and {q} -> {q_next} (active vs dead state)"
                else:
                    # Both are active states: check if their target pair is already marked
                    target_pair = (min(p_next, q_next), max(p_next, q_next))
                    if target_pair in marked_pairs:
                        distinguishable = True
                        reason = f"on symbol '{sym}' they lead to marked pair ({target_pair[0]}, {target_pair[1]})"

                if distinguishable:
                    marked_pairs[pair] = {
                        "round": current_round,
                        "symbol": sym,
                        "reason": reason,
                    }
                    mark_info = {
                        "round": current_round,
                        "pair": pair,
                        "pair_str": f"({p}, {q})",
                        "symbol": sym,
                        "reason": reason,
                    }
                    round_marks.append(mark_info)
                    marking_history.append(mark_info)
                    break

        if not round_marks:
            break
        current_round += 1

    # Pairs left unmarked are equivalent
    unmarked_pairs = [pair for pair in all_pairs if pair not in marked_pairs]

    # Partition states into equivalence classes using disjoint sets
    parent: Dict[str, str] = {s: s for s in states}

    def find(i: str) -> str:
        if parent[i] == i:
            return i
        parent[i] = find(parent[i])
        return parent[i]

    def union(i: str, j: str) -> None:
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    for p, q in unmarked_pairs:
        union(p, q)

    # Group states by root
    groups: Dict[str, List[str]] = {}
    for s in states:
        root = find(s)
        groups.setdefault(root, []).append(s)

    # Build mapping from old states to merged states
    merged_mapping: Dict[str, str] = {}
    merged_classes: List[List[str]] = []
    for grp in groups.values():
        grp_sorted = sorted(grp)
        merged_classes.append(grp_sorted)
        if len(grp_sorted) > 1:
            merged_name = "_".join(grp_sorted)
        else:
            merged_name = grp_sorted[0]
        for member in grp_sorted:
            merged_mapping[member] = merged_name

    min_states = sorted(list(dict.fromkeys(merged_mapping.values())))
    min_start_state = merged_mapping[dfa.start_state]
    min_final_states = sorted(list(dict.fromkeys(
        merged_mapping[s] for s in dfa.final_states if s in merged_mapping
    )))

    # Construct transitions for minimized DFA
    min_transitions: Dict[Tuple[str, str], str] = {}
    for st in states:
        merged_src = merged_mapping[st]
        for sym in dfa.alphabet:
            nxt = dfa.transitions.get((st, sym), dfa.dead_state)
            if nxt == dfa.dead_state:
                min_transitions[(merged_src, sym)] = dfa.dead_state
            else:
                min_transitions[(merged_src, sym)] = merged_mapping[nxt]

    minimized_dfa = DFA(
        states=min_states + [dfa.dead_state],
        alphabet=dfa.alphabet,
        transitions=min_transitions,
        start_state=min_start_state,
        final_states=min_final_states,
        dead_state=dfa.dead_state,
    )

    # Explanation text for handover
    merged_notes = [
        f"{' and '.join(grp)} merge into {merged_mapping[grp[0]]}"
        for grp in merged_classes if len(grp) > 1
    ]
    if not merged_notes:
        merged_notes = ["No states were equivalent; automaton is already minimal."]

    display_table: List[Dict[str, Any]] = []
    for pair in all_pairs:
        is_marked = pair in marked_pairs
        info = marked_pairs.get(pair, {})
        display_table.append({
            "Pair": f"({pair[0]}, {pair[1]})",
            "Distinguishable": "Yes" if is_marked else "No (Equivalent)",
            "Marked Round": info.get("round", "-"),
            "Reason": info.get("reason", "Equivalent states (unmarked)"),
        })

    step_details: Dict[str, Any] = {
        "before_state_count": len(states),
        "after_state_count": len(min_states),
        "counting_rule": "Implicit dead state is excluded from explicit state counts (8 -> 7).",
        "all_pairs_count": len(all_pairs),
        "marked_pairs_count": len(marked_pairs),
        "marking_history": marking_history,
        "unmarked_pairs": unmarked_pairs,
        "unmarked_pairs_str": [f"({p}, {q})" for p, q in unmarked_pairs],
        "merged_classes": merged_classes,
        "merged_mapping": merged_mapping,
        "merged_notes": merged_notes,
        "display_table": display_table,
        "minimized_dfa": minimized_dfa,
    }

    return minimized_dfa, step_details


class MooreMachine:
    """
    Moore Machine: output is attached to each state.
    Output alphabet Gamma, with output function lambda: Q -> Gamma.
    """

    def __init__(
        self,
        states: Union[Set[str], List[str]],
        alphabet: Union[Set[str], List[str]],
        transitions: Dict[Tuple[str, str], str],
        start_state: str,
        output_table: Dict[str, str],
        dead_state: Optional[str] = None,
        default_output: str = "Gate LOCKED, alarm",
    ) -> None:
        self.states: List[str] = list(dict.fromkeys(states))
        self.alphabet: List[str] = list(dict.fromkeys(alphabet))
        self.transitions: Dict[Tuple[str, str], str] = dict(transitions)
        self.start_state: str = start_state
        self.output_table: Dict[str, str] = dict(output_table)
        self.dead_state: str = dead_state or ("JT" if "JT" in self.states else "qd")
        self.default_output: str = default_output

    def get_output(self, state: str) -> str:
        """Returns the Moore output for `state`."""
        return self.output_table.get(state, self.default_output)

    def step(self, state: str, symbol: str) -> Tuple[str, str]:
        """
        Takes one step from `state` on `symbol`.
        Returns (next_state, output_of_next_state).
        """
        if symbol not in self.alphabet:
            nxt = self.dead_state
        else:
            nxt = self.transitions.get((state, symbol), self.dead_state)
        return nxt, self.get_output(nxt)

    def run(self, sequence: Union[str, List[str]]) -> List[str]:
        """
        Runs the Moore machine on an input sequence.
        Returns one output per input symbol (the output of the state just entered),
        ensuring equal length and seamless 1-to-1 comparison with Mealy outputs.
        """
        if isinstance(sequence, str):
            all_single_char = all(len(s) == 1 for s in self.alphabet)
            symbols = list(sequence) if all_single_char else sequence.split()
        else:
            symbols = list(sequence)

        curr_state = self.start_state
        outputs: List[str] = []
        for sym in symbols:
            curr_state, out = self.step(curr_state, sym)
            outputs.append(out)
        return outputs

    def get_table(self) -> List[Dict[str, str]]:
        """Returns a display-friendly list of dictionaries for Streamlit."""
        rows: List[Dict[str, str]] = []
        for st in self.states:
            row: Dict[str, str] = {
                "State": st,
                "Output": self.get_output(st),
            }
            for sym in self.alphabet:
                row[sym] = self.transitions.get((st, sym), self.dead_state)
            rows.append(row)
        return rows


class MealyMachine:
    """
    Mealy Machine: output is attached to each transition.
    Output function lambda: Q x Sigma -> Gamma.
    """

    def __init__(
        self,
        states: Union[Set[str], List[str]],
        alphabet: Union[Set[str], List[str]],
        transitions: Dict[Tuple[str, str], str],
        start_state: str,
        output_table: Dict[Tuple[str, str], str],
        dead_state: Optional[str] = None,
        default_output: str = "Lock gate, alarm",
    ) -> None:
        self.states: List[str] = list(dict.fromkeys(states))
        self.alphabet: List[str] = list(dict.fromkeys(alphabet))
        self.transitions: Dict[Tuple[str, str], str] = dict(transitions)
        self.start_state: str = start_state
        self.output_table: Dict[Tuple[str, str], str] = dict(output_table)
        self.dead_state: str = dead_state or ("JT" if "JT" in self.states else "qd")
        self.default_output: str = default_output

    def get_output(self, state: str, symbol: str) -> str:
        """Returns the Mealy output for transition (state, symbol)."""
        return self.output_table.get((state, symbol), self.default_output)

    def step(self, state: str, symbol: str) -> Tuple[str, str]:
        """
        Takes one step from `state` on `symbol`.
        Returns (next_state, transition_output).
        """
        if symbol not in self.alphabet:
            nxt = self.dead_state
            out = self.default_output
        else:
            nxt = self.transitions.get((state, symbol), self.dead_state)
            out = self.get_output(state, symbol)
        return nxt, out

    def run(self, sequence: Union[str, List[str]]) -> List[str]:
        """
        Runs the Mealy machine on an input sequence.
        Returns one output per input symbol (the output of the transition taken).
        """
        if isinstance(sequence, str):
            all_single_char = all(len(s) == 1 for s in self.alphabet)
            symbols = list(sequence) if all_single_char else sequence.split()
        else:
            symbols = list(sequence)

        curr_state = self.start_state
        outputs: List[str] = []
        for sym in symbols:
            curr_state, out = self.step(curr_state, sym)
            outputs.append(out)
        return outputs

    def get_table(self) -> List[Dict[str, str]]:
        """Returns a display-friendly list of dictionaries for Streamlit."""
        rows: List[Dict[str, str]] = []
        for st in self.states:
            row: Dict[str, str] = {"State": st}
            for sym in self.alphabet:
                nxt = self.transitions.get((st, sym), self.dead_state)
                out = self.get_output(st, sym)
                row[sym] = f"{nxt} / '{out}'"
            rows.append(row)
        return rows
