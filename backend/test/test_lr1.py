"""
test_lr1.py
===========
Suite de pruebas para Parser LR(1) (lr1_parser + lr_base).

Internamente el motor usa 'eps'; en consola se muestra 'ε'.

Uso:
    cd backend/test && python test_lr1.py
"""

from __future__ import annotations

import re
from typing import Any

import _paths  # noqa: F401

from lr1_parser import run_analysis

EPS_INTERNAL = "eps"
EPS_DISPLAY = "ε"

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
DIM = "\033[2m"


def _strip(s: str) -> str:
    return re.sub(r"\033\[[0-9;]*m", "", s)


def _eps(t: str) -> str:
    return t.replace(EPS_INTERNAL, EPS_DISPLAY)


def _col(text: str, width: int) -> str:
    raw = _strip(str(text))
    return str(text) + " " * max(width - len(raw), 0)


def _hline(widths: list[int], l: str, m: str, r: str, ch: str) -> str:
    return l + m.join(ch * (w + 2) for w in widths) + r


def print_table(
    title: str,
    headers: list[str],
    rows: list[list[str]],
    hdr_color: str = BOLD + CYAN,
) -> None:
    n = len(headers)
    widths = [len(_strip(h)) for h in headers]
    for row in rows:
        for i, c in enumerate(row[:n]):
            widths[i] = max(widths[i], min(len(_strip(str(c))), 52))

    def row_str(cells: list[str]) -> str:
        return "║" + "║".join(f" {_col(c, widths[i])} " for i, c in enumerate(cells[:n])) + "║"

    print()
    print(BOLD + BLUE + f"  ▶  {title}" + RESET)
    print(_hline(widths, "╔", "╦", "╗", "═"))
    print(row_str([f"{hdr_color}{h}{RESET}" for h in headers]))
    print(_hline(widths, "╠", "╬", "╣", "═"))
    for i, row in enumerate(rows):
        shade = DIM if i % 2 else ""
        print(row_str([f"{shade}{c}" for c in row[:n]]))
    print(_hline(widths, "╚", "╩", "╝", "═"))


def show_banner(label: str, result: dict[str, Any]) -> None:
    if "error" in result:
        print()
        print("═" * 72)
        print(f"  {BOLD}{label}{RESET}")
        print("═" * 72)
        print(f"  {RED}{BOLD}✘  {result['error']}{RESET}")
        return

    valid = result["cadena_valida"]
    icon = "✔" if valid else "✘"
    color = GREEN if valid else RED
    print()
    print("═" * 72)
    print(f"  {BOLD}{label}{RESET}")
    print("═" * 72)
    print(f"  {color}{BOLD}{icon}  cadena_valida = {valid}{RESET}")
    print(f"  {DIM}Mensaje: {_eps(result['mensaje'])}{RESET}")


def show_input(inp: dict[str, Any]) -> None:
    print(f"\n  {BOLD}Entrada del caso:{RESET}")
    print(f"  {DIM}Simbolo inicial:{RESET} {inp.get('simbolo_inicial', '')}")
    print(f"  {DIM}Cadena entrada:{RESET}  {inp['cadena_entrada']!r}")
    print(f"\n  {BOLD}Gramatica:{RESET}")
    for line in inp["gramatica"].strip().splitlines():
        print(f"    {CYAN}{_eps(line.strip())}{RESET}")


def show_afn(afn: dict[str, Any]) -> None:
    estados = afn.get("estados", [])
    if not estados:
        return
    print()
    print(BOLD + BLUE + f"  ▶  AFN de clausura ({afn.get('tipo', 'LR1')})" + RESET)
    for st in estados[:6]:
        print(f"\n  {BOLD}{st['estado']}{RESET}")
        for it in st.get("items", [])[:8]:
            print(f"    {DIM}{_eps(it)}{RESET}")
        if len(st.get("items", [])) > 8:
            print(f"    {DIM}... ({len(st['items'])} items){RESET}")
        if st.get("transiciones"):
            trans = ", ".join(f"{k}→{v}" for k, v in st["transiciones"].items())
            print(f"    {MAGENTA}{trans}{RESET}")
    if len(estados) > 6:
        print(f"\n  {DIM}... ({len(estados)} estados en total){RESET}")


def show_lr1_table(tabla: dict[str, Any]) -> None:
    columnas = tabla["columnas"]
    filas = tabla["filas"]

    def colorize(val: str) -> str:
        if val.startswith("S"):
            return f"{CYAN}{val}{RESET}"
        if val.startswith("R("):
            return f"{YELLOW}{_eps(val)}{RESET}"
        if val == "ACC":
            return f"{GREEN}{BOLD}{val}{RESET}"
        return f"{MAGENTA}{val}{RESET}"

    rows: list[list[str]] = []
    for fila in filas[:12]:
        row = []
        for col in columnas:
            raw = fila.get(col, "")
            row.append(colorize(_eps(raw)) if raw else "")
        rows.append(row)

    print_table(
        "Tabla LR(1)  — ACTION + GOTO",
        [_eps(c) for c in columnas],
        rows,
        hdr_color=BOLD + CYAN,
    )
    if len(filas) > 12:
        print(f"  {DIM}... ({len(filas)} filas en total){RESET}")

    conflictos = tabla.get("conflictos", [])
    if conflictos:
        print(f"\n  {RED}{BOLD}⚠  Conflictos en tabla ({len(conflictos)}){RESET}")
        for c in conflictos[:5]:
            print(
                f"    {RED}•{RESET} estado {c.get('estado')}, "
                f"simbolo '{c.get('simbolo')}': {_eps(c.get('conflicto', ''))}"
            )


def show_steps(steps: list[dict[str, Any]]) -> None:
    if not steps:
        print(f"\n  {DIM}(sin simulacion){RESET}")
        return

    rows: list[list[str]] = []
    for step in steps:
        accion = _eps(step["accion"])
        if "Aceptar" in accion or "ACC" in accion:
            colored = f"{GREEN}{BOLD}✔ {accion}{RESET}"
        elif "Error" in accion:
            colored = f"{RED}{BOLD}✘ {accion}{RESET}"
        elif "Shift" in accion or "Desplazar" in accion:
            colored = f"{CYAN}{accion}{RESET}"
        elif "Reduce" in accion or "Reducir" in accion:
            colored = f"{YELLOW}{accion}{RESET}"
        else:
            colored = accion
        rows.append([
            str(step["paso"]),
            step["pila"],
            _eps(step["entrada"]),
            colored,
        ])

    print_table(
        "Simulacion paso a paso",
        ["Paso", "Pila", "Entrada", "Accion"],
        rows,
        hdr_color=BOLD + GREEN,
    )


CASES: list[dict[str, Any]] = [
    {
        "label": "CASO 1 — Expresiones LR(1)  (cadena: 'id + id * id')",
        "input": {
            "gramatica": (
                "E  -> T E'\n"
                "E' -> + T E' | ε\n"
                "T  -> F T'\n"
                "T' -> * F T' | ε\n"
                "F  -> ( E ) | id"
            ),
            "simbolo_inicial": "E",
            "cadena_entrada": "id + id * id",
        },
    },
    {
        "label": "CASO 2 — Gramatica clasica LR(1)  (cadena: 'id * id + id')",
        "input": {
            "gramatica": (
                "E -> E + T | T\n"
                "T -> T * F | F\n"
                "F -> ( E ) | id"
            ),
            "simbolo_inicial": "E",
            "cadena_entrada": "id * id + id",
        },
    },
    {
        "label": "CASO 3 — Cadena invalida  (cadena: 'id + * id')",
        "input": {
            "gramatica": (
                "E  -> T E'\n"
                "E' -> + T E' | ε\n"
                "T  -> F T'\n"
                "T' -> * F T' | ε\n"
                "F  -> ( E ) | id"
            ),
            "simbolo_inicial": "E",
            "cadena_entrada": "id + * id",
        },
    },
    {
        "label": "CASO 4 — Produccion epsilon  (cadena: 'b')",
        "input": {
            "gramatica": "S -> A b\nA -> a | eps",
            "simbolo_inicial": "S",
            "cadena_entrada": "b",
        },
    },
]


def run_tests() -> None:
    print(f"\n{BOLD}{'═' * 72}")
    print("   LR(1) PARSER — SUITE DE PRUEBAS")
    print(f"{'═' * 72}{RESET}")

    for case in CASES:
        result = run_analysis(case["input"])
        show_banner(case["label"], result)
        if "error" in result:
            continue
        show_input(case["input"])
        show_afn(result.get("afn_clausura", {}))
        show_lr1_table(result["construccion_tablas"])
        show_steps(result.get("proceso_paso_a_paso", []))
        print()

    print(f"\n{BOLD}{GREEN}  Todos los casos ejecutados.{RESET}\n")


if __name__ == "__main__":
    run_tests()
