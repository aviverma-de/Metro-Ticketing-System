"""
Automata Theory Core Engine
---------------------------
Implements pure, abstract Deterministic Finite Automaton (DFA) models
and execution tracing for the Metro Ticketing & Journey Validation System.

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
        if isinstance(sequence, str):
            all_single_char = all(len(s) == 1 for s in self.alphabet)
            if all_single_char:
                symbols: List[str] = list(sequence)
            else:
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

        if accepted:
            reason = "Accepted"
        elif unknown_symbol_encountered is not None:
            reason = f"Unknown symbol '{unknown_symbol_encountered}' not in alphabet"
        elif curr_state == self.dead_state or dead_state_entered:
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