"""
test_lr0.py
===========
Suite de pruebas para LR0Parser.
Muestra resultados en tablas Unicode coloreadas en consola.

Usa el símbolo visual 'ε' (épsilon) al imprimir, aunque internamente
el motor usa 'eps'.

Uso:
    cd backend/test && python test_lr0.py
"""

from __future__ import annotations

import re
from typing import Any

import _paths  # noqa: F401  # BottomUp en sys.path

from lr0_parser import run_analysis

# ── Paleta ANSI ───────────────────────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
GREEN   = "\033[92m"
RED     = "\033[91m"
YELLOW  = "\033[93m"
CYAN    = "\033[96m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
DIM     = "\033[2m"

EPS_INTERNAL = "eps"
EPS_DISPLAY  = "ε"


# ══════════════════════════════════════════════════════════════════════════════
# Utilidades de visualización
# ══════════════════════════════════════════════════════════════════════════════

def _strip_ansi(s: str) -> str:
    return re.sub(r"\033\[[0-9;]*m", "", s)


def _eps(text: str) -> str:
    """Sustituye 'eps' por 'ε' en una cadena para el display."""
    return text.replace(EPS_INTERNAL, EPS_DISPLAY)


def _col(text: str, width: int) -> str:
    raw = _strip_ansi(str(text))
    pad = width - len(raw)
    return str(text) + (" " * max(pad, 0))


def _hline(widths: list[int], l: str, m: str, r: str, ch: str) -> str:
    return l + m.join(ch * (w + 2) for w in widths) + r


def print_table(
    title: str,
    headers: list[str],
    rows: list[list[str]],
    header_color: str = BOLD + CYAN,
) -> None:
    """Tabla Unicode genérica con anchos auto-calculados."""
    n = len(headers)
    widths = [len(_strip_ansi(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row[:n]):
            widths[i] = max(widths[i], min(len(_strip_ansi(str(cell))), 50))

    def row_str(cells: list[str]) -> str:
        parts = [f" {_col(c, widths[i])} " for i, c in enumerate(cells[:n])]
        return "║" + "║".join(parts) + "║"

    print()
    print(BOLD + BLUE + f"  ▶  {title}" + RESET)
    print(_hline(widths, "╔", "╦", "╗", "═"))
    hdr = [f"{header_color}{h}{RESET}" for h in headers]
    print(row_str(hdr))
    print(_hline(widths, "╠", "╬", "╣", "═"))
    for i, row in enumerate(rows):
        shade = DIM if i % 2 else ""
        print(row_str([f"{shade}{c}" for c in row[:n]]))
    print(_hline(widths, "╚", "╩", "╝", "═"))


# ══════════════════════════════════════════════════════════════════════════════
# Secciones de visualización por resultado
# ══════════════════════════════════════════════════════════════════════════════

def show_banner(label: str, result: dict[str, Any]) -> None:
    valid = result["cadena_valida"]
    icon  = "✔" if valid else "✘"
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
    print(BOLD + BLUE + f"  ▶  AFN de clausura ({afn.get('tipo', 'LR0')})" + RESET)
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


def show_lr0_table(tabla: dict[str, Any]) -> None:
    """Muestra la tabla LR(0) unificada (ACTION + GOTO)."""
    columnas: list[str] = tabla["columnas"]   # ["Estado", "id", ...]
    filas:    list[dict] = tabla["filas"]

    def cell_color(val: str) -> str:
        if val.startswith("S"):
            return f"{CYAN}{val}{RESET}"
        if val.startswith("R"):
            return f"{YELLOW}{val}{RESET}"
        if val == "ACC":
            return f"{GREEN}{BOLD}{val}{RESET}"
        if "/" in val:
            return f"{RED}{BOLD}{val}{RESET}"   # conflicto
        return f"{MAGENTA}{val}{RESET}"          # GOTO numérico

    rows: list[list[str]] = []
    for fila in filas:
        row: list[str] = []
        for col in columnas:
            raw = fila.get(col, "")
            row.append(cell_color(_eps(raw)) if raw else "")
        rows.append(row)

    print_table(
        "Tabla Unificada LR(0)  — ACTION + GOTO",
        [_eps(c) for c in columnas],
        rows,
        header_color=BOLD + CYAN,
    )

    # Leyenda
    print(
        f"  {DIM}Leyenda: "
        f"{CYAN}S<j>{RESET}{DIM}=Shift  "
        f"{YELLOW}R<i>{RESET}{DIM}=Reduce  "
        f"{GREEN}ACC{RESET}{DIM}=Aceptar  "
        f"{MAGENTA}<j>{RESET}{DIM}=GOTO  "
        f"{RED}X/Y{RESET}{DIM}=CONFLICTO{RESET}"
    )


def show_steps(steps: list[dict[str, Any]]) -> None:
    """Tabla de simulación paso a paso con colores semánticos."""
    if not steps:
        print(f"\n  {DIM}(simulación abortada por conflictos){RESET}")
        return

    rows: list[list[str]] = []
    for step in steps:
        accion = _eps(step["accion"])
        if "ACEPTAR" in accion:
            colored = f"{GREEN}{BOLD}✔ {accion}{RESET}"
        elif "ERROR" in accion:
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
        "Simulación Paso a Paso  (Shift-Reduce)",
        ["Paso", "Pila  (→ top)", "Entrada", "Acción"],
        rows,
        header_color=BOLD + GREEN,
    )


def show_conflicts(result: dict[str, Any]) -> None:
    """Resalta los conflictos si los hay (solo cuando cadena_valida es False y hay conflictos)."""
    if result["cadena_valida"]:
        return   # gramática y cadena OK → no hay nada que reportar
    msg = result["mensaje"]
    if "Detalles:" not in msg:
        return   # rechazo de cadena, no conflicto de tabla
    print(f"\n  {RED}{BOLD}⚠  CONFLICTOS DETECTADOS — Gramática NO es LR(0){RESET}")
    detalles = msg.split("Detalles:")[1].strip()
    for d in detalles.split(" | "):
        print(f"    {RED}•{RESET} {_eps(d.strip())}")


# ══════════════════════════════════════════════════════════════════════════════
# Casos de prueba
# ══════════════════════════════════════════════════════════════════════════════

CASES: list[dict[str, Any]] = [

    # ── Caso 1: Gramática LR(0) válida clásica ───────────────────────────────
    # G → aGb | ab   → LR(0), cadena "a a b b" es válida
    {
        "label": "CASO 1 — Gramática LR(0) válida  (cadena: 'a a b b')",
        "input": {
            "gramatica":       "G -> a G b | a b",
            "simbolo_inicial": "G",
            "cadena_entrada":  "a a b b",
        },
    },

    # ── Caso 2: Gramática LR(0) válida con reducción ─────────────────────────
    # S -> A A    A -> a | b   → LR(0) sin conflictos, cadena "a b"
    {
        "label": "CASO 2 — Gramática LR(0) válida  (cadena: 'a b')",
        "input": {
            "gramatica":       "S -> A A\nA -> a | b",
            "simbolo_inicial": "S",
            "cadena_entrada":  "a b",
        },
    },

    # ── Caso 3: Cadena inválida (gramática LR(0), cadena NO pertenece) ────────
    {
        "label": "CASO 3 — Gramática LR(0) válida, cadena INVÁLIDA  (cadena: 'a a b')",
        "input": {
            "gramatica":       "G -> a G b | a b",
            "simbolo_inicial": "G",
            "cadena_entrada":  "a a b",
        },
    },

    # ── Caso 4: Gramática CON conflicto Shift/Reduce ──────────────────────────
    # E -> E + T | T    T -> T * F | F    F -> ( E ) | id
    # Esta gramática clásica tiene conflictos S/R en LR(0)
    {
        "label": "CASO 4 — Gramática con CONFLICTO S/R  (E -> E + T | T ...)",
        "input": {
            "gramatica":       "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id",
            "simbolo_inicial": "E",
            "cadena_entrada":  "id * id",
        },
    },

    # ── Caso 5: Gramática con producción épsilon ──────────────────────────────
    # S -> A b    A -> a | eps
    {
        "label": "CASO 5 — Gramática con ε (eps)  (cadena: 'b')",
        "input": {
            "gramatica":       "S -> A b\nA -> a | eps",
            "simbolo_inicial": "S",
            "cadena_entrada":  "b",
        },
    },
]


def run_tests() -> None:
    print(f"\n{BOLD}{'═'*72}")
    print("   LR(0) PARSER — SUITE DE PRUEBAS")
    print(f"{'═'*72}{RESET}")

    for case in CASES:
        result = run_analysis(case["input"])
        show_banner(case["label"], result)
        show_input(case["input"])
        show_afn(result.get("afn_clausura", {}))
        show_lr0_table(result["construccion_tablas"])
        show_conflicts(result)
        show_steps(result["proceso_paso_a_paso"])
        print()

    print(f"\n{BOLD}{GREEN}  Todos los casos ejecutados.{RESET}\n")


if __name__ == "__main__":
    run_tests()
