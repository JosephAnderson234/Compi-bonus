"""
ll1_parser.py
=============
Backend para el Parser Predictivo LL(1) — "The Ultimate Parser App"
Curso: Compiladores | Concurso universitario

Autor  : (tu nombre)
Versión: 1.0.0

Este módulo implementa la clase LL1Parser que encapsula:
  1. Preprocesamiento de gramática (texto plano → estructuras internas)
  2. Cálculo de conjuntos FIRST y FOLLOW
  3. Construcción de la tabla LL(1) con detección de conflictos
  4. Módulo de transformación automática (recursividad izq. + factorización)
  5. Simulación del parser paso a paso (pila + buffer)
  6. Serialización del resultado al contrato JSON estricto del concurso
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict, OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from grammar_symbols import fresh_prime_name, symbols_in_grammar

# ── Constantes globales ────────────────────────────────────────────────────────
EPSILON = "eps"
END_OF_INPUT = "$"

# Entrada de gramatica: token eps, simbolo ε, o alternativa vacia
EPSILON_INPUT = {"eps", "ε", "epsilon", "EPSILON", "EPS"}


def _normalize_symbol(sym: str) -> str:
    return EPSILON if sym in EPSILON_INPUT else sym


def _format_symbols(symbols: list[str]) -> str:
    return " ".join(symbols)


# ══════════════════════════════════════════════════════════════════════════════
# Clase principal
# ══════════════════════════════════════════════════════════════════════════════

class LL1Parser:
    """
    Encapsula toda la lógica del análisis LL(1):
      - parse_grammar()          → rellena self.productions, terminals, non_terminals
      - compute_first()          → rellena self.first
      - compute_follow()         → rellena self.follow
      - build_table()            → rellena self.table; detecta conflictos
      - transform_grammar()      → elimina recursividad izq. y factoriza
      - simulate()               → simula la pila paso a paso
      - analyze()                → orquesta todo y devuelve el JSON de salida
    """

    def __init__(self, grammar_text: str, start_symbol: str, input_string: str) -> None:
        """
        Parámetros
        ----------
        grammar_text  : str  — Gramática en texto plano, una producción por línea.
                               Formato: "NT -> alt1 | alt2 | ..."
        start_symbol  : str  — Símbolo inicial de la gramática.
        input_string  : str  — Cadena a analizar (tokens separados por espacios).
        """
        self.grammar_text:  str = grammar_text
        self.start_symbol:  str = start_symbol.strip()
        # Tokeniza la cadena de entrada y añade '$'
        raw_tokens = input_string.strip().split()
        self.input_tokens: list[str] = raw_tokens + [END_OF_INPUT]

        # Estructuras internas principales
        self.non_terminals: list[str]              = []   # orden de aparición
        self.terminals:     list[str]              = []
        # productions: { NT -> [ [sym, sym, ...], ... ] }
        self.productions:   dict[str, list[list[str]]] = OrderedDict()

        # Conjuntos FIRST y FOLLOW
        self.first:  dict[str, set[str]] = {}
        self.follow: dict[str, set[str]] = {}

        # Tabla LL(1): table[NT][terminal] = lista de producciones que aplican
        self.table:  dict[str, dict[str, list[list[str]]]] = {}

        # Bandera: ¿la gramática tiene conflictos en la tabla?
        self.has_conflicts: bool = False
        self.conflict_details: list[str] = []

        # Resultado de la simulación
        self.simulation_steps: list[dict[str, Any]] = []

        # Gramática transformada sugerida (si procede)
        self.suggested_grammar: str | None = None
        self.transformation_reason: str = ""

    # ──────────────────────────────────────────────────────────────────────────
    # 1. PREPROCESAMIENTO
    # ──────────────────────────────────────────────────────────────────────────

    def parse_grammar(self) -> None:
        """
        Convierte el texto plano de la gramática en la estructura interna
        self.productions: { NT -> [ alternativa1, alternativa2, ... ] }
        donde cada alternativa es una lista de símbolos (strings).

        Reglas del parser de texto:
          - Una línea = una regla de producción: "NT -> alt1 | alt2"
          - Los símbolos se separan por espacios dentro de cada alternativa.
          - Alternativa vacia, token eps o simbolo ε → epsilon interno 'eps'.
          - Las líneas vacías se ignoran.
        """
        seen_nt: set[str] = set()

        for raw_line in self.grammar_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue  # ignorar líneas vacías

            # Separar cabeza y cuerpo: "NT -> ..."
            if "->" not in line:
                continue  # línea malformada → ignorar
            head, _, tail = line.partition("->")
            head = head.strip()

            if not head:
                continue

            # Registrar no terminal conservando el orden de primera aparición
            if head not in seen_nt:
                self.non_terminals.append(head)
                self.productions[head] = []
                seen_nt.add(head)

            # Dividir en alternativas por '|'
            for alt_raw in tail.split("|"):
                symbols = alt_raw.strip().split()
                normalized = [_normalize_symbol(s) for s in symbols]
                if not normalized:
                    normalized = [EPSILON]
                self.productions[head].append(normalized)

        # Calcular terminales: todos los símbolos que NO son no-terminales ni ε
        nt_set = set(self.non_terminals)
        terminal_set: set[str] = set()
        for alts in self.productions.values():
            for alt in alts:
                for sym in alt:
                    if sym != EPSILON and sym not in nt_set:
                        terminal_set.add(sym)
        # Ordenar para reproducibilidad (mantenemos el orden de aparición)
        self.terminals = sorted(terminal_set)

    # ──────────────────────────────────────────────────────────────────────────
    # 2. CÁLCULO DE CONJUNTOS FIRST
    # ──────────────────────────────────────────────────────────────────────────

    def compute_first(self) -> None:
        """
        Calcula FIRST(X) para cada No Terminal X.

        Reglas:
          - Si X es terminal → FIRST(X) = {X}
          - Si X → ε         → ε ∈ FIRST(X)
          - Si X → Y1 Y2 ... Yk:
              añadir FIRST(Y1) - {ε} a FIRST(X)
              si ε ∈ FIRST(Y1), añadir FIRST(Y2) - {ε}, etc.
              si ε ∈ FIRST(Yi) para todo i, añadir ε a FIRST(X)
        Itera hasta punto fijo.
        """
        # Inicializar
        for nt in self.non_terminals:
            self.first[nt] = set()

        changed = True
        while changed:
            changed = False
            for nt, alts in self.productions.items():
                for alt in alts:
                    added = self._first_of_sequence(alt)
                    before = len(self.first[nt])
                    self.first[nt] |= added
                    if len(self.first[nt]) > before:
                        changed = True

    def _first_of_sequence(self, symbols: list[str]) -> set[str]:
        """
        Devuelve FIRST de una secuencia de símbolos (puede incluir ε).
        Se usa también durante la construcción de la tabla.
        """
        result: set[str] = set()
        for sym in symbols:
            if sym == EPSILON:
                result.add(EPSILON)
                break  # ε ya añadido; no hay más símbolos que procesar
            elif sym not in self.productions:
                # Es terminal
                result.add(sym)
                break  # los terminales no derivan ε
            else:
                # Es no terminal
                sym_first = self.first.get(sym, set())
                result |= (sym_first - {EPSILON})
                if EPSILON not in sym_first:
                    break  # este NT no puede derivar ε, paramos
        else:
            # El bucle terminó sin break → todos los símbolos derivan ε
            result.add(EPSILON)
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # 3. CÁLCULO DE CONJUNTOS FOLLOW
    # ──────────────────────────────────────────────────────────────────────────

    def compute_follow(self) -> None:
        """
        Calcula FOLLOW(A) para cada No Terminal A.

        Reglas:
          1. $ ∈ FOLLOW(S)  donde S es el símbolo inicial
          2. Para cada producción B → α A β:
               FOLLOW(A) ⊇ FIRST(β) - {ε}
          3. Para cada producción B → α A β donde ε ∈ FIRST(β)
             (o β = ε):
               FOLLOW(A) ⊇ FOLLOW(B)
        Itera hasta punto fijo.
        """
        for nt in self.non_terminals:
            self.follow[nt] = set()

        # Regla 1
        self.follow[self.start_symbol].add(END_OF_INPUT)

        changed = True
        while changed:
            changed = False
            for head, alts in self.productions.items():
                for alt in alts:
                    for i, sym in enumerate(alt):
                        if sym not in self.productions:
                            continue  # es terminal o ε
                        # β = resto de la secuencia tras sym
                        beta = alt[i + 1:]
                        first_beta = self._first_of_sequence(beta) if beta else {EPSILON}

                        # Regla 2
                        before = len(self.follow[sym])
                        self.follow[sym] |= (first_beta - {EPSILON})
                        # Regla 3
                        if EPSILON in first_beta:
                            self.follow[sym] |= self.follow[head]
                        if len(self.follow[sym]) > before:
                            changed = True

    # ──────────────────────────────────────────────────────────────────────────
    # 4. CONSTRUCCIÓN DE LA TABLA LL(1)
    # ──────────────────────────────────────────────────────────────────────────

    def build_table(self) -> None:
        """
        Construye la tabla de análisis M[A, a] según el algoritmo estándar:

        Para cada producción A → α:
          - Para cada terminal a ∈ FIRST(α) - {ε}:
              añadir A → α a M[A, a]
          - Si ε ∈ FIRST(α):
              Para cada b ∈ FOLLOW(A):
                  añadir A → α a M[A, b]

        Si una celda acumula más de una producción → CONFLICTO (no LL(1)).
        """
        # Inicializar tabla
        for nt in self.non_terminals:
            self.table[nt] = {}

        for nt, alts in self.productions.items():
            for alt in alts:
                first_alpha = self._first_of_sequence(alt)

                for terminal in first_alpha - {EPSILON}:
                    self._add_to_table(nt, terminal, alt)

                if EPSILON in first_alpha:
                    for terminal in self.follow[nt]:
                        self._add_to_table(nt, terminal, alt)

    def _add_to_table(self, nt: str, terminal: str, production: list[str]) -> None:
        """Añade una producción a la tabla; registra conflicto si la celda ya tiene entrada."""
        cell = self.table[nt].setdefault(terminal, [])
        # Evitar duplicados exactos
        if production not in cell:
            cell.append(production)
        if len(self.table[nt][terminal]) > 1:
            self.has_conflicts = True
            detail = (
                f"Conflicto en M[{nt}, {terminal}]: "
                + " | ".join(
                    _format_symbols(p) for p in self.table[nt][terminal]
                )
            )
            if detail not in self.conflict_details:
                self.conflict_details.append(detail)

    # ──────────────────────────────────────────────────────────────────────────
    # 5. MÓDULO DE TRANSFORMACIÓN AUTOMÁTICA
    # ──────────────────────────────────────────────────────────────────────────

    def _used_symbol_names(
        self, *prod_dicts: dict[str, list[list[str]]]
    ) -> set[str]:
        """NTs, terminales y símbolos en cuerpos ya presentes (gramática + borrador)."""
        used = set(self.non_terminals) | set(self.terminals)
        used |= symbols_in_grammar(self.productions)
        for d in prod_dicts:
            used |= symbols_in_grammar(d)
        return used

    def transform_grammar(self) -> tuple[dict[str, list[list[str]]], list[str]]:
        """
        Aplica, en orden:
          1. Eliminación de recursividad por la izquierda directa.
          2. Factorización por la izquierda.

        Devuelve (new_productions, new_non_terminals).
        Las producciones transformadas se almacenan en self.suggested_grammar.
        """
        # Trabajar sobre una copia profunda para no mutar el estado original
        prods: dict[str, list[list[str]]] = deepcopy(self.productions)
        nt_order: list[str] = list(self.non_terminals)

        # ── Paso 1: Eliminar recursividad por la izquierda directa ────────────
        prods, nt_order = self._eliminate_left_recursion(prods, nt_order)

        # ── Paso 2: Factorización por la izquierda ────────────────────────────
        prods, nt_order = self._left_factor(prods, nt_order)

        # Serializar la gramática sugerida
        lines: list[str] = []
        for nt in nt_order:
            alts = prods[nt]
            rhs = " | ".join(_format_symbols(alt) for alt in alts)
            lines.append(f"{nt} -> {rhs}")
        self.suggested_grammar = "\n".join(lines)

        return prods, nt_order

    # ── Recursividad por la izquierda directa ─────────────────────────────────

    def _eliminate_left_recursion(
        self,
        prods: dict[str, list[list[str]]],
        nt_order: list[str],
    ) -> tuple[dict[str, list[list[str]]], list[str]]:
        """
        Para cada NT A con producciones del tipo A → Aα | β:
          Se generan:
            A  → β A'
            A' → α A' | ε
        donde A' es un nuevo no terminal.
        Solo trata recursividad DIRECTA por la izquierda.
        """
        new_order: list[str] = []
        new_prods: dict[str, list[list[str]]] = OrderedDict()

        for nt in nt_order:
            alts = prods[nt]
            recursive_alts: list[list[str]] = []   # α para A → Aα
            non_recursive_alts: list[list[str]] = []  # β para A → β

            for alt in alts:
                if alt and alt[0] == nt:
                    # Recursividad directa por izquierda encontrada
                    recursive_alts.append(alt[1:] if len(alt) > 1 else [EPSILON])
                else:
                    non_recursive_alts.append(alt)

            if not recursive_alts:
                # Sin recursividad → copiar tal cual
                new_order.append(nt)
                new_prods[nt] = alts
                continue

            used = self._used_symbol_names(prods, new_prods)
            prime = fresh_prime_name(nt, used)

            # A  → β A'   para cada β no recursivo
            new_alts_A: list[list[str]] = []
            for beta in non_recursive_alts:
                if beta == [EPSILON]:
                    new_alts_A.append([prime])
                else:
                    new_alts_A.append(beta + [prime])

            # A' → α A' | ε
            new_alts_prime: list[list[str]] = []
            for alpha in recursive_alts:
                if alpha == [EPSILON]:
                    new_alts_prime.append([prime])
                else:
                    new_alts_prime.append(alpha + [prime])
            new_alts_prime.append([EPSILON])

            new_order.append(nt)
            new_order.append(prime)
            new_prods[nt] = new_alts_A
            new_prods[prime] = new_alts_prime

        return new_prods, new_order

    # ── Factorización por la izquierda ────────────────────────────────────────

    def _left_factor(
        self,
        prods: dict[str, list[list[str]]],
        nt_order: list[str],
    ) -> tuple[dict[str, list[list[str]]], list[str]]:
        """
        Para cada NT A:
          Agrupa las alternativas que compartan prefijo común.
          A → α β1 | α β2 | γ  se convierte en:
            A  → α A'' | γ
            A'' → β1 | β2
        Repite hasta que no queden prefijos comunes.
        """
        new_prods: dict[str, list[list[str]]] = OrderedDict()
        new_order: list[str] = list(nt_order)
        # Copiar estado inicial
        for nt in nt_order:
            new_prods[nt] = list(prods[nt])

        changed = True
        while changed:
            changed = False
            extra_order: list[str] = []
            extra_prods: dict[str, list[list[str]]] = {}

            for nt in list(new_order):
                alts = new_prods[nt]
                factored, extras, did_change = self._factor_one(nt, alts, new_prods, new_order)
                if did_change:
                    changed = True
                    new_prods[nt] = factored
                    extra_order.extend(extras.keys())
                    extra_prods.update(extras)

            # Insertar los nuevos NTs después del NT que los generó (preservar orden)
            for nt, alts in extra_prods.items():
                if nt not in new_prods:
                    new_prods[nt] = alts
                    new_order.append(nt)

        return new_prods, new_order

    def _factor_one(
        self,
        nt: str,
        alts: list[list[str]],
        existing_prods: dict[str, list[list[str]]],
        existing_order: list[str],
    ) -> tuple[list[list[str]], dict[str, list[list[str]]], bool]:
        """
        Factoriza un único NT si tiene prefijos comunes.
        Devuelve (nuevas alternativas para NT, NTs extra creados, hubo cambio).
        """
        if len(alts) <= 1:
            return alts, {}, False

        # Agrupar por primer símbolo
        groups: dict[str, list[list[str]]] = defaultdict(list)
        for alt in alts:
            key = alt[0] if alt else EPSILON
            groups[key].append(alt)

        # ¿Hay algún grupo con más de una alternativa?
        needs_factoring = any(len(g) > 1 for g in groups.values())
        if not needs_factoring:
            return alts, {}, False

        new_alts: list[list[str]] = []
        extra_prods: dict[str, list[list[str]]] = {}

        for first_sym, group in groups.items():
            if len(group) == 1:
                new_alts.append(group[0])
                continue

            # Calcular prefijo común más largo
            prefix = self._longest_common_prefix(group)
            suffix_alts: list[list[str]] = []
            for alt in group:
                suffix = alt[len(prefix):]
                suffix_alts.append(suffix if suffix else [EPSILON])

            used = self._used_symbol_names(existing_prods, extra_prods)
            prime = fresh_prime_name(nt, used)

            new_alts.append(prefix + [prime])
            extra_prods[prime] = suffix_alts

        return new_alts, extra_prods, True

    @staticmethod
    def _longest_common_prefix(alts: list[list[str]]) -> list[str]:
        """
        Calcula el prefijo común más largo entre una lista de alternativas.
        """
        if not alts:
            return []
        prefix: list[str] = []
        for symbols in zip(*alts):
            if len(set(symbols)) == 1:
                prefix.append(symbols[0])
            else:
                break
        return prefix

    # ──────────────────────────────────────────────────────────────────────────
    # 6. SIMULACIÓN DEL PARSER
    # ──────────────────────────────────────────────────────────────────────────

    def simulate(self) -> bool:
        """
        Simula el parser LL(1) usando pila y buffer de entrada.

        Estado inicial:
          pila   = [END_OF_INPUT, start_symbol]   (top = start_symbol)
          buffer = [t1, t2, ..., tn, END_OF_INPUT]

        Acciones:
          - Si top == END_OF_INPUT == buffer[0] → ACEPTAR
          - Si top == buffer[0] (terminal) → MATCH (pop pila, avanzar buffer)
          - Si top es NT → buscar M[top][buffer[0]]:
              si existe → REEMPLAZAR TOP por la producción (en orden inverso)
              si no     → ERROR
        Registra cada paso en self.simulation_steps.

        Retorna True si la cadena es aceptada, False en caso contrario.
        """
        stack: list[str] = [END_OF_INPUT, self.start_symbol]
        buffer: list[str] = list(self.input_tokens)   # ya incluye '$'
        step_num = 0
        accepted = False

        while True:
            top = stack[-1]
            current_input = buffer[0] if buffer else END_OF_INPUT
            stack_str  = " ".join(reversed(stack))   # top a la derecha (visual)
            buffer_str = " ".join(buffer)

            step_num += 1

            # ── Aceptar ────────────────────────────────────────────────────
            if top == END_OF_INPUT and current_input == END_OF_INPUT:
                self.simulation_steps.append({
                    "paso":    step_num,
                    "pila":    stack_str,
                    "entrada": buffer_str,
                    "accion": "ACEPTAR",
                })
                accepted = True
                break

            # ── Match de terminal ──────────────────────────────────────────
            if top == current_input and top != END_OF_INPUT:
                action = f"Coincidencia: '{top}'"
                self.simulation_steps.append({
                    "paso":    step_num,
                    "pila":    stack_str,
                    "entrada": buffer_str,
                    "accion": action,
                })
                stack.pop()
                buffer.pop(0)
                continue

            # ── Error: terminal en tope que no coincide con entrada ────────
            if top in self.terminals or top == END_OF_INPUT:
                self.simulation_steps.append({
                    "paso":    step_num,
                    "pila":    stack_str,
                    "entrada": buffer_str,
                    "accion": f"ERROR: se esperaba '{top}' pero se encontró '{current_input}'",
                })
                accepted = False
                break

            # ── NT: consultar tabla ────────────────────────────────────────
            if top not in self.table or current_input not in self.table[top]:
                self.simulation_steps.append({
                    "paso":    step_num,
                    "pila":    stack_str,
                    "entrada": buffer_str,
                    "accion": f"ERROR: no existe entrada en M[{top}, {current_input}]",
                })
                accepted = False
                break

            production = self.table[top][current_input][0]  # primera (y única) entrada
            prod_str = f"{top} -> {_format_symbols(production)}"

            self.simulation_steps.append({
                "paso":    step_num,
                "pila":    stack_str,
                "entrada": buffer_str,
                "accion": prod_str,
            })

            # Reemplazar el tope de la pila
            stack.pop()
            if production != [EPSILON]:           # ε no se apila
                for sym in reversed(production):
                    stack.append(sym)

        return accepted

    # ──────────────────────────────────────────────────────────────────────────
    # 7. ORQUESTACIÓN Y SERIALIZACIÓN JSON
    # ──────────────────────────────────────────────────────────────────────────

    def analyze(self) -> dict[str, Any]:
        """
        Método principal que ejecuta todo el pipeline y devuelve el resultado
        en el formato JSON estricto exigido por el concurso.
        """
        # ── Paso 1: Preprocesar ────────────────────────────────────────────
        self.parse_grammar()

        # ── Paso 2: FIRST y FOLLOW ─────────────────────────────────────────
        self.compute_first()
        self.compute_follow()

        # ── Paso 3: Tabla LL(1) ───────────────────────────────────────────
        self.build_table()

        # ══ Construir sección conjuntos_first_follow ══════════════════════
        first_follow_section: dict[str, dict[str, list[str]]] = {}
        for nt in self.non_terminals:
            first_follow_section[nt] = {
                "FIRST":  sorted(self.first[nt]),
                "FOLLOW": sorted(self.follow[nt]),
            }

        # ══ Construir sección construccion_tablas ════════════════════════
        all_terminals_in_table: list[str] = sorted(
            {t for row in self.table.values() for t in row}
        )
        # Asegurar que $ esté al final
        if END_OF_INPUT in all_terminals_in_table:
            all_terminals_in_table.remove(END_OF_INPUT)
            all_terminals_in_table.append(END_OF_INPUT)

        columnas: list[str] = ["NoTerminal"] + all_terminals_in_table
        filas: list[dict[str, str]] = []
        for nt in self.non_terminals:
            row: dict[str, str] = {"NoTerminal": nt}
            for terminal in all_terminals_in_table:
                entries = self.table[nt].get(terminal, [])
                if entries:
                    # Si hay conflicto: mostrar todas separadas por ' o '
                    row[terminal] = " o ".join(
                        f"{nt} -> {_format_symbols(p)}" for p in entries
                    )
                # else: celda vacía → no añadir la clave
            filas.append(row)

        tabla_section: dict[str, Any] = {
            "tipo":     "LL1",
            "columnas": columnas,
            "filas":    filas,
        }

        # ══ Rama: No LL(1) ═══════════════════════════════════════════════
        if self.has_conflicts:
            # Detectar tipo de problema para el mensaje
            has_lr = self._check_left_recursion(self.productions, self.non_terminals)
            motivo_parts: list[str] = []
            if has_lr:
                motivo_parts.append("recursividad por la izquierda")
            if self.conflict_details:
                motivo_parts.append(
                    "colisiones en la tabla: " + "; ".join(self.conflict_details[:3])
                )
            motivo = "La gramática NO es LL(1) debido a: " + " y ".join(motivo_parts)

            self.transformation_reason = motivo
            self.transform_grammar()

            return {
                "gramatica_parseable": False,
                "cadena_valida": False,
                "mensaje": (
                    "La gramática no es LL(1). Se aplican transformaciones automáticas. "
                    "La simulación de la cadena fue abortada."
                ),
                "conjuntos_first_follow": first_follow_section,
                "construccion_tablas":    tabla_section,
                "proceso_paso_a_paso":    [],
                "sugerencias_transformacion": {
                    "requiere_transformacion": True,
                    "motivo":             self.transformation_reason,
                    "gramatica_sugerida": self.suggested_grammar,
                },
            }

        # ══ Rama: LL(1) válida — simular ════════════════════════════════
        accepted = self.simulate()

        if accepted:
            mensaje   = "Análisis completado exitosamente. La cadena es válida."
        else:
            # La cadena no pertenece al lenguaje, pero la gramática sí es LL(1)
            mensaje = "La cadena no es válida para el lenguaje definido por la gramática."

        return {
            "gramatica_parseable": True,
            "cadena_valida": accepted,
            "mensaje":       mensaje,
            "conjuntos_first_follow": first_follow_section,
            "construccion_tablas":    tabla_section,
            "proceso_paso_a_paso":    self.simulation_steps,
            "sugerencias_transformacion": {
                "requiere_transformacion": False,
                "motivo": "La gramática ya es LL(1) válida.",
                "gramatica_sugerida": None,
            },
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Utilidad: detección de recursividad por la izquierda
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _check_left_recursion(
        prods: dict[str, list[list[str]]],
        nt_order: list[str],
    ) -> bool:
        """
        Devuelve True si existe al menos una producción con recursividad
        directa por la izquierda (A → A α).
        """
        for nt in nt_order:
            for alt in prods.get(nt, []):
                if alt and alt[0] == nt:
                    return True
        return False


# ══════════════════════════════════════════════════════════════════════════════
# Función de conveniencia (interfaz estilo API)
# ══════════════════════════════════════════════════════════════════════════════

def run_analysis(input_data: dict[str, str]) -> dict[str, Any]:
    """
    Punto de entrada principal. Acepta el JSON de entrada y retorna el JSON
    de salida completo según el contrato del concurso.

    Parámetros
    ----------
    input_data : dict — Debe contener las claves:
                   "gramatica"        : str
                   "simbolo_inicial"  : str
                   "cadena_entrada"   : str

    Retorna
    -------
    dict  — Resultado completo del análisis LL(1).
    """
    parser = LL1Parser(
        grammar_text   = input_data["gramatica"],
        start_symbol   = input_data["simbolo_inicial"],
        input_string   = input_data["cadena_entrada"],
    )
    return parser.analyze()


