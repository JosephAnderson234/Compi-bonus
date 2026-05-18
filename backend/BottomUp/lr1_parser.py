"""
lr1_parser.py
Parser LR1. Importa la infraestructura de lr_base.py.
"""

import json
from collections import defaultdict

from lr_base import (
    Grammar,
    compute_first,
    LR1Item,
    LR1State,
    closure,
    goto_state,
    ActionType,
    Action,
    LRTable,
    run_parser,
)


class ParserLR1:
    def __init__(self):
        self.grammar: Grammar = None
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

    def run(self, tokens: list[str]) -> dict:
        parse_result = run_parser(tokens, self.table)
        return {
            "cadena_valida":       parse_result["cadena_valida"],
            "mensaje":             parse_result["mensaje"],
            "afn_clausura":        self.afn_closure_to_json(),
            "construccion_tablas": self.table.to_json(
                                       self.grammar.terminals(),
                                       self.grammar.non_terminals(),
                                       tipo="LR1"
                                   ),
            "proceso_paso_a_paso": parse_result["proceso_paso_a_paso"]
        }


def run_analysis(input_data: dict) -> dict:
    """Misma interfaz que lr0_parser / slr1_parser."""
    payload = dict(input_data)
    payload.setdefault("tipo_parser", "LR1")
    return parse_request(payload)


def parse_request(request: dict) -> dict:
    """
    Entrada:
        {
          "gramatica":       "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id",
          "simbolo_inicial": "E",
          "cadena_entrada":  "id * id + id",
          "tipo_parser":     "LR1"
        }
    La cadena_entrada ya viene tokenizada con espacios.
    """
    tipo = request.get("tipo_parser", "LR1")
    if tipo != "LR1":
        return {"error": f"tipo_parser '{tipo}' no soportado en lr1_parser (solo LR1)"}

    grammar = Grammar.from_text(
        request["gramatica"],
        simbolo_inicial=request.get("simbolo_inicial")
    )
    tokens = request["cadena_entrada"].strip().split()

    lr1 = ParserLR1()
    lr1.build(grammar)
    return lr1.run(tokens)


if __name__ == "__main__":
    request = {
        "gramatica":       "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id",
        "simbolo_inicial": "E",
        "cadena_entrada":  "id * id + id",
        "tipo_parser":     "LR1"
    }
    print(json.dumps(parse_request(request), ensure_ascii=False, indent=2))

    print("\n" + "-" * 60 + "\n")

    grammar = Grammar()
    grammar.add_production("S'", ["S"])
    grammar.add_production("S",  ["S", "a"])
    grammar.add_production("S",  ["b"])
    lr1 = ParserLR1()
    lr1.build(grammar)
    print(json.dumps(lr1.run(["b", "a", "a", "a", "a"]), ensure_ascii=False, indent=2))