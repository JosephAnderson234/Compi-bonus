"""
lr0_parser.py
=============
Backend para el Parser LR(0) — "The Ultimate Parser App"
Curso: Compiladores | Concurso universitario  (Bloque Bottom-Up)

Clase principal : LR0Parser
Función pública : run_analysis(input_data) -> dict

Algoritmo
---------
1. Preprocesamiento + Gramática Aumentada  (S' -> S)
2. Colección Canónica de Ítems LR(0)       (Closure + GOTO)
3. Tabla Unificada LR(0)                   (ACTION + GOTO en una sola matriz)
4. Detección de Conflictos                 (Shift/Reduce, Reduce/Reduce)
5. Simulación Shift-Reduce                 (si no hay conflictos)

Símbolo especial
----------------
- Épsilon se representa **exclusivamente** como la cadena "eps".
- Una producción A -> eps se convierte en un ítem con el punto al final: A -> .
  (reducción inmediata sin consumir entrada).

Formato del ítem LR(0)
-----------------------
Tupla (head: str,  body: tuple[str, ...],  dot: int)
  head  → No Terminal de la cabeza de la producción
  body  → secuencia de símbolos (puede ser () si la producción es A -> eps)
  dot   → posición del punto (0..len(body))
"""

from __future__ import annotations

import json
from collections import OrderedDict
from typing import Any

# ── Constantes ────────────────────────────────────────────────────────────────
EPS          = "eps"           # épsilon en esta aplicación
END_MARKER   = "$"             # fin de entrada
AUG_SUFFIX   = "'"            # sufijo del símbolo aumentado  S -> S'

# Tipo del ítem LR(0)
Item = tuple[str, tuple[str, ...], int]   # (head, body, dot)


# ══════════════════════════════════════════════════════════════════════════════
# Parser principal
# ══════════════════════════════════════════════════════════════════════════════

class LR0Parser:
    """
    Encapsula toda la lógica del análisis LR(0).

    Uso
    ---
    parser = LR0Parser(grammar_text, start_symbol, input_string)
    result = parser.analyze()   # → dict con el contrato JSON del concurso
    """

    def __init__(self, grammar_text: str, start_symbol: str, input_string: str) -> None:
        self.grammar_text  = grammar_text
        self.start_symbol  = start_symbol.strip()
        self.input_tokens  = input_string.strip().split() + [END_MARKER]

        # ── Atributos que se rellenan durante el análisis ─────────────────
        # Gramática original (sin aumentar)
        self.non_terminals: list[str] = []
        self.terminals:     list[str] = []
        # productions[NT] = [ (sym1, sym2, ...), ... ]   (tuplas de strings)
        self.productions: dict[str, list[tuple[str, ...]]] = OrderedDict()

        # Gramática aumentada
        self.aug_start:    str = ""
        self.aug_productions: dict[str, list[tuple[str, ...]]] = OrderedDict()

        # Colección canónica: lista de frozensets de ítems
        self.states:       list[frozenset[Item]] = []
        # goto_table[state_idx][symbol] = state_idx
        self.goto_map:     dict[int, dict[str, int]] = {}

        # Tabla unificada: action[state_idx][symbol] = "S3" | "R2" | "ACC" | "2"
        self.table:        dict[int, dict[str, str]] = {}
        # Índice de producciones para el output (lista ordenada)
        self.prod_list:    list[tuple[str, tuple[str, ...]]] = []

        # Resultado de la simulación
        self.sim_steps:    list[dict[str, Any]] = []
        self.conflicts:    list[str] = []

    # ──────────────────────────────────────────────────────────────────────────
    # 1. PREPROCESAMIENTO
    # ──────────────────────────────────────────────────────────────────────────

    def _parse_grammar(self) -> None:
        """
        Parsea el texto de la gramática en self.productions.
        Eps → producción de cuerpo vacío representada como tuple vacía ().
        """
        seen_nt: set[str] = set()

        for raw in self.grammar_text.splitlines():
            line = raw.strip()
            if not line or "->" not in line:
                continue
            head, _, tail = line.partition("->")
            head = head.strip()
            if not head:
                continue
            if head not in seen_nt:
                self.non_terminals.append(head)
                self.productions[head] = []
                seen_nt.add(head)

            for alt_raw in tail.split("|"):
                symbols = alt_raw.strip().split()
                if not symbols:
                    symbols = [EPS]
                # eps → cuerpo vacío ()
                body: tuple[str, ...] = () if (len(symbols) == 1 and symbols[0] == EPS) \
                                        else tuple(symbols)
                self.productions[head].append(body)

        # Calcular terminales
        nt_set = set(self.non_terminals)
        term_set: set[str] = set()
        for alts in self.productions.values():
            for body in alts:
                for sym in body:
                    if sym not in nt_set:
                        term_set.add(sym)
        self.terminals = sorted(term_set)

    def _build_augmented_grammar(self) -> None:
        """
        Crea la gramática aumentada: S' -> S  (S' nuevo símbolo).
        Guarda todas las producciones en self.aug_productions y self.prod_list.
        """
        # Elegir el nombre del símbolo aumentado evitando colisiones
        aug = self.start_symbol + AUG_SUFFIX
        while aug in self.productions:
            aug += AUG_SUFFIX
        self.aug_start = aug

        # Gramática aumentada: primero la regla nueva, luego el resto
        self.aug_productions = OrderedDict()
        self.aug_productions[aug] = [(self.start_symbol,)]
        for nt, alts in self.productions.items():
            self.aug_productions[nt] = list(alts)

        # Lista plana de producciones (para indexar Reduce)
        for head, alts in self.aug_productions.items():
            for body in alts:
                self.prod_list.append((head, body))

    # ──────────────────────────────────────────────────────────────────────────
    # 2. CLOSURE y GOTO
    # ──────────────────────────────────────────────────────────────────────────

    def _closure(self, items: frozenset[Item]) -> frozenset[Item]:
        """
        Closure(I):
          Para cada ítem [A -> α . B β] en I y cada producción B -> γ,
          añadir [B -> . γ] si no estaba ya.
          Repetir hasta punto fijo.
        """
        closure: set[Item] = set(items)
        changed = True
        while changed:
            changed = False
            for head, body, dot in list(closure):
                if dot >= len(body):
                    continue                        # punto al final
                next_sym = body[dot]
                if next_sym in self.aug_productions:
                    for b in self.aug_productions[next_sym]:
                        new_item: Item = (next_sym, b, 0)
                        if new_item not in closure:
                            closure.add(new_item)
                            changed = True
        return frozenset(closure)

    def _goto(self, state: frozenset[Item], symbol: str) -> frozenset[Item]:
        """
        GOTO(I, X):
          Closure del conjunto de ítems obtenidos desplazando el punto
          sobre el símbolo X en los ítems de I.
        """
        moved: set[Item] = set()
        for head, body, dot in state:
            if dot < len(body) and body[dot] == symbol:
                moved.add((head, body, dot + 1))
        return self._closure(frozenset(moved)) if moved else frozenset()

    # ──────────────────────────────────────────────────────────────────────────
    # 3. COLECCIÓN CANÓNICA DE ÍTEMS LR(0)
    # ──────────────────────────────────────────────────────────────────────────

    def _build_canonical_collection(self) -> None:
        """
        Construye todos los estados (conjuntos de ítems LR(0)) y el mapa GOTO.
        """
        # Estado inicial: Closure([S' -> . S])
        initial_item: Item = (self.aug_start, (self.start_symbol,), 0)
        i0 = self._closure(frozenset({initial_item}))

        self.states = [i0]
        # Mapeo frozenset -> índice para no duplicar estados
        state_index: dict[frozenset[Item], int] = {i0: 0}
        self.goto_map = {}

        # Todos los símbolos de la gramática (terminales + no terminales aug.)
        all_nt  = list(self.aug_productions.keys())
        all_sym = self.terminals + all_nt

        worklist: list[int] = [0]
        while worklist:
            idx = worklist.pop(0)
            state = self.states[idx]
            self.goto_map.setdefault(idx, {})

            for sym in all_sym:
                next_state = self._goto(state, sym)
                if not next_state:
                    continue
                if next_state not in state_index:
                    new_idx = len(self.states)
                    self.states.append(next_state)
                    state_index[next_state] = new_idx
                    worklist.append(new_idx)
                self.goto_map[idx][sym] = state_index[next_state]

    # ──────────────────────────────────────────────────────────────────────────
    # 4. TABLA UNIFICADA LR(0) + DETECCIÓN DE CONFLICTOS
    # ──────────────────────────────────────────────────────────────────────────

    def _build_table(self) -> None:
        """
        Construye la tabla LR(0) unificada en self.table[estado][símbolo].

        Convenciones de celda
        ----------------------
        Shift  → "S<j>"        ej. "S5"
        Reduce → "R<i>"        ej. "R2"  (índice en self.prod_list)
        Accept → "ACC"
        GOTO   → "<j>"         ej. "3"   (solo para no terminales)

        Conflicto → se registra en self.conflicts y la celda queda con
                    el conjunto de acciones separadas por " / ".
        """
        self.table = {i: {} for i in range(len(self.states))}
        aug_nt_set = set(self.aug_productions.keys())

        for state_idx, state in enumerate(self.states):
            # ── GOTO entries (no terminales) ───────────────────────────────
            for nt in aug_nt_set:
                if nt in self.goto_map.get(state_idx, {}):
                    j = self.goto_map[state_idx][nt]
                    self._set_cell(state_idx, nt, str(j))

            # ── SHIFT entries (terminales con GOTO definido) ───────────────
            for term in self.terminals:
                if term in self.goto_map.get(state_idx, {}):
                    j = self.goto_map[state_idx][term]
                    self._set_cell(state_idx, term, f"S{j}")

            # ── REDUCE / ACCEPT (ítems con punto al final) ─────────────────
            for head, body, dot in state:
                if dot < len(body):
                    continue   # punto NO al final → ignorar para reduce/accept

                if head == self.aug_start:
                    # [S' -> S .] → ACCEPT  (solo sobre $)
                    self._set_cell(state_idx, END_MARKER, "ACC")
                else:
                    # [A -> α .] → REDUCE para TODOS los terminales + $
                    prod_idx = self.prod_list.index((head, body))
                    reduce_code = f"R{prod_idx}"
                    for term in self.terminals + [END_MARKER]:
                        self._set_cell(state_idx, term, reduce_code)

    def _set_cell(self, state: int, symbol: str, action: str) -> None:
        """
        Asigna una acción a self.table[state][symbol].
        Si ya existía una acción diferente → registra conflicto.
        """
        existing = self.table[state].get(symbol)
        if existing is None:
            self.table[state][symbol] = action
            return
        if existing == action:
            return   # duplicado idéntico → sin conflicto

        # ── CONFLICTO ─────────────────────────────────────────────────────
        # Unir las acciones (puede haber más de dos en teorías degeneradas)
        actions_set = set(existing.split(" / ")) | {action}
        merged = " / ".join(sorted(actions_set))
        self.table[state][symbol] = merged

        # Tipo de conflicto
        kinds = {a[0] for a in actions_set}
        if "S" in kinds and "R" in kinds:
            conflict_type = "Shift/Reduce"
        elif len(kinds) == 1 and "R" in kinds:
            conflict_type = "Reduce/Reduce"
        else:
            conflict_type = "Desconocido"

        detail = (
            f"Conflicto {conflict_type} en Estado {state}, símbolo '{symbol}': "
            f"{merged}"
        )
        if detail not in self.conflicts:
            self.conflicts.append(detail)

    # ──────────────────────────────────────────────────────────────────────────
    # 5. SIMULACIÓN SHIFT-REDUCE
    # ──────────────────────────────────────────────────────────────────────────

    def _simulate(self) -> bool:
        """
        Simula el parser LR(0) con pila de estados y pila de símbolos.

        Pila representada como dos listas paralelas:
          state_stack  → [s0, s1, ..., sn]
          symbol_stack → ["", sym1, ..., symn]  (el primer elemento es vacío)

        Retorna True si la cadena es aceptada, False en caso contrario.
        """
        state_stack:  list[int] = [0]
        symbol_stack: list[str] = [""]        # slot vacío para estado 0
        buffer = list(self.input_tokens)
        step_num = 0

        def pila_str() -> str:
            """Representación visual de la pila: 'estado símbolo estado ...'"""
            parts: list[str] = []
            for i in range(len(state_stack)):
                if i > 0:
                    parts.append(symbol_stack[i])
                parts.append(str(state_stack[i]))
            return " ".join(parts)

        while True:
            top_state = state_stack[-1]
            current   = buffer[0] if buffer else END_MARKER
            entrada   = " ".join(buffer)
            pila      = pila_str()
            step_num += 1

            action = self.table.get(top_state, {}).get(current)

            if action is None:
                # ── ERROR ─────────────────────────────────────────────────
                self.sim_steps.append({
                    "paso":    step_num,
                    "pila":    pila,
                    "entrada": entrada,
                    "accion":  (f"ERROR: no existe acción en "
                                f"tabla[{top_state}]['{current}']"),
                })
                return False

            if action == "ACC":
                # ── ACEPTAR ────────────────────────────────────────────────
                self.sim_steps.append({
                    "paso":    step_num,
                    "pila":    pila,
                    "entrada": entrada,
                    "accion":  "ACEPTAR",
                })
                return True

            if action.startswith("S"):
                # ── SHIFT ──────────────────────────────────────────────────
                next_state = int(action[1:])
                self.sim_steps.append({
                    "paso":    step_num,
                    "pila":    pila,
                    "entrada": entrada,
                    "accion":  f"Desplazar (Shift) al estado {next_state}",
                })
                symbol_stack.append(buffer.pop(0))
                state_stack.append(next_state)

            elif action.startswith("R"):
                # ── REDUCE ─────────────────────────────────────────────────
                prod_idx        = int(action[1:])
                red_head, red_body = self.prod_list[prod_idx]
                body_display    = (
                    EPS if not red_body
                    else " ".join(red_body)
                )
                rule_display    = f"{red_head} -> {body_display}"

                self.sim_steps.append({
                    "paso":    step_num,
                    "pila":    pila,
                    "entrada": entrada,
                    "accion":  f"Reducir (Reduce) por regla {rule_display}",
                })

                # Sacar |body| elementos de la pila
                pop_count = len(red_body)
                for _ in range(pop_count):
                    state_stack.pop()
                    symbol_stack.pop()

                # GOTO con el NT reducido desde el nuevo tope
                goto_state = self.table.get(state_stack[-1], {}).get(red_head)
                if goto_state is None:
                    step_num += 1
                    self.sim_steps.append({
                        "paso":    step_num,
                        "pila":    pila_str(),
                        "entrada": entrada,
                        "accion":  (f"ERROR: no existe GOTO en "
                                    f"tabla[{state_stack[-1]}]['{red_head}']"),
                    })
                    return False
                symbol_stack.append(red_head)
                state_stack.append(int(goto_state))

            else:
                # Acción desconocida (no debería ocurrir)
                self.sim_steps.append({
                    "paso":    step_num,
                    "pila":    pila,
                    "entrada": entrada,
                    "accion":  f"ERROR: acción desconocida '{action}'",
                })
                return False

    # ──────────────────────────────────────────────────────────────────────────
    # 6. SERIALIZACIÓN DEL AFN (colección canónica)
    # ──────────────────────────────────────────────────────────────────────────

    def _item_to_str(self, head: str, body: tuple[str, ...], dot: int) -> str:
        """Formato LR(0): 'A -> α . β' (cuerpo vacío: 'A -> .')."""
        if not body:
            return f"{head} -> ."
        left = list(body[:dot])
        right = list(body[dot:])
        core = " ".join(left + ["."] + right)
        return f"{head} -> {core}"

    def afn_closure_to_json(self, tipo: str = "LR0") -> dict[str, Any]:
        estados: list[dict[str, Any]] = []
        for state_idx, state in enumerate(self.states):
            trans = self.goto_map.get(state_idx, {})
            estados.append({
                "estado": f"I{state_idx}",
                "items": sorted(
                    self._item_to_str(h, b, d) for h, b, d in state
                ),
                "transiciones": {
                    sym: f"I{dst}"
                    for sym, dst in sorted(trans.items())
                },
            })
        return {"tipo": tipo, "estados": estados}

    # ──────────────────────────────────────────────────────────────────────────
    # 7. ORQUESTACIÓN + SERIALIZACIÓN JSON
    # ──────────────────────────────────────────────────────────────────────────

    def analyze(self) -> dict[str, Any]:
        """
        Ejecuta el pipeline completo y devuelve el JSON del contrato.
        """
        # ── Pasos 1-2: Gramática ───────────────────────────────────────────
        self._parse_grammar()
        self._build_augmented_grammar()

        # ── Paso 3: Colección canónica ─────────────────────────────────────
        self._build_canonical_collection()

        # ── Paso 4: Tabla + detección de conflictos ────────────────────────
        self._build_table()

        # ══ Serializar tabla ═════════════════════════════════════════════
        # Columnas: Estado | terminales (ordenados) | $ | no terminales
        aug_nt_list = list(self.aug_productions.keys())
        col_terms   = sorted(self.terminals)
        col_nt      = [nt for nt in aug_nt_list if nt != self.aug_start]
        # El símbolo aumentado no aparece como columna GOTO (nunca se hace
        # GOTO a S', solo se acepta)
        columnas: list[str] = ["Estado"] + col_terms + [END_MARKER] + col_nt

        filas: list[dict[str, str]] = []
        for idx in range(len(self.states)):
            fila: dict[str, str] = {"Estado": str(idx)}
            for sym in col_terms + [END_MARKER] + col_nt:
                cell = self.table.get(idx, {}).get(sym)
                if cell is not None:
                    fila[sym] = cell
            filas.append(fila)

        table_section: dict[str, Any] = {
            "tipo":     "LR0",
            "columnas": columnas,
            "filas":    filas,
        }

        # ══ Conflictos → abortar simulación ══════════════════════════════
        if self.conflicts:
            mensaje = (
                "La gramática NO es LR(0): se detectaron conflictos. "
                "Simulación abortada. Detalles: "
                + " | ".join(self.conflicts)
            )
            return {
                "cadena_valida":        False,
                "mensaje":              mensaje,
                "afn_clausura":         self.afn_closure_to_json(),
                "construccion_tablas":  table_section,
                "proceso_paso_a_paso":  [],
            }

        # ══ Sin conflictos → simular ══════════════════════════════════════
        accepted = self._simulate()

        if accepted:
            mensaje = "Análisis sintáctico completado exitosamente sin conflictos LR(0)."
        else:
            mensaje = "La cadena no es válida para el lenguaje definido por la gramática."

        return {
            "cadena_valida":       accepted,
            "mensaje":             mensaje,
            "afn_clausura":        self.afn_closure_to_json(),
            "construccion_tablas": table_section,
            "proceso_paso_a_paso": self.sim_steps,
        }


# ══════════════════════════════════════════════════════════════════════════════
# Función de conveniencia (interfaz API)
# ══════════════════════════════════════════════════════════════════════════════

def run_analysis(input_data: dict[str, str]) -> dict[str, Any]:
    """
    Punto de entrada principal.

    Claves requeridas en input_data
    --------------------------------
    gramatica        : str  — Texto de la gramática (una regla por línea).
    simbolo_inicial  : str  — No Terminal inicial.
    cadena_entrada   : str  — Tokens a analizar, separados por espacio.
    """
    parser = LR0Parser(
        grammar_text  = input_data["gramatica"],
        start_symbol  = input_data["simbolo_inicial"],
        input_string  = input_data["cadena_entrada"],
    )
    return parser.analyze()
