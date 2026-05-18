import json
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional
from enum import Enum, auto


# ------------------------------------------------------------------------------
# Production
# ------------------------------------------------------------------------------

@dataclass
class Production:
    non_terminal: str
    transaction: list[str]

    def __eq__(self, other):
        return (self.non_terminal == other.non_terminal and
                self.transaction == other.transaction)

    def __hash__(self):
        return hash((self.non_terminal, tuple(self.transaction)))

    def __lt__(self, other):
        if self.non_terminal != other.non_terminal:
            return self.non_terminal < other.non_terminal
        return self.transaction < other.transaction

    def __repr__(self):
        return f"{self.non_terminal} -> {' '.join(self.transaction)}"


# ------------------------------------------------------------------------------
# Grammar
# Soporta una forma de construccion:
#   1. grammar.add_production("S'", ["S"])           (manual, como antes)
# ------------------------------------------------------------------------------

class Grammar:
    def __init__(self):
        self.productions: list[Production] = []
        self.simbolo_inicial: Optional[str] = None

    def add_production(self, non_terminal: str, transaction: list[str]):
        self.productions.append(Production(non_terminal, transaction))


    def non_terminals(self) -> set[str]:
        return {p.non_terminal for p in self.productions}

    def terminals(self) -> set[str]:
        nt = self.non_terminals()
        result = {"$"}
        for p in self.productions:
            for sym in p.transaction:
                if sym not in nt:
                    result.add(sym)
        return result

    def productions_of(self, nt: str) -> list[Production]:
        return [p for p in self.productions if p.non_terminal == nt]


# ------------------------------------------------------------------------------
# FIRST sets
# ------------------------------------------------------------------------------

def compute_first(grammar: Grammar) -> dict[str, set[str]]:
    nt = grammar.non_terminals()
    first: dict[str, set[str]] = defaultdict(set)

    for p in grammar.productions:
        for sym in p.transaction:
            if sym not in nt:
                first[sym].add(sym)
    first["$"].add("$")

    changed = True
    while changed:
        changed = False
        for p in grammar.productions:
            F = first[p.non_terminal]
            all_eps = True
            for sym in p.transaction:
                before = len(F)
                F |= first[sym] - {"e"}
                if len(F) > before:
                    changed = True
                if "e" not in first[sym]:
                    all_eps = False
                    break
            if all_eps and "e" not in F:
                F.add("e")
                changed = True

    return first


def first_of_sequence(seq: list[str], first_sets: dict[str, set[str]]) -> set[str]:
    result = set()
    all_eps = True
    for sym in seq:
        fs = first_sets.get(sym, set())
        result |= fs - {"e"}
        if "e" not in fs:
            all_eps = False
            break
    if all_eps:
        result.add("e")
    return result


# ------------------------------------------------------------------------------
# LR1 Item
# ------------------------------------------------------------------------------

@dataclass
class LR1Item:
    production: Production
    dot_pos: int
    lookaheads: frozenset

    def next_symbol(self) -> Optional[str]:
        if self.dot_pos < len(self.production.transaction):
            return self.production.transaction[self.dot_pos]
        return None

    def beta(self) -> list[str]:
        return self.production.transaction[self.dot_pos + 1:]

    def is_reduce(self) -> bool:
        return self.dot_pos == len(self.production.transaction)

    def same_core(self, other: "LR1Item") -> bool:
        return self.production == other.production and self.dot_pos == other.dot_pos

    def __eq__(self, other):
        return (self.production == other.production and
                self.dot_pos == other.dot_pos and
                self.lookaheads == other.lookaheads)

    def __hash__(self):
        return hash((self.production, self.dot_pos, self.lookaheads))

    def __lt__(self, other):
        if self.production != other.production:
            return self.production < other.production
        if self.dot_pos != other.dot_pos:
            return self.dot_pos < other.dot_pos
        return sorted(self.lookaheads) < sorted(other.lookaheads)

    def to_str(self) -> str:
        """
        Formato: "E -> E • + T , $/+"
        Usa bullet (punto LR) como en el documento.
        """
        syms = list(self.production.transaction)
        syms.insert(self.dot_pos, ".")
        la = "/".join(sorted(self.lookaheads))
        return f"{self.production.non_terminal} -> {' '.join(syms)} , {la}"


# ------------------------------------------------------------------------------
# LR1 State
# ------------------------------------------------------------------------------

class LR1State:
    def __init__(self, state_id: int):
        self.id = state_id
        self._cores: list[tuple[Production, int]] = []
        self._lookaheads: list[set[str]] = []

    def add_item(self, item: LR1Item) -> bool:
        for i, (prod, dot) in enumerate(self._cores):
            if prod == item.production and dot == item.dot_pos:
                before = len(self._lookaheads[i])
                self._lookaheads[i] |= set(item.lookaheads)
                return len(self._lookaheads[i]) > before
        self._cores.append((item.production, item.dot_pos))
        self._lookaheads.append(set(item.lookaheads))
        return True

    def items(self) -> list[LR1Item]:
        return [
            LR1Item(prod, dot, frozenset(la))
            for (prod, dot), la in zip(self._cores, self._lookaheads)
        ]

    def same_items(self, other: "LR1State") -> bool:
        return self.items() == other.items()


# ------------------------------------------------------------------------------
# Closure y Goto
# ------------------------------------------------------------------------------

def closure(state: LR1State, grammar: Grammar, first_sets: dict) -> LR1State:
    nt = grammar.non_terminals()
    changed = True
    while changed:
        changed = False
        for item in state.items():
            ns = item.next_symbol()
            if ns is None or ns not in nt:
                continue
            for prod in grammar.productions_of(ns):
                beta_seq = item.beta()
                new_la = set()
                for la in item.lookaheads:
                    seq = beta_seq + [la]
                    f = first_of_sequence(seq, first_sets)
                    new_la |= f - {"e"}
                new_item = LR1Item(prod, 0, frozenset(new_la))
                if state.add_item(new_item):
                    changed = True
    return state


def goto_state(state: LR1State, symbol: str, state_id: int,
               grammar: Grammar, first_sets: dict) -> LR1State:
    next_state = LR1State(state_id)
    for item in state.items():
        if item.next_symbol() == symbol:
            moved = LR1Item(item.production, item.dot_pos + 1, item.lookaheads)
            next_state.add_item(moved)
    return closure(next_state, grammar, first_sets)


# ------------------------------------------------------------------------------
# Action
# ------------------------------------------------------------------------------

class ActionType(Enum):
    SHIFT  = auto()
    REDUCE = auto()
    ACCEPT = auto()
    ERROR  = auto()


@dataclass
class Action:
    type: ActionType = ActionType.ERROR
    value: int = -1
    reduce_prod: Optional[Production] = None

    def __eq__(self, other):
        return self.type == other.type and self.value == other.value

    def to_str(self) -> str:
        if self.type == ActionType.SHIFT:
            return f"S{self.value}"
        if self.type == ActionType.REDUCE:
            body = " ".join(self.reduce_prod.transaction)
            return f"R({self.reduce_prod.non_terminal} -> {body})"
        if self.type == ActionType.ACCEPT:
            return "ACC"
        return ""


# ------------------------------------------------------------------------------
# LR Table
# ------------------------------------------------------------------------------

class LRTable:
    def __init__(self):
        self.action: dict[int, dict[str, Action]] = defaultdict(dict)
        self.goto_table: dict[int, dict[str, int]] = defaultdict(dict)
        self.conflicts: list[dict] = []

    def set_action(self, state: int, sym: str, act: Action):
        existing = self.action[state].get(sym)
        if existing and existing != act:
            self.conflicts.append({
                "estado": state,
                "simbolo": sym,
                "conflicto": f"{existing.to_str()} vs {act.to_str()}"
            })
        self.action[state][sym] = act

    def to_json(self, terminals: set[str], non_terminals: set[str]) -> dict:
        """
        {
          "tipo": "LR",
          "columnas": ["Estado", "id", "+", ...],
          "filas": [{"Estado": "0", "id": "S5", ...}, ...]
          "conflictos": [...]
        }
        """
        terms = sorted(terminals)
        nts   = sorted(s for s in non_terminals if not s.endswith("'"))

        columnas = ["Estado"] + terms + nts

        all_states = sorted(set(self.action.keys()) | set(self.goto_table.keys()))

        filas = []
        for st in all_states:
            fila: dict[str, str] = {"Estado": str(st)}
            for t in terms:
                act = self.action[st].get(t)
                if act:
                    fila[t] = act.to_str()
            for nt in nts:
                dst = self.goto_table[st].get(nt)
                if dst is not None:
                    fila[nt] = str(dst)
            filas.append(fila)

        return {
            "tipo": "LR",
            "columnas": columnas,
            "filas": filas,
            "conflictos": self.conflicts
        }


# ------------------------------------------------------------------------------
# Parser LR1
# ------------------------------------------------------------------------------

class ParserLR1:
    def __init__(self):
        self.grammar: Optional[Grammar] = None
        self._afn_states: list[LR1State] = []
        self._transitions: dict[int, dict[str, int]] = defaultdict(dict)
        self.table = LRTable()
        self.first_sets: dict = {}

    def build(self, grammar: Grammar):
        self.grammar = grammar
        self.first_sets = compute_first(grammar)

        start_prod = grammar.productions[0]
        start_item = LR1Item(start_prod, 0, frozenset({"$"}))
        s0 = LR1State(0)
        s0.add_item(start_item)
        s0 = closure(s0, grammar, self.first_sets)
        self._afn_states.append(s0)

        all_symbols = set()
        for p in grammar.productions:
            all_symbols.add(p.non_terminal)
            for sym in p.transaction:
                all_symbols.add(sym)

        pending = [0]
        while pending:
            cur_id = pending.pop(0)
            cur = self._afn_states[cur_id]

            for sym in sorted(all_symbols):
                next_id = len(self._afn_states)
                nxt = goto_state(cur, sym, next_id, grammar, self.first_sets)
                if not nxt.items():
                    continue

                found_id = -1
                for st in self._afn_states:
                    if st.same_items(nxt):
                        found_id = st.id
                        break

                if found_id == -1:
                    self._afn_states.append(nxt)
                    self._transitions[cur_id][sym] = next_id
                    pending.append(next_id)
                else:
                    self._transitions[cur_id][sym] = found_id

        terms = grammar.terminals()
        nts   = grammar.non_terminals()

        for state in self._afn_states:
            trans = self._transitions.get(state.id, {})
            for sym, dst in trans.items():
                if sym in terms:
                    self.table.set_action(state.id, sym, Action(ActionType.SHIFT, dst))
                else:
                    self.table.goto_table[state.id][sym] = dst

            for item in state.items():
                if not item.is_reduce():
                    continue
                prod = item.production
                if (prod.non_terminal == grammar.productions[0].non_terminal and
                        prod == grammar.productions[0]):
                    self.table.set_action(state.id, "$", Action(ActionType.ACCEPT))
                else:
                    for la in item.lookaheads:
                        self.table.set_action(state.id, la,
                                              Action(ActionType.REDUCE, -1, prod))

    def afn_closure_to_json(self) -> dict:
        """
        {
          "tipo": "LR1",
          "estados": [
            {
              "estado": "I0",
              "items": ["E' -> . E , $", ...],
              "transiciones": {"E": "I1", ...}
            }, ...
          ]
        }
        """
        estados = []
        for state in self._afn_states:
            trans = self._transitions.get(state.id, {})
            estados.append({
                "estado": f"I{state.id}",
                "items": [it.to_str() for it in state.items()],
                "transiciones": {
                    sym: f"I{dst}"
                    for sym, dst in sorted(trans.items())
                }
            })
        return {"tipo": "LR1", "estados": estados}

    def accept(self, tokens: list[str]) -> dict:
        """
        {
          "cadena_valida": bool,
          "mensaje": str,
          "proceso_paso_a_paso": [
            {"paso": 1, "pila": "0", "entrada": "id * id $", "accion": "..."},
            ...
          ]
        }
        """
        inp = tokens + ["$"]
        steps = []
        state_stack  = [0]
        symbol_stack: list[str] = []
        pos      = 0
        paso     = 1
        accepted = False
        mensaje  = ""

        while True:
            cur_state = state_stack[-1]
            token     = inp[pos]

            # Pila con estados y simbolos intercalados: "0 id 5 * 7"
            pila_parts = [str(state_stack[0])]
            for sym, st in zip(symbol_stack, state_stack[1:]):
                pila_parts.append(sym)
                pila_parts.append(str(st))
            pila_str   = " ".join(pila_parts)
            entrada_str = " ".join(inp[pos:])

            act = self.table.action[cur_state].get(token, Action())

            if act.type == ActionType.SHIFT:
                steps.append({
                    "paso":    paso,
                    "pila":    pila_str,
                    "entrada": entrada_str,
                    "accion":  f"Desplazar (Shift) al estado {act.value}"
                })
                symbol_stack.append(token)
                state_stack.append(act.value)
                pos += 1

            elif act.type == ActionType.REDUCE:
                prod = act.reduce_prod
                body = " ".join(prod.transaction)
                steps.append({
                    "paso":    paso,
                    "pila":    pila_str,
                    "entrada": entrada_str,
                    "accion":  f"Reducir (Reduce) por {prod.non_terminal} -> {body}"
                })
                for _ in prod.transaction:
                    state_stack.pop()
                    symbol_stack.pop()
                symbol_stack.append(prod.non_terminal)
                top  = state_stack[-1]
                goto = self.table.goto_table[top].get(prod.non_terminal, -1)
                if goto == -1:
                    mensaje = (f"Error interno: GOTO faltante para estado "
                               f"{top} con {prod.non_terminal}")
                    break
                state_stack.append(goto)

            elif act.type == ActionType.ACCEPT:
                steps.append({
                    "paso":    paso,
                    "pila":    pila_str,
                    "entrada": entrada_str,
                    "accion":  "Aceptar (ACC)"
                })
                accepted = True
                mensaje  = "La cadena fue aceptada exitosamente."
                break

            else:
                steps.append({
                    "paso":    paso,
                    "pila":    pila_str,
                    "entrada": entrada_str,
                    "accion":  (f"Error: no hay accion para '{token}' "
                                f"en estado {cur_state}")
                })
                mensaje = (f"La cadena fue rechazada. "
                           f"Token inesperado '{token}' en estado {cur_state}.")
                break

            paso += 1

        return {
            "cadena_valida":       accepted,
            "mensaje":             mensaje,
            "proceso_paso_a_paso": steps
        }

    def run(self, tokens: list[str]) -> dict:
        """
        Devuelve el JSON completo segun el contrato del documento.
        """
        parse_result = self.accept(tokens)
        return {
            "cadena_valida":       parse_result["cadena_valida"],
            "mensaje":             parse_result["mensaje"],
            "afn_clausura":        self.afn_closure_to_json(),
            "construccion_tablas": self.table.to_json(
                                       self.grammar.terminals(),
                                       self.grammar.non_terminals()
                                   ),
            "proceso_paso_a_paso": parse_result["proceso_paso_a_paso"]
        }




# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

if __name__ == "__main__":

    # --- Ejemplo: construyendo Grammar manualmente (como antes) ---
    grammar = Grammar()
    grammar.add_production("S'", ["S"])
    grammar.add_production("S",  ["S", "a"])
    grammar.add_production("S",  ["b"])

    lr1 = ParserLR1()
    lr1.build(grammar)
    result2 = lr1.run(["b", "a", "a", "a", "a"])
    print(json.dumps(result2, ensure_ascii=False, indent=2))