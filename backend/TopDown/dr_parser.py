"""
recursive_descent_parser.py
===========================
Backend para el Parser de Descenso Recursivo con Backtracking — "The Ultimate Parser App"
Curso: Compiladores | Concurso universitario

Clase principal : RecursiveDescentParser
Función pública : run_analysis(input_data) → dict  (mismo contrato que ll1_parser)

Algoritmo
---------
Para cada No Terminal, se prueban sus alternativas en orden de aparición.
Antes de intentar cada alternativa, se guarda el puntero de entrada actual.
Si la alternativa falla en cualquier punto, el puntero se restaura (Backtracking)
y se prueba la siguiente alternativa.
Si todas las alternativas de un NT fallan, el NT reporta fallo al llamador.

El árbol de derivación resultante sólo contiene los nodos de la derivación
exitosa final (las ramas muertas de los backtracks se descartan).
"""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from typing import Any

# ── Constantes ────────────────────────────────────────────────────────────────
EPSILON = ""
END_OF_INPUT = "$"


def _format_symbols(symbols: list[str]) -> str:
    return " ".join("" if s == EPSILON else s for s in symbols)


# ══════════════════════════════════════════════════════════════════════════════
# Nodo del árbol de derivación
# ══════════════════════════════════════════════════════════════════════════════

class TreeNode:
    """
    Nodo del árbol de derivación.
    'name'     → etiqueta del símbolo (NT o terminal).
    'children' → lista de TreeNode hijos (vacía para hojas terminales).
    """

    def __init__(self, name: str) -> None:
        self.name: str = name
        self.children: list[TreeNode] = []

    def to_dict(self) -> dict[str, Any]:
        """Serializa recursivamente al formato JSON del contrato."""
        return {
            "name":     self.name,
            "children": [c.to_dict() for c in self.children],
        }


# ══════════════════════════════════════════════════════════════════════════════
# Parser principal
# ══════════════════════════════════════════════════════════════════════════════

class RecursiveDescentParser:
    """
    Parser de Descenso Recursivo con Backtracking.

    Métodos públicos
    ----------------
    analyze() → dict   Ejecuta el pipeline completo y retorna el JSON de salida.
    """

    def __init__(self, grammar_text: str, start_symbol: str, input_string: str) -> None:
        self.grammar_text  = grammar_text
        self.start_symbol  = start_symbol.strip()

        # Tokens de entrada (sin '$': lo manejamos internamente)
        self.tokens: list[str] = input_string.strip().split()

        # Estructuras de gramática
        self.non_terminals: list[str] = []
        self.productions:   dict[str, list[list[str]]] = OrderedDict()

        # Estado de la simulación
        self._pointer: int = 0          # índice actual en self.tokens
        self._steps:   list[dict[str, Any]] = []
        self._step_num: int = 0

    # ──────────────────────────────────────────────────────────────────────────
    # 1. PREPROCESAMIENTO  (idéntico al de ll1_parser para consistencia)
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _has_direct_left_recursion(
        prods: dict[str, list[list[str]]],
        nt_order: list[str],
    ) -> bool:
        """True si existe A -> A alpha (descenso recursivo puede no terminar)."""
        for nt in nt_order:
            for alt in prods.get(nt, []):
                if alt and alt[0] == nt:
                    return True
        return False

    def _is_grammar_compatible(self) -> bool:
        """La gramatica admite descenso recursivo con backtracking."""
        if self.start_symbol not in self.productions:
            return False
        return not self._has_direct_left_recursion(
            self.productions, self.non_terminals
        )

    def _parse_grammar(self) -> None:
        """Parsea el texto de la gramática y rellena self.productions."""
        seen: set[str] = set()
        for raw in self.grammar_text.splitlines():
            line = raw.strip()
            if not line or "->" not in line:
                continue
            head, _, tail = line.partition("->")
            head = head.strip()
            if not head:
                continue
            if head not in seen:
                self.non_terminals.append(head)
                self.productions[head] = []
                seen.add(head)
            for alt_raw in tail.split("|"):
                symbols = alt_raw.strip().split()
                normalized = list(symbols)
                self.productions[head].append(normalized if normalized else [EPSILON])

    # ──────────────────────────────────────────────────────────────────────────
    # 2. REGISTRO DE PASOS
    # ──────────────────────────────────────────────────────────────────────────

    def _log(self, action: str) -> None:
        """Añade un paso al log cronológico."""
        self._step_num += 1
        self._steps.append({"paso": self._step_num, "accion": action})

    def _peek(self) -> str:
        """Token actual bajo el puntero (o '$' si se llegó al final)."""
        if self._pointer < len(self.tokens):
            return self.tokens[self._pointer]
        return END_OF_INPUT

    def _peek_display(self) -> str:
        """Representación legible del token actual para los logs."""
        tok = self._peek()
        return f"'{tok}'"

    # ──────────────────────────────────────────────────────────────────────────
    # 3. MOTOR RECURSIVO
    # ──────────────────────────────────────────────────────────────────────────

    def _parse_nt(self, symbol: str) -> TreeNode | None:
        """
        Intenta derivar el No Terminal `symbol` desde la posición actual.

        Prueba cada alternativa en orden.  Si una alternativa falla, restaura
        el puntero (backtracking) y prueba la siguiente.

        Retorna un TreeNode completo si tiene éxito, o None si todas fallan.
        """
        self._log(f"Llamando a NoTerminal '{symbol}'. Puntero en: {self._peek_display()}")

        alts = self.productions.get(symbol, [])

        for alt in alts:
            saved_ptr = self._pointer          # guardar posición antes de intentar
            alt_display = str(alt)
            self._log(f"{symbol} -> Intentando regla {alt_display}")

            node = TreeNode(symbol)
            success = self._parse_sequence(alt, node)

            if success:
                self._log(
                    f"NoTerminal '{symbol}' resuelto exitosamente con regla {alt_display}."
                )
                return node

            # Falló: backtrack
            self._pointer = saved_ptr
            self._log(
                f"¡BACKTRACKING! Regla {symbol} -> {alt_display} falló. "
                f"Restaurando puntero a: {self._peek_display()}"
            )

        # Todas las alternativas agotadas
        self._log(f"NoTerminal '{symbol}' falló: ninguna alternativa funcionó.")
        return None

    def _parse_sequence(self, symbols: list[str], parent: TreeNode) -> bool:
        """
        Intenta hacer match de la secuencia de símbolos `symbols`.
        Va añadiendo hijos a `parent` a medida que avanza.
        Si retorna False, `parent.children` puede estar parcialmente poblado
        (el llamador desechará este nodo al hacer backtrack).

        Retorna True si la secuencia completa se consumió con éxito.
        """
        for sym in symbols:
            if sym == EPSILON:
                # Producción vacía: nodo hoja ε sin consumir entrada
                child = TreeNode(EPSILON)
                parent.children.append(child)
                self._log(f"Derivacion epsilon (vacio) en '{parent.name}'.")
                continue

            if sym in self.productions:
                # Es un No Terminal → llamada recursiva
                child_node = self._parse_nt(sym)
                if child_node is None:
                    return False          # propagamos el fallo
                parent.children.append(child_node)

            else:
                # Es un Terminal → match directo
                current = self._peek()
                if current == sym:
                    child = TreeNode(sym)
                    parent.children.append(child)
                    self._pointer += 1
                    self._log(
                        f"Match exitoso con terminal '{sym}'. "
                        f"Avanza puntero a: {self._peek_display()}"
                    )
                else:
                    self._log(
                        f"Fallo de match: se esperaba '{sym}' "
                        f"pero se encontró {self._peek_display()}."
                    )
                    return False

        return True

    # ──────────────────────────────────────────────────────────────────────────
    # 4. ORQUESTACIÓN
    # ──────────────────────────────────────────────────────────────────────────

    def analyze(self) -> dict[str, Any]:
        """
        Ejecuta el pipeline completo y retorna el JSON del contrato.
        """
        self._parse_grammar()
        gramatica_parseable = self._is_grammar_compatible()

        if not gramatica_parseable:
            if self.start_symbol not in self.productions:
                motivo = (
                    f"El simbolo inicial '{self.start_symbol}' no esta definido "
                    "en la gramatica."
                )
            else:
                motivo = (
                    "La gramatica tiene recursividad izquierda directa; "
                    "no es compatible con descenso recursivo."
                )
            return {
                "gramatica_parseable": False,
                "cadena_valida":      False,
                "mensaje":            motivo,
                "proceso_paso_a_paso": [],
                "arbol_derivacion":   None,
            }

        # Reiniciar estado
        self._pointer  = 0
        self._steps    = []
        self._step_num = 0

        # Iniciar el descenso desde el símbolo inicial
        root = self._parse_nt(self.start_symbol)

        # ¿La cadena fue consumida completamente?
        fully_consumed = self._pointer == len(self.tokens)
        accepted       = root is not None and fully_consumed

        if accepted:
            self._log("ACEPTAR: Cadena válida.")
            mensaje        = "Cadena analizada correctamente por Descenso Recursivo."
            tree_dict: Any = root.to_dict()
        else:
            if root is None:
                self._log("RECHAZAR: El símbolo inicial no pudo derivar la cadena.")
                mensaje = "La cadena no es válida: ninguna derivación la reconoce."
            else:
                self._log(
                    f"RECHAZAR: Se consumieron {self._pointer} de {len(self.tokens)} "
                    f"tokens. Entrada no consumida: {self.tokens[self._pointer:]}."
                )
                mensaje = (
                    "La cadena no es válida: la gramática no consume toda la entrada."
                )
            tree_dict = root.to_dict() if root is not None else None

        return {
            "gramatica_parseable": True,
            "cadena_valida":      accepted,
            "mensaje":            mensaje,
            "proceso_paso_a_paso": self._steps,
            "arbol_derivacion":   tree_dict,
        }


# ══════════════════════════════════════════════════════════════════════════════
# Función de conveniencia (interfaz estilo API)
# ══════════════════════════════════════════════════════════════════════════════

def run_analysis(input_data: dict[str, str]) -> dict[str, Any]:
    """
    Punto de entrada principal.  Acepta el JSON de entrada y retorna el JSON
    de salida según el contrato del concurso.

    Claves requeridas en input_data
    --------------------------------
    gramatica        : str  — Texto de la gramática (una regla por línea).
    simbolo_inicial  : str  — No Terminal inicial.
    cadena_entrada   : str  — Cadena a analizar (tokens separados por espacio).
    """
    parser = RecursiveDescentParser(
        grammar_text  = input_data["gramatica"],
        start_symbol  = input_data["simbolo_inicial"],
        input_string  = input_data["cadena_entrada"],
    )
    return parser.analyze()
