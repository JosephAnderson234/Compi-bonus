"""
test_ll1.py
===========
Suite de pruebas para LL1Parser.
Ejecuta los 4 casos de prueba y muestra los resultados en tablas legibles.

Uso:
    python test_ll1.py
"""

from __future__ import annotations

import re
import textwrap
from typing import Any

from ll1_parser import run_analysis

# Paleta ANSI (solo colores; sin iconos Unicode)
RESET   = "\033[0m"
BOLD    = "\033[1m"
GREEN   = "\033[92m"
RED     = "\033[91m"
YELLOW  = "\033[93m"
CYAN    = "\033[96m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
DIM     = "\033[2m"

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", str(text))


def _visible_len(text: str) -> int:
    return len(_strip_ansi(text))


def _disp_sym(sym: str) -> str:
    """Epsilon interno ('') se muestra como ε solo en consola."""
    return "ε" if sym == "" else sym


def _disp(text: str) -> str:
    s = str(text).replace("∅", "{}").replace("→", "->").replace("…", "...")
    if " -> " in s:
        head, _, rhs = s.partition(" -> ")
        if not rhs.strip():
            return f"{head} -> ε"
    if "|" in s:
        left, _, alt = s.partition("|")
        if not alt.strip():
            s = left.rstrip() + " | ε"
    if ", " in s:
        return ", ".join(_disp_sym(part) for part in s.split(", "))
    return s


def _col(text: str, width: int, align: str = "<") -> str:
    """Celda con ancho fijo segun caracteres visibles (sin ANSI)."""
    plain = _strip_ansi(str(text))
    if _visible_len(plain) > width:
        plain = plain[: max(0, width - 3)] + "..."
    return f"{plain:{align}{width}}"


def _hline(widths: list[int], left: str = "+", mid: str = "+", right: str = "+") -> str:
    parts = ["-" * (w + 2) for w in widths]
    return left + mid.join(parts) + right


def _row(cells: list[str], widths: list[int], colors: list[str] | None = None) -> str:
    colors = colors or [""] * len(cells)
    parts = []
    for cell, w, color in zip(cells, widths, colors):
        padded = _col(cell, w)
        parts.append(f" {color}{padded}{RESET} ")
    return "|" + "|".join(parts) + "|"


def print_table(
    title: str,
    headers: list[str],
    rows: list[list[str]],
    header_color: str = BOLD + CYAN,
) -> None:
    """Tabla ASCII; colores se aplican despues de calcular anchos."""
    plain_headers = [_disp(h) for h in headers]
    plain_rows = [[_disp(c) for c in row] for row in rows]

    widths = [_visible_len(h) for h in plain_headers]
    for row in plain_rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], min(_visible_len(cell), 48))

    print()
    print(BOLD + BLUE + f"  >> {title}" + RESET)
    print(_hline(widths))
    print(_row(plain_headers, widths, [header_color] * len(plain_headers)))
    print(_hline(widths, mid="+"))
    for i, row in enumerate(plain_rows):
        row_color = DIM if i % 2 == 1 else ""
        print(_row(row, widths, [row_color] * len(row)))
    print(_hline(widths))


# ══════════════════════════════════════════════════════════════════════════════
# Secciones de visualización
# ══════════════════════════════════════════════════════════════════════════════

def show_input(inp: dict[str, Any]) -> None:
    """Gramatica, simbolo inicial y cadena del caso."""
    print(f"\n  {BOLD}Entrada del caso:{RESET}")
    print(f"  {DIM}Simbolo inicial:{RESET} {inp['simbolo_inicial']}")
    cadena = repr(inp["cadena_entrada"])
    print(f"  {DIM}Cadena entrada:{RESET}  {_disp(cadena)}")
    print(f"\n  {BOLD}Gramatica:{RESET}")
    for line in inp["gramatica"].strip().splitlines():
        print(f"    {CYAN}{_disp(line.strip())}{RESET}")


def show_summary(case_label: str, result: dict[str, Any], expected_parseable: bool | None) -> None:
    """Muestra el banner de resultado (valida/invalida + mensaje)."""
    valid     = result["cadena_valida"]
    parseable = result["gramatica_parseable"]
    mensaje   = result["mensaje"]
    color     = GREEN if valid else RED
    icon      = "[OK]" if valid else "[X]"
    p_color   = GREEN if parseable else YELLOW
    needs     = result["sugerencias_transformacion"]["requiere_transformacion"]

    print()
    print("=" * 72)
    print(f"  {BOLD}{case_label}{RESET}")
    print("=" * 72)
    print(f"  {p_color}{BOLD}gramatica_parseable (LL(1)) = {parseable}{RESET}")
    if expected_parseable is not None:
        ok = parseable == expected_parseable
        mark = f"{GREEN}[OK]" if ok else f"{RED}[X]"
        print(f"  {mark}  esperado gramatica_parseable = {expected_parseable}{RESET}")
    print(f"  {color}{BOLD}{icon}  cadena_valida = {valid}{RESET}")
    print(f"  {DIM}Mensaje: {mensaje}{RESET}")
    if needs:
        print(f"  {YELLOW}!  La gramatica NO es LL(1) — se activan transformaciones.{RESET}")


def show_first_follow(ff: dict[str, dict[str, list[str]]]) -> None:
    """Tabla de conjuntos FIRST y FOLLOW."""
    rows = [
        [
            nt,
            ", ".join(_disp_sym(s) for s in data["FIRST"]) or "{}",
            ", ".join(_disp_sym(s) for s in data["FOLLOW"]) or "{}",
        ]
        for nt, data in ff.items()
    ]
    print_table(
        "Conjuntos FIRST / FOLLOW",
        ["No Terminal", "FIRST", "FOLLOW"],
        rows,
        header_color=BOLD + MAGENTA,
    )


def show_ll1_table(tabla: dict[str, Any]) -> None:
    """Tabla de análisis LL(1) M[NT, terminal]."""
    columnas: list[str] = tabla["columnas"]   # ["NoTerminal", "id", "+", ...]
    filas: list[dict]   = tabla["filas"]

    headers = columnas
    rows: list[list[str]] = []
    for fila in filas:
        row = [fila.get(col, "") for col in columnas]
        rows.append(row)

    print_table(
        "Tabla de Analisis LL(1)  M[NT, terminal]",
        headers,
        rows,
        header_color=BOLD + CYAN,
    )


def show_simulation(steps: list[dict[str, Any]]) -> None:
    """Tabla de la simulación paso a paso."""
    if not steps:
        print(f"\n  {DIM}(sin simulación — gramática no es LL(1)){RESET}")
        return

    rows: list[list[str]] = []
    for step in steps:
        accion = step["accion"]
        if accion == "ACEPTAR":
            accion = f"{GREEN}{BOLD}[OK] ACEPTAR{RESET}"
        elif accion.startswith("ERROR"):
            accion = f"{RED}{BOLD}[X] {accion}{RESET}"
        elif accion.startswith("Coincidencia"):
            accion = f"{CYAN}{accion}{RESET}"
        rows.append([
            str(step["paso"]),
            step["pila"],
            step["entrada"],
            accion,
        ])

    print_table(
        "Simulación paso a paso",
        ["Paso", "Pila (top->)", "Entrada", "Accion"],
        rows,
        header_color=BOLD + GREEN,
    )


def show_transformation(sug: dict[str, Any]) -> None:
    """Muestra la sugerencia de transformación si aplica."""
    if not sug["requiere_transformacion"]:
        print(f"\n  {GREEN}[OK] No se requiere transformacion.{RESET}")
        return

    print(f"\n  {YELLOW}{BOLD}* Modulo de Transformacion Automatica{RESET}")
    motivo = textwrap.fill(sug["motivo"], width=68, initial_indent="  ", subsequent_indent="    ")
    print(f"{DIM}{motivo}{RESET}")

    print(f"\n  {BOLD}Gramática sugerida:{RESET}")
    for line in (sug["gramatica_sugerida"] or "").splitlines():
        print(f"    {CYAN}{_disp(line)}{RESET}")


# ══════════════════════════════════════════════════════════════════════════════
# Casos de prueba
# ══════════════════════════════════════════════════════════════════════════════

CASES: list[dict[str, Any]] = [
    {
        "label": "CASO 1 — Gramática LL(1) válida  (cadena: 'id + id * id')",
        "gramatica_parseable": True,
        "input": {
            "gramatica": (
                "E  -> T E'\n"
                "E' -> + T E' | \n"
                "T  -> F T'\n"
                "T' -> * F T' | \n"
                "F  -> ( E ) | id"
            ),
            "simbolo_inicial": "E",
            "cadena_entrada":  "id + id * id",
        },
    },
    {
        "label": "CASO 2 — Recursividad izquierda  (no LL(1), activa transformación)",
        "gramatica_parseable": False,
        "input": {
            "gramatica": (
                "E -> E + T | T\n"
                "T -> T * F | F\n"
                "F -> ( E ) | id"
            ),
            "simbolo_inicial": "E",
            "cadena_entrada":  "id * id + id",
        },
    },
    {
        "label": "CASO 3 — Gramática LL(1) válida, cadena INVÁLIDA  ('id + * id')",
        "gramatica_parseable": True,
        "input": {
            "gramatica": (
                "E  -> T E'\n"
                "E' -> + T E' | \n"
                "T  -> F T'\n"
                "T' -> * F T' | \n"
                "F  -> ( E ) | id"
            ),
            "simbolo_inicial": "E",
            "cadena_entrada":  "id + * id",
        },
    },
    {
        "label": "CASO 4 — Prefijos comunes  (necesita factorización por izquierda)",
        "gramatica_parseable": False,
        "input": {
            "gramatica": (
                "S -> a b | a c\n"
                "B -> b\n"
                "C -> c"
            ),
            "simbolo_inicial": "S",
            "cadena_entrada":  "a b",
        },
    },
]


def run_tests() -> None:
    print(f"\n{BOLD}{'='*72}")
    print("   LL(1) PARSER - SUITE DE PRUEBAS")
    print(f"{'='*72}{RESET}")

    for case in CASES:
        result = run_analysis(case["input"])

        show_summary(case["label"], result, case.get("gramatica_parseable"))
        show_input(case["input"])
        show_first_follow(result["conjuntos_first_follow"])
        show_ll1_table(result["construccion_tablas"])
        show_simulation(result["proceso_paso_a_paso"])
        show_transformation(result["sugerencias_transformacion"])
        print()

    print(f"\n{BOLD}{GREEN}  Todos los casos ejecutados.{RESET}\n")


if __name__ == "__main__":
    run_tests()
