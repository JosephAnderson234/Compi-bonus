"""
lalr1_parser.py
===============
Backend para el Parser LALR(1) — "The Ultimate Parser App"
Curso: Compiladores | Concurso universitario  (Bloque Bottom-Up)

Clase principal : LALR1Parser
Función pública : run_analysis(input_data) -> dict

Herencia y reutilización
------------------------
lr_base.py   →  Grammar, Production, LR1Item, LR1State,
                 compute_first, closure, goto_state, LRTable, run_parser
LALR1Parser  →  hereda/utiliza la infraestructura LR(1) para generar la
                 colección canónica completa y luego fusiona los estados
                 con el mismo "core" (núcleo de ítems) combinando sus
                 lookaheads.

Algoritmo LALR(1)  (paso a paso)
----------------------------------
1. Construir la colección canónica LR(1) completa   (idéntico a LR(1))
2. Agrupar los estados por su "core_key":
   core_key(I) = frozenset{(producción, dot_pos)}  para cada ítem de I
   Dos estados con el mismo core_key son **fusionables**.
3. Fusionar cada grupo: crear un nuevo estado LALR(1) cuyo conjunto de
   ítems tiene los mismos cores que el grupo pero con la **unión** de los
   lookaheads de todos los estados del grupo.
4. Re-mapear todas las transiciones: si una transición apuntaba a un estado
   LR(1) antiguo, ahora apunta al estado LALR(1) que lo absorbió.
5. Construir la tabla ACTION+GOTO usando los estados LALR(1) fusionados,
   con la misma lógica restringida que SLR(1)/LR(1):
   Reduce(A→α) solo en los lookaheads del ítem (no en todos los terminales).
6. Detectar conflictos: un conflicto generado **durante la fusión** indica
   que la gramática no es LALR(1).  Se aborta la simulación con un mensaje
   detallado que identifica los estados LR(1) originales involucrados.

Diferencia LALR(1) vs LR(1)
------------------------------
LR(1)   : cada estado tiene su propio conjunto de lookaheads → más estados,
           menos conflictos (nunca falso-positivos).
LALR(1) : estados de igual núcleo se fusionan → menos estados (igual que
           LR(0)/SLR(1) en cantidad), lookaheads de LR(1) (más precisos que
           SLR(1)), pero la fusión puede introducir conflictos Reduce/Reduce
           que LR(1) no tenía.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Optional

from lr_base import (
    EPS,
    Grammar,
    Production,
    compute_first,
    LR1Item,
    LR1State,
    closure,
    goto_state,
    ActionType,
    Action,
    LRTable,
    run_parser,
    format_body,
)


# ══════════════════════════════════════════════════════════════════════════════
# Parser LALR(1)
# ══════════════════════════════════════════════════════════════════════════════

class LALR1Parser:
    """
    Parser LALR(1).

    Genera primero la colección LR(1) completa (usando la infraestructura de
    lr_base.py) y luego fusiona los estados con el mismo núcleo para obtener
    la tabla LALR(1) con lookaheads refinados.

    Atributos públicos (útiles para depuración/frontend)
    -----------------------------------------------------
    lr1_states       : lista de estados LR(1) antes de la fusión
    lalr_states      : lista de estados LALR(1) después de la fusión
    merge_map        : dict[lr1_state_id -> lalr_state_id]
    table            : LRTable de la tabla LALR(1)
    grammar          : Grammar aumentada usada
    conflicts_detail : lista de strings; descripción detallada de conflictos
                       originados en la fusión.
    """

    def __init__(self) -> None:
        self.grammar:     Optional[Grammar]       = None
        self.first_sets:  dict[str, set[str]]     = {}

        # ── LR(1) original ────────────────────────────────────────────────
        self.lr1_states:      list[LR1State]           = []
        self.lr1_transitions: dict[int, dict[str, int]] = defaultdict(dict)

        # ── LALR(1) después de la fusión ──────────────────────────────────
        self.lalr_states:      list[LR1State]           = []
        self.lalr_transitions: dict[int, dict[str, int]] = defaultdict(dict)
        # lr1_id → lalr_id
        self.merge_map:        dict[int, int]            = {}
        # lalr_id → lista de lr1_ids que lo forman
        self.merge_groups:     dict[int, list[int]]      = {}

        self.table:            LRTable = LRTable()
        self.conflicts_detail: list[str] = []

    # ──────────────────────────────────────────────────────────────────────────
    # A. CONSTRUCCIÓN DE LA COLECCIÓN LR(1) CANÓNICA
    # ──────────────────────────────────────────────────────────────────────────

    def _build_lr1_collection(self) -> None:
        """
        Genera todos los estados LR(1) y sus transiciones.
        Algoritmo estándar: igual al de ParserLR1 en lr1_parser.py.
        """
        assert self.grammar is not None

        start_prod  = self.grammar.productions[0]
        start_item  = LR1Item(start_prod, 0, frozenset({"$"}))
        s0 = LR1State(0)
        s0.add_item(start_item)
        s0 = closure(s0, self.grammar, self.first_sets)
        self.lr1_states.append(s0)

        # Todos los símbolos de la gramática
        all_symbols: set[str] = set()
        for p in self.grammar.productions:
            all_symbols.add(p.non_terminal)
            for sym in p.transaction:
                all_symbols.add(sym)

        pending = [0]
        while pending:
            cur_id = pending.pop(0)
            cur    = self.lr1_states[cur_id]

            for sym in sorted(all_symbols):
                next_id = len(self.lr1_states)
                nxt = goto_state(cur, sym, next_id, self.grammar, self.first_sets)
                if not nxt.items():
                    continue

                # ¿El estado ya existe (mismo ítem LR(1) completo)?
                found_id = -1
                for st in self.lr1_states:
                    if st.same_items(nxt):
                        found_id = st.id
                        break

                if found_id == -1:
                    self.lr1_states.append(nxt)
                    self.lr1_transitions[cur_id][sym] = next_id
                    pending.append(next_id)
                else:
                    self.lr1_transitions[cur_id][sym] = found_id

    # ──────────────────────────────────────────────────────────────────────────
    # B. FUSIÓN DE ESTADOS (LR(1) → LALR(1))
    # ──────────────────────────────────────────────────────────────────────────

    def _merge_states(self) -> None:
        """
        Agrupa los estados LR(1) por core_key y los fusiona en estados LALR(1).

        La fusión combina los lookaheads de todos los ítems con el mismo
        (producción, dot_pos):

        LALR merge rule:
            state_LALR[A → α • β, LA] donde LA = ⋃ { la_i | (A → α • β, la_i) ∈ I_k }
            para todos los estados LR(1) I_k que comparten el mismo core.

        Después de la fusión, re-mapeamos las transiciones para que los
        destinos LR(1) originales sean reemplazados por los IDs LALR(1).
        """
        assert self.grammar is not None

        # ── Agrupar por core_key ──────────────────────────────────────────
        # core_key → [lr1_state_id, ...]
        groups: dict[frozenset, list[int]] = defaultdict(list)
        for st in self.lr1_states:
            groups[st.core_key()].append(st.id)

        # Asignar IDs LALR(1) nuevos (0, 1, 2, ...) siguiendo el orden del
        # primer estado de cada grupo (preserva I0 como Estado 0)
        sorted_groups = sorted(groups.values(), key=lambda g: min(g))

        for lalr_id, group in enumerate(sorted_groups):
            self.merge_groups[lalr_id] = group
            for lr1_id in group:
                self.merge_map[lr1_id] = lalr_id

        # ── Crear estado LALR(1) por cada grupo ───────────────────────────
        # Tomamos los ítems del primer estado y les unimos los lookaheads del resto.
        lalr_state_map: dict[int, LR1State] = {}  # lalr_id → LR1State

        for lalr_id, group in sorted(self.merge_groups.items()):
            merged = LR1State(lalr_id)

            # Recolectar todos los lookaheads por core_key de producción del grupo
            # core_dict: (Production, dot_pos) → set[str] lookaheads
            core_dict: dict[tuple, set[str]] = defaultdict(set)

            for lr1_id in group:
                for item in self.lr1_states[lr1_id].items():
                    core_dict[(item.production, item.dot_pos)] |= set(item.lookaheads)

            for (prod, dot), las in core_dict.items():
                merged.add_item(LR1Item(prod, dot, frozenset(las)))

            lalr_state_map[lalr_id] = merged
            self.lalr_states.append(merged)

        # ── Re-mapear transiciones ─────────────────────────────────────────
        for lr1_id, trans in self.lr1_transitions.items():
            lalr_src = self.merge_map[lr1_id]
            for sym, lr1_dst in trans.items():
                lalr_dst = self.merge_map[lr1_dst]
                # Si ya hay una transición inconsistente (no debería ocurrir
                # en gramáticas correctas), ignorar duplicados idénticos.
                existing = self.lalr_transitions[lalr_src].get(sym)
                if existing is not None and existing != lalr_dst:
                    # Esto nunca debería ocurrir si la fusión es correcta,
                    # pero lo registramos como salvaguarda.
                    self.conflicts_detail.append(
                        f"Inconsistencia de transición en Estado LALR {lalr_src} "
                        f"con símbolo '{sym}': destino {existing} vs {lalr_dst}."
                    )
                self.lalr_transitions[lalr_src][sym] = lalr_dst

    # ──────────────────────────────────────────────────────────────────────────
    # C. CONSTRUCCIÓN DE LA TABLA LALR(1)
    # ──────────────────────────────────────────────────────────────────────────

    def _build_table(self) -> None:
        """
        Construye la tabla ACTION + GOTO para los estados LALR(1).

        Reglas (idénticas a LR(1) pero sobre estados fusionados):
        ─────────────────────────────────────────────────────────
        Para cada estado LALR  I  y sus ítems:
          • [A → α • a β, la]  y  GOTO(I, a) = J  → ACTION[I, a] = Shift J
          • [S'→ S •, $]                           → ACTION[I, $] = Accept
          • [A → α •, la]      (A ≠ S')            → ACTION[I, la] = Reduce(A→α)
          • GOTO[I, A] = J  para transición sobre No Terminal A

        Un conflicto durante el llenado de la tabla significa que la gramática
        NO es LALR(1).  En tal caso abortamos la simulación y generamos un
        mensaje ultra-detallado que indica qué estados LR(1) originales se
        fusionaron para crear el conflicto.
        """
        assert self.grammar is not None

        terms = self.grammar.terminals()
        nts   = self.grammar.non_terminals()
        aug_prod = self.grammar.productions[0]   # S' → S

        for state in self.lalr_states:
            trans = self.lalr_transitions.get(state.id, {})

            # ── SHIFT y GOTO ──────────────────────────────────────────────
            for sym, dst in trans.items():
                if sym in terms:
                    self.table.set_action(state.id, sym, Action(ActionType.SHIFT, dst))
                elif sym in nts:
                    self.table.goto_table[state.id][sym] = dst

            # ── REDUCE y ACCEPT ───────────────────────────────────────────
            for item in state.items():
                if not item.is_reduce():
                    continue

                prod = item.production

                # ¿Es la producción aumentada S' → S •  con lookahead $?
                if prod == aug_prod and "$" in item.lookaheads:
                    self.table.set_action(state.id, "$", Action(ActionType.ACCEPT))
                    continue

                # Reduce: colocar solo en los lookaheads del ítem LALR(1)
                for la in item.lookaheads:
                    act = Action(ActionType.REDUCE, -1, prod)
                    # Verificar conflicto antes de escribir
                    existing = self.table.action[state.id].get(la)
                    if existing and existing != act:
                        self._record_merge_conflict(state.id, la, existing, act)
                    self.table.set_action(state.id, la, act)

    def _record_merge_conflict(
        self,
        lalr_state_id: int,
        token: str,
        existing: Action,
        incoming: Action,
    ) -> None:
        """
        Genera un mensaje de conflicto ultra-detallado que expone qué estados
        LR(1) originales generaron el problema al fusionarse.
        """
        lr1_ids = self.merge_groups.get(lalr_state_id, [lalr_state_id])
        lr1_str = ", ".join(f"I{i}" for i in lr1_ids)

        def desc(act: Action) -> str:
            if act.type == ActionType.SHIFT:
                return f"Shift al estado {act.value}"
            if act.type == ActionType.REDUCE:
                p = act.reduce_prod
                return f"Reduce por '{p.non_terminal} → {format_body(p.transaction)}'"
            return act.to_str()

        if existing.type == ActionType.REDUCE and incoming.type == ActionType.REDUCE:
            kind = "Reduce/Reduce"
        else:
            kind = "Shift/Reduce"

        msg = (
            f"[{kind}] Estado LALR(1) {lalr_state_id} "
            f"(fusión de estados LR(1): {lr1_str}), token '{token}':\n"
            f"  • {desc(existing)}\n"
            f"  • {desc(incoming)}\n"
            f"  ↳ Este conflicto surgió al fusionar los estados LR(1) "
            f"({lr1_str}) porque sus lookaheads se solapan con '{token}'. "
            f"La gramática NO es LALR(1); usa LR(1) completo para analizarla."
        )

        if msg not in self.conflicts_detail:
            self.conflicts_detail.append(msg)

    # ──────────────────────────────────────────────────────────────────────────
    # D. API pública
    # ──────────────────────────────────────────────────────────────────────────

    def build(self, grammar: Grammar) -> None:
        """Ejecuta el pipeline completo de construcción LALR(1)."""
        self.grammar    = grammar
        self.first_sets = compute_first(grammar)

        self._build_lr1_collection()
        self._merge_states()
        self._build_table()

    def afn_lr1_to_json(self) -> dict:
        """Serializa la colección LR(1) completa (antes de fusionar)."""
        estados = []
        for state in self.lr1_states:
            trans = self.lr1_transitions.get(state.id, {})
            estados.append({
                "estado": f"I{state.id}",
                "items": [it.to_str() for it in sorted(state.items())],
                "transiciones": {
                    sym: f"I{dst}"
                    for sym, dst in sorted(trans.items())
                },
            })
        return {"tipo": "LR1", "estados": estados}

    def afn_closure_to_json(self) -> dict:
        """Serializa el AFN LALR(1) (estados fusionados con ítems y transiciones)."""
        estados = []
        for st in self.lalr_states:
            lr1_origins = self.merge_groups.get(st.id, [st.id])
            trans = self.lalr_transitions.get(st.id, {})
            estados.append({
                "estado": f"I{st.id}",
                "lr1_fusionados": [f"I{x}" for x in lr1_origins],
                "items": [it.to_str() for it in sorted(st.items())],
                "transiciones": {
                    sym: f"I{dst}" for sym, dst in sorted(trans.items())
                },
            })
        return {"tipo": "LALR1", "estados": estados}

    def lalr_states_to_json(self) -> dict:
        """Alias retrocompatible de afn_closure_to_json()."""
        return self.afn_closure_to_json()

    def run(self, tokens: list[str]) -> dict:
        """
        Ejecuta análisis completo y devuelve el JSON del contrato.
        Si hay conflictos de fusión, aborta la simulación.
        """
        assert self.grammar is not None

        # ── Conflictos de mesa → abortar ──────────────────────────────────
        all_conflicts = (
            self.conflicts_detail
            + [
                (f"[LRTable] Estado {c['estado']}, símbolo '{c['simbolo']}': "
                 f"{c['conflicto']}")
                for c in self.table.conflicts
                if not any(f"Estado LALR(1) {c['estado']}" in d
                            for d in self.conflicts_detail)
            ]
        )

        terms = self.grammar.terminals()
        nts   = self.grammar.non_terminals()
        table_json = self.table.to_json(terms, nts, tipo="LALR1")
        afn_lr1    = self.afn_lr1_to_json()
        afn_lalr   = self.afn_closure_to_json()

        if all_conflicts:
            detail = "\n\n".join(all_conflicts)
            return {
                "cadena_valida":       False,
                "mensaje":             (
                    "La gramática NO es LALR(1): conflictos detectados "
                    "durante la fusión de estados.\n\n" + detail
                ),
                "afn_lr1":             afn_lr1,
                "afn_clausura":        afn_lalr,
                "lalr_estados":        afn_lalr,
                "construccion_tablas": table_json,
                "proceso_paso_a_paso": [],
            }

        # ── Sin conflictos → simular ──────────────────────────────────────
        parse_result = run_parser(tokens, self.table)
        aceptado     = parse_result["cadena_valida"]

        return {
            "cadena_valida":       aceptado,
            "mensaje":             (
                "Análisis completado. Estados LR(1) fusionados correctamente "
                "sin conflictos."
                if aceptado else
                parse_result["mensaje"]
            ),
            "afn_lr1":             afn_lr1,
            "afn_clausura":        afn_lalr,
            "lalr_estados":        afn_lalr,
            "construccion_tablas": table_json,
            "proceso_paso_a_paso": parse_result["proceso_paso_a_paso"],
        }


# ══════════════════════════════════════════════════════════════════════════════
# Función de conveniencia (interfaz API unificada)
# ══════════════════════════════════════════════════════════════════════════════

def run_analysis(input_data: dict) -> dict:
    """
    Punto de entrada principal.  Misma interfaz que lr0_parser / slr1_parser.

    Claves requeridas
    -----------------
    gramatica        : str  — Texto de la gramática (una regla por línea).
    simbolo_inicial  : str  — No Terminal inicial.
    cadena_entrada   : str  — Tokens separados por espacio.
    """
    grammar = Grammar.from_text(
        input_data["gramatica"],
        simbolo_inicial=input_data.get("simbolo_inicial"),
    )
    tokens = input_data["cadena_entrada"].strip().split()

    parser = LALR1Parser()
    parser.build(grammar)
    return parser.run(tokens)


# ══════════════════════════════════════════════════════════════════════════════
# Demo rápida
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    req = {
        "gramatica":       "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id",
        "simbolo_inicial": "E",
        "cadena_entrada":  "id + id * id",
    }
    print(json.dumps(run_analysis(req), ensure_ascii=False, indent=2))
