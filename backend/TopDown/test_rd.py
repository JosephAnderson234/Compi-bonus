"""
test_rd_parser.py
=================
Suite de pruebas para RecursiveDescentParser.
Muestra los resultados en tablas y arbol visual en consola.

Uso:
    python test_rd_parser.py
"""

from __future__ import annotations

import re
from typing import Any

from dr_parser import run_analysis

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
    plain_headers = [_disp(h) for h in headers]
    plain_rows = [[_disp(c) for c in row] for row in rows]

    widths = [_visible_len(h) for h in plain_headers]
    for row in plain_rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], min(_visible_len(cell), 56))

    print()
    print(BOLD + BLUE + f"  >> {title}" + RESET)
    print(_hline(widths))
    print(_row(plain_headers, widths, [header_color] * len(plain_headers)))
    print(_hline(widths, mid="+"))
    for i, row in enumerate(plain_rows):
        row_color = DIM if i % 2 == 1 else ""
        print(_row(row, widths, [row_color] * len(row)))
    print(_hline(widths))


def show_banner(
    label: str,
    result: dict[str, Any],
    expected_parseable: bool | None,
) -> None:
    valid = result["cadena_valida"]
    parseable = result["gramatica_parseable"]
    color = GREEN if valid else RED
    icon = "[OK]" if valid else "[X]"
    p_color = GREEN if parseable else YELLOW
    print()
    print("=" * 72)
    print(f"  {BOLD}{label}{RESET}")
    print("=" * 72)
    print(f"  {p_color}{BOLD}gramatica_parseable (descenso recursivo) = {parseable}{RESET}")
    if expected_parseable is not None:
        ok = parseable == expected_parseable
        mark = f"{GREEN}[OK]" if ok else f"{RED}[X]"
        print(f"  {mark}  esperado gramatica_parseable = {expected_parseable}{RESET}")
    print(f"  {color}{BOLD}{icon}  cadena_valida = {valid}{RESET}")
    print(f"  {DIM}Mensaje: {result['mensaje']}{RESET}")


def show_input(inp: dict[str, Any]) -> None:
    print(f"\n  {BOLD}Entrada del caso:{RESET}")
    print(f"  {DIM}Simbolo inicial:{RESET} {inp['simbolo_inicial']}")
    cadena = repr(inp["cadena_entrada"])
    print(f"  {DIM}Cadena entrada:{RESET}  {_disp(cadena)}")
    print(f"\n  {BOLD}Gramatica:{RESET}")
    for line in inp["gramatica"].strip().splitlines():
        print(f"    {CYAN}{_disp(line.strip())}{RESET}")


def show_steps(steps: list[dict[str, Any]]) -> None:
    rows: list[list[str]] = []
    for step in steps:
        accion = step["accion"]
        if "ACEPTAR" in accion:
            colored = f"{GREEN}{BOLD}[OK] {accion}{RESET}"
        elif "RECHAZAR" in accion:
            colored = f"{RED}{BOLD}[X] {accion}{RESET}"
        elif "BACKTRACKING" in accion:
            colored = f"{YELLOW}<- {accion}{RESET}"
        elif accion.startswith("Match exitoso"):
            colored = f"{CYAN}{accion}{RESET}"
        elif "Llamando a NoTerminal" in accion:
            colored = f"{MAGENTA}{accion}{RESET}"
        elif "Fallo de match" in accion:
            colored = f"{RED}{DIM}{accion}{RESET}"
        elif "resuelto exitosamente" in accion:
            colored = f"{GREEN}{accion}{RESET}"
        elif "ninguna alternativa" in accion or "falló" in accion or "fallo" in accion:
            colored = f"{RED}{DIM}{accion}{RESET}"
        else:
            colored = accion
        rows.append([str(step["paso"]), colored])

    print_table(
        "Proceso paso a paso",
        ["Paso", "Accion"],
        rows,
        header_color=BOLD + GREEN,
    )


def _render_tree(node: dict[str, Any], prefix: str = "", is_last: bool = True) -> list[str]:
    connector = "`-- " if is_last else "|-- "
    lines = [f"{prefix}{connector}{BOLD}{CYAN}{_disp(node['name'])}{RESET}"]
    children = node.get("children", [])
    child_prefix = prefix + ("    " if is_last else "|   ")
    for i, child in enumerate(children):
        last = i == len(children) - 1
        lines.extend(_render_tree(child, child_prefix, last))
    return lines


def show_tree(tree: dict[str, Any] | None) -> None:
    print()
    print(BOLD + BLUE + "  >> Arbol de derivacion" + RESET)
    if tree is None:
        print(f"  {RED}(arbol no disponible — cadena invalida){RESET}")
        return

    print(f"  {BOLD}{CYAN}{_disp(tree['name'])}{RESET}")
    children = tree.get("children", [])
    for i, child in enumerate(children):
        last = i == len(children) - 1
        for line in _render_tree(child, "  ", last):
            print(line)


CASES: list[dict[str, Any]] = [
    {
        "label": "CASO 1 — S -> q A | q B   (cadena: 'q a c' — backtrack en A, exito en B)",
        "gramatica_parseable": True,
        "input": {
            "gramatica":       "S -> q A | q B\nA -> a b\nB -> a c",
            "simbolo_inicial": "S",
            "cadena_entrada":  "q a c",
        },
    },
    {
        "label": "CASO 2 — Expresiones aritmeticas (cadena: 'id + id')",
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
            "cadena_entrada":  "id + id",
        },
    },
    {
        "label": "CASO 3 — S -> q A | q B   (cadena: 'q a d' — RECHAZADA)",
        "gramatica_parseable": True,
        "input": {
            "gramatica":       "S -> q A | q B\nA -> a b\nB -> a c",
            "simbolo_inicial": "S",
            "cadena_entrada":  "q a d",
        },
    },
    {
        "label": "CASO 4 — Gramatica con epsilon (cadena: 'a b')",
        "gramatica_parseable": True,
        "input": {
            "gramatica":       "S -> A B\nA -> a | \nB -> b c | b",
            "simbolo_inicial": "S",
            "cadena_entrada":  "a b",
        },
    },
]


def run_tests() -> None:
    print(f"\n{BOLD}{'='*72}")
    print("   RECURSIVE DESCENT PARSER (Backtracking) - SUITE DE PRUEBAS")
    print(f"{'='*72}{RESET}")

    for case in CASES:
        result = run_analysis(case["input"])
        show_banner(case["label"], result, case.get("gramatica_parseable"))
        show_input(case["input"])
        show_steps(result["proceso_paso_a_paso"])
        show_tree(result["arbol_derivacion"])
        print()

    print(f"\n{BOLD}{GREEN}  Todos los casos ejecutados.{RESET}\n")


if __name__ == "__main__":
    run_tests()
