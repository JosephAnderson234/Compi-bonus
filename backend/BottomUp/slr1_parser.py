"""
slr1_parser.py
==============
Backend para el Parser SLR(1) — "The Ultimate Parser App"
Curso: Compiladores | Concurso universitario  (Bloque Bottom-Up)

Clase principal : SLR1Parser  (hereda de LR0Parser)
Función pública : run_analysis(input_data) -> dict

Herencia y reutilización
------------------------
LR0Parser  →  preprocesamiento, gramática aumentada, Closure, GOTO,
              colección canónica de ítems, simulación Shift-Reduce.
SLR1Parser →  agrega FIRST/FOLLOW, sobreescribe _build_table()
              con la restricción SLR(1): las reducciones se colocan
              ÚNICAMENTE en los terminales del conjunto FOLLOW(A),
              no en todos los terminales como en LR(0).

Por qué SLR(1) > LR(0)
------------------------
LR(0) coloca Reduce(A→α) en TODAS las columnas de terminales del estado
que contiene el ítem [A → α •].  Esto crea conflictos Shift/Reduce
innecesarios porque no distingue qué terminales pueden seguir a A.

SLR(1) usa FOLLOW(A) para filtrar: solo coloca Reduce(A→α) en la columna
del terminal `t` si  t ∈ FOLLOW(A).  De esta forma, si el terminal que
viene a continuación NUNCA puede seguir a A en la gramática, no se
coloca ninguna acción de reducción → se eliminan muchos falsos conflictos.

Símbolo épsilon
---------------
Se representa **exclusivamente** como la cadena "eps" tanto en el input
como en el output JSON.  Internamente, las producciones con eps se
almacenan como tupla vacía ().
"""

from __future__ import annotations

import sys
import os

# Añadir el directorio padre para importar lr0_parser sin instalar paquetes
sys.path.insert(0, os.path.dirname(__file__))

from lr0_parser import LR0Parser, EPS, END_MARKER
from collections import OrderedDict
from typing import Any


# ══════════════════════════════════════════════════════════════════════════════
# SLR(1) Parser — hereda de LR0Parser
# ══════════════════════════════════════════════════════════════════════════════

class SLR1Parser(LR0Parser):
    """
    Parser SLR(1).  Reutiliza el autómata de estados LR(0) completo y
    sobreescribe únicamente la construcción de la tabla de análisis para
    aplicar el filtro de FOLLOW.

    Atributos adicionales
    ---------------------
    first  : dict[str, set[str]]  — conjuntos FIRST de cada NT original
    follow : dict[str, set[str]]  — conjuntos FOLLOW de cada NT original
    """

    def __init__(self, grammar_text: str, start_symbol: str, input_string: str) -> None:
        # Inicializar toda la lógica LR(0) base
        super().__init__(grammar_text, start_symbol, input_string)

        # Conjuntos FIRST y FOLLOW (solo para NTs de la gramática original)
        self.first:  dict[str, set[str]] = {}
        self.follow: dict[str, set[str]] = {}

    # ──────────────────────────────────────────────────────────────────────────
    # A. CÁLCULO DE CONJUNTOS FIRST
    # ──────────────────────────────────────────────────────────────────────────

    def _first_of_sequence(self, symbols: tuple[str, ...]) -> set[str]:
        """
        Devuelve FIRST de una secuencia de símbolos.
        Reglas estándar (punto fijo integrado en compute_first):
          - Si seq = ε              → {ε}
          - Si seq = a X... (term.) → {a}
          - Si seq = A X... (NT)    → (FIRST(A) - {ε}) ∪ (ε ∈ FIRST(A) ? FIRST(X...) : ∅)
        """
        result: set[str] = set()
        if not symbols:           # producción vacía ()
            result.add(EPS)
            return result

        for sym in symbols:
            if sym in self.productions:           # No Terminal
                sym_first = self.first.get(sym, set())
                result |= (sym_first - {EPS})
                if EPS not in sym_first:
                    break                         # NT no puede derivar ε → parar
            else:                                 # Terminal (o eps literal)
                if sym == EPS:
                    result.add(EPS)
                else:
                    result.add(sym)
                break
        else:
            # Todos los símbolos pueden derivar ε → ε ∈ FIRST(secuencia)
            result.add(EPS)

        return result

    def compute_first(self) -> None:
        """
        Calcula FIRST(A) para cada No Terminal A de la gramática original.
        Itera hasta punto fijo (converge porque la gramática es finita).
        """
        for nt in self.non_terminals:
            self.first[nt] = set()

        changed = True
        while changed:
            changed = False
            for nt, alts in self.productions.items():
                for body in alts:
                    added = self._first_of_sequence(body)
                    before = len(self.first[nt])
                    self.first[nt] |= added
                    if len(self.first[nt]) > before:
                        changed = True

    # ──────────────────────────────────────────────────────────────────────────
    # B. CÁLCULO DE CONJUNTOS FOLLOW
    # ──────────────────────────────────────────────────────────────────────────

    def compute_follow(self) -> None:
        """
        Calcula FOLLOW(A) para cada No Terminal A de la gramática original.

        Reglas:
          1. $ ∈ FOLLOW(S)  (S = símbolo inicial)
          2. B → α A β  ⟹  FOLLOW(A) ⊇ FIRST(β) - {ε}
          3. B → α A β  con ε ∈ FIRST(β)  ⟹  FOLLOW(A) ⊇ FOLLOW(B)
             (también si β = ε, es decir A al final del cuerpo)
        """
        for nt in self.non_terminals:
            self.follow[nt] = set()
        self.follow[self.start_symbol].add(END_MARKER)  # Regla 1

        changed = True
        while changed:
            changed = False
            for head, alts in self.productions.items():
                for body in alts:
                    for i, sym in enumerate(body):
                        if sym not in self.productions:
                            continue              # sym es terminal → ignorar
                        # β = sufijo tras sym en esta producción
                        beta = body[i + 1:]
                        first_beta = self._first_of_sequence(beta)

                        before = len(self.follow[sym])

                        # Regla 2: FIRST(β) - {ε} ⊆ FOLLOW(sym)
                        self.follow[sym] |= (first_beta - {EPS})

                        # Regla 3: si ε ∈ FIRST(β), FOLLOW(head) ⊆ FOLLOW(sym)
                        if EPS in first_beta:
                            self.follow[sym] |= self.follow[head]

                        if len(self.follow[sym]) > before:
                            changed = True

    # ──────────────────────────────────────────────────────────────────────────
    # C. TABLA SLR(1) — sobreescribe la de LR(0)
    # ──────────────────────────────────────────────────────────────────────────

    def _build_table(self) -> None:  # type: ignore[override]
        """
        Construye la tabla SLR(1) unificada (ACTION + GOTO).

        Diferencia clave vs LR(0)
        --------------------------
        LR(0) coloca Reduce(A→α) en TODOS los terminales del estado.
        SLR(1) coloca Reduce(A→α) SOLO en el terminal `t` si t ∈ FOLLOW(A).

        Esto se implementa sustituyendo el bucle:
            for term in self.terminals + [END_MARKER]:   # LR(0)
        por:
            for term in (self.terminals + [END_MARKER]):
                if term in self.follow.get(head, set()):  # SLR(1) filter

        El resto de la lógica (Shift, GOTO, Accept) es idéntica a LR(0).
        """
        self.table = {i: {} for i in range(len(self.states))}
        aug_nt_set = set(self.aug_productions.keys())

        for state_idx, state in enumerate(self.states):

            # ── GOTO (No Terminales) ───────────────────────────────────────
            for nt in aug_nt_set:
                if nt in self.goto_map.get(state_idx, {}):
                    j = self.goto_map[state_idx][nt]
                    self._set_cell(state_idx, nt, str(j))

            # ── SHIFT (Terminales con transición definida) ─────────────────
            for term in self.terminals:
                if term in self.goto_map.get(state_idx, {}):
                    j = self.goto_map[state_idx][term]
                    self._set_cell(state_idx, term, f"S{j}")

            # ── REDUCE / ACCEPT (ítems con punto al final) ─────────────────
            for head, body, dot in state:
                if dot < len(body):
                    continue          # punto NO al final → no es ítem reduce

                if head == self.aug_start:
                    # [S' → S •] → ACCEPT (solo sobre $)
                    self._set_cell(state_idx, END_MARKER, "ACC")

                else:
                    # ┌─ DIFERENCIA SLR(1) ────────────────────────────────┐
                    # │ Solo colocar Reduce en t ∈ FOLLOW(head).            │
                    # │ En LR(0) sería: "for t in todos_los_terminales".    │
                    # │ Aquí filtramos con el conjunto FOLLOW calculado.     │
                    # └─────────────────────────────────────────────────────┘
                    prod_idx    = self.prod_list.index((head, body))
                    reduce_code = f"R{prod_idx}"

                    follow_a = self.follow.get(head, set())  # FOLLOW(A)

                    for term in self.terminals + [END_MARKER]:
                        if term in follow_a:                 # ← filtro SLR(1)
                            self._set_cell(state_idx, term, reduce_code)

    # ──────────────────────────────────────────────────────────────────────────
    # D. MENSAJE DE CONFLICTO ULTRA-DETALLADO
    # ──────────────────────────────────────────────────────────────────────────

    def _conflict_message(self) -> str:
        """
        Genera una explicación en lenguaje natural de cada conflicto SLR(1).
        Para cada conflicto registrado en self.conflicts construye un párrafo
        que explica: qué tipo es, en qué estado, con qué token, qué acciones
        colisionan y por qué (cruce con FOLLOW).
        """
        explanations: list[str] = []

        for raw in self.conflicts:
            # raw tiene el formato generado por LR0Parser._set_cell():
            # "Conflicto <Tipo> en Estado <n>, símbolo '<t>': <acciones>"
            parts = raw.split(":")
            header = parts[0]                                 # "Conflicto X en Estado n, símbolo 't'"
            actions_str = parts[1].strip() if len(parts) > 1 else "?"
            actions = [a.strip() for a in actions_str.split(" / ")]

            # Extraer estado y símbolo del header
            try:
                state_tok   = header.split("Estado")[1].strip().split(",")[0].strip()
                symbol_part = header.split("símbolo")[1].strip().strip("'\"")
                state_n     = int(state_tok)
                token       = symbol_part.strip("'")
            except (IndexError, ValueError):
                explanations.append(raw)
                continue

            # Clasificar acciones
            shifts  = [a for a in actions if a.startswith("S")]
            reduces = [a for a in actions if a.startswith("R")]

            if shifts and reduces:
                conflict_type = "Shift/Reduce"
            elif len(reduces) >= 2:
                conflict_type = "Reduce/Reduce"
            else:
                conflict_type = "Desconocido"

            lines: list[str] = [
                f"[{conflict_type}] Estado {state_n}, token '{token}':"
            ]

            for sh in shifts:
                dest = sh[1:]
                lines.append(
                    f"  • Shift → Estado {dest} "
                    f"(existe una transición GOTO[{state_n}, '{token}'] = {dest})."
                )

            for red in reduces:
                prod_idx = int(red[1:])
                p_head, p_body = self.prod_list[prod_idx]
                body_str = " ".join(p_body) if p_body else EPS
                follow_str = ", ".join(sorted(self.follow.get(p_head, set())))
                lines.append(
                    f"  • Reduce por '{p_head} → {body_str}' "
                    f"(el token '{token}' ∈ FOLLOW({p_head}) = {{{follow_str}}})."
                )

            # Explicación teórica del conflicto
            if conflict_type == "Shift/Reduce":
                lines.append(
                    f"  ↳ El parser no puede decidir si desplazar '{token}' "
                    f"(continuar acumulando en la pila) o reducir la producción "
                    f"(colapsar la cima de la pila). "
                    f"Esto indica que la gramática NO es SLR(1) y requiere "
                    f"lookahead adicional (use LR(1) o LALR(1))."
                )
            else:
                lines.append(
                    f"  ↳ El parser no puede decidir cuál de las {len(reduces)} "
                    f"producciones aplicar ante el token '{token}'. "
                    f"Sus FOLLOW se solapan, señal de ambigüedad estructural "
                    f"que SLR(1) no puede resolver."
                )

            explanations.append("\n".join(lines))

        return "\n\n".join(explanations)

    # ──────────────────────────────────────────────────────────────────────────
    # E. ORQUESTACIÓN (sobreescribe analyze())
    # ──────────────────────────────────────────────────────────────────────────

    def analyze(self) -> dict[str, Any]:  # type: ignore[override]
        """
        Pipeline SLR(1) completo.

        1. Preprocesar gramática  (heredado de LR0Parser)
        2. Gramática aumentada    (heredado)
        3. FIRST y FOLLOW         (nuevo en SLR1Parser)
        4. Colección canónica     (heredado)
        5. Tabla SLR(1)           (sobreescrita)
        6. Conflictos → abortar   (con mensaje ultra-detallado)
        7. Simulación Shift-Reduce (heredada de LR0Parser._simulate)
        """
        # ── Pasos 1-2: Gramática base ──────────────────────────────────────
        self._parse_grammar()
        self._build_augmented_grammar()

        # ── Paso 3: FIRST y FOLLOW ─────────────────────────────────────────
        self.compute_first()
        self.compute_follow()

        # ── Paso 4: Autómata LR(0) ────────────────────────────────────────
        self._build_canonical_collection()

        # ── Paso 5: Tabla SLR(1) ──────────────────────────────────────────
        self._build_table()   # versión SLR(1) sobrecargada

        # ══ Serializar conjuntos FIRST / FOLLOW ═══════════════════════════
        ff_section: dict[str, dict[str, list[str]]] = {}
        for nt in self.non_terminals:
            ff_section[nt] = {
                "FIRST":  sorted(self.first.get(nt, set())),
                "FOLLOW": sorted(self.follow.get(nt, set())),
            }

        # ══ Serializar tabla unificada ════════════════════════════════════
        aug_nt_list = list(self.aug_productions.keys())
        col_terms   = sorted(self.terminals)
        col_nt      = [nt for nt in aug_nt_list if nt != self.aug_start]
        columnas    = ["Estado"] + col_terms + [END_MARKER] + col_nt

        filas: list[dict[str, str]] = []
        for idx in range(len(self.states)):
            fila: dict[str, str] = {"Estado": str(idx)}
            for sym in col_terms + [END_MARKER] + col_nt:
                cell = self.table.get(idx, {}).get(sym)
                if cell is not None:
                    fila[sym] = cell
            filas.append(fila)

        table_section: dict[str, Any] = {
            "tipo":     "SLR1",
            "columnas": columnas,
            "filas":    filas,
        }

        # ══ Conflictos → abortar ══════════════════════════════════════════
        if self.conflicts:
            detail_msg = self._conflict_message()
            mensaje = (
                "La gramática NO es SLR(1): se detectaron conflictos.\n"
                "Simulación abortada.\n\n" + detail_msg
            )
            return {
                "cadena_valida":         False,
                "mensaje":               mensaje,
                "afn_clausura":          self.afn_closure_to_json(tipo="SLR1"),
                "conjuntos_first_follow": ff_section,
                "construccion_tablas":   table_section,
                "proceso_paso_a_paso":   [],
            }

        # ══ Sin conflictos → simular ══════════════════════════════════════
        accepted = self._simulate()
        mensaje  = (
            "Análisis sintáctico completado exitosamente sin conflictos SLR(1)."
            if accepted else
            "La cadena no es válida para el lenguaje definido por la gramática."
        )

        return {
            "cadena_valida":         accepted,
            "mensaje":               mensaje,
            "afn_clausura":          self.afn_closure_to_json(tipo="SLR1"),
            "conjuntos_first_follow": ff_section,
            "construccion_tablas":   table_section,
            "proceso_paso_a_paso":   self.sim_steps,
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
    cadena_entrada   : str  — Tokens separados por espacio.
    """
    parser = SLR1Parser(
        grammar_text = input_data["gramatica"],
        start_symbol = input_data["simbolo_inicial"],
        input_string = input_data["cadena_entrada"],
    )
    return parser.analyze()
