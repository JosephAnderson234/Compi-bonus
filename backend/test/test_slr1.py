"""
test_slr1.py
============
Suite de pruebas para SLR1Parser.
Muestra resultados en tablas Unicode coloreadas.

Casos
-----
1. Gramática expresiones E->E+T|T ... (falla LR(0), PASA SLR(1))
2. Cadena inválida sobre la gramática anterior
3. Gramática con conflicto SLR(1) → demostración del mensaje ultra-detallado

Símbolo épsilon: 'eps' internamente, 'ε' en la consola.

Uso:
    cd backend/test && python test_slr1.py
"""

from __future__ import annotations

import re
from typing import Any

import _paths  # noqa: F401

from slr1_parser import run_analysis
from lr0_parser import run_analysis as run_lr0

EPS_STR    = "eps"
EPS_SYMBOL = "ε"

# ── ANSI ──────────────────────────────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
GREEN   = "\033[92m"
RED     = "\033[91m"
YELLOW  = "\033[93m"
CYAN    = "\033[96m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
DIM     = "\033[2m"


# ══════════════════════════════════════════════════════════════════════════════
# Utilidades de tabla
# ══════════════════════════════════════════════════════════════════════════════

def _strip(s: str) -> str:
    return re.sub(r"\033\[[0-9;]*m", "", s)

def _eps(t: str) -> str:
    return t.replace(EPS_STR, EPS_SYMBOL)

def _col(text: str, width: int) -> str:
    raw = _strip(str(text))
    return str(text) + " " * max(width - len(raw), 0)

def _hline(widths: list[int], l: str, m: str, r: str, ch: str) -> str:
    return l + m.join(ch * (w + 2) for w in widths) + r

def print_table(title: str, headers: list[str], rows: list[list[str]],
                hdr_color: str = BOLD + CYAN) -> None:
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


# ══════════════════════════════════════════════════════════════════════════════
# Secciones de visualización
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
    # Solo mostrar la primera línea del mensaje (el detalle va en show_conflicts)
    first_line = _eps(result["mensaje"].split("\n")[0])
    print(f"  {DIM}Mensaje: {first_line}{RESET}")


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
    print(BOLD + BLUE + f"  ▶  AFN de clausura ({afn.get('tipo', 'SLR1')})" + RESET)
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


def show_first_follow(ff: dict[str, dict]) -> None:
    rows = [
        [nt,
         ", ".join(_eps(x) for x in data["FIRST"]) or "∅",
         ", ".join(_eps(x) for x in data["FOLLOW"]) or "∅"]
        for nt, data in ff.items()
    ]
    print_table("Conjuntos FIRST / FOLLOW", ["NT", "FIRST", "FOLLOW"],
                rows, hdr_color=BOLD + MAGENTA)


def show_slr_table(tabla: dict[str, Any]) -> None:
    columnas = tabla["columnas"]
    filas    = tabla["filas"]

    def colorize(val: str) -> str:
        if val.startswith("S"):   return f"{CYAN}{val}{RESET}"
        if val.startswith("R"):   return f"{YELLOW}{val}{RESET}"
        if val == "ACC":          return f"{GREEN}{BOLD}{val}{RESET}"
        if "/" in val:            return f"{RED}{BOLD}{val}{RESET}"
        return f"{MAGENTA}{val}{RESET}"          # GOTO numérico

    rows: list[list[str]] = []
    for fila in filas:
        row = [_eps(fila.get(col, "")) for col in columnas]
        row = [colorize(c) if c else "" for c in row]
        rows.append(row)

    print_table(
        "Tabla Unificada SLR(1)  — ACTION + GOTO",
        [_eps(c) for c in columnas], rows, hdr_color=BOLD + CYAN,
    )
    print(
        f"  {DIM}Leyenda: "
        f"{CYAN}S<j>{RESET}{DIM}=Shift  "
        f"{YELLOW}R<i>{RESET}{DIM}=Reduce(FOLLOW-filtrado)  "
        f"{GREEN}ACC{RESET}{DIM}=Aceptar  "
        f"{MAGENTA}<j>{RESET}{DIM}=GOTO  "
        f"{RED}X/Y{RESET}{DIM}=CONFLICTO{RESET}"
    )


def show_steps(steps: list[dict]) -> None:
    if not steps:
        print(f"\n  {DIM}(simulación abortada o vacía){RESET}")
        return

    rows: list[list[str]] = []
    for s in steps:
        accion = _eps(s.get("accion", s.get("action", "")))
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
        rows.append([str(s["paso"]), s["pila"], _eps(s["entrada"]), colored])

    print_table("Simulación Paso a Paso  (Shift-Reduce)",
                ["Paso", "Pila  (→ top)", "Entrada", "Acción"],
                rows, hdr_color=BOLD + GREEN)


def show_conflict_detail(result: dict[str, Any]) -> None:
    """Imprime el mensaje de conflicto completo con colores."""
    if result["cadena_valida"]:
        return
    msg = result["mensaje"]
    if "Detalles:" not in msg and "[Shift/Reduce]" not in msg and "[Reduce/Reduce]" not in msg:
        return   # rechazo de cadena, no conflicto

    print(f"\n  {RED}{BOLD}⚠  CONFLICTOS DETECTADOS — Gramática NO es SLR(1){RESET}")
    # Imprimir línea por línea con colores semánticos
    for line in msg.split("\n")[2:]:     # saltar las dos primeras líneas de encabezado
        raw = line.strip()
        if raw.startswith("[Shift/Reduce]") or raw.startswith("[Reduce/Reduce]"):
            print(f"\n  {RED}{BOLD}{_eps(raw)}{RESET}")
        elif raw.startswith("• Shift"):
            print(f"  {CYAN}{_eps(raw)}{RESET}")
        elif raw.startswith("• Reduce"):
            print(f"  {YELLOW}{_eps(raw)}{RESET}")
        elif raw.startswith("↳"):
            print(f"  {DIM}{_eps(raw)}{RESET}")
        elif raw:
            print(f"  {_eps(raw)}")


# ══════════════════════════════════════════════════════════════════════════════
# Función auxiliar: ejecutar LR(0) y mostrar si falla
# ══════════════════════════════════════════════════════════════════════════════

def compare_lr0(input_data: dict, label: str) -> None:
    """Llama al analizador LR(0) con la misma gramática para comparar."""
    r = run_lr0(input_data)
    valid = r["cadena_valida"]
    has_conflict = not valid and "Detalles:" in r["mensaje"]
    if has_conflict:
        print(
            f"\n  {YELLOW}{BOLD}⚡ Comparación LR(0):{RESET} "
            f"{RED}Falla con {len(r.get('construccion_tablas', {}).get('filas', []))} "
            f"estados — conflictos detectados.{RESET}"
        )
        # Mostrar solo las celdas con conflicto
        for fila in r["construccion_tablas"]["filas"]:
            for k, v in fila.items():
                if "/" in str(v):
                    print(f"    {RED}Conflicto LR(0): Estado {fila['Estado']}, "
                          f"col '{k}': {v}{RESET}")
    else:
        print(f"\n  {GREEN}⚡ Comparación LR(0): También aceptada.{RESET}")


# ══════════════════════════════════════════════════════════════════════════════
# Casos de prueba
# ══════════════════════════════════════════════════════════════════════════════

CASES: list[dict[str, Any]] = [

    # ── Caso 1 ──────────────────────────────────────────────────────────────
    # Gramática clásica de expresiones aritméticas.
    # * Falla en LR(0): estados de reduce colocan R en todas las columnas,
    #   creando conflictos S/R con '+' y '*'.
    # * Pasa SLR(1): FOLLOW(E)={+,$,)}, FOLLOW(T)={+,*,$,)}, FOLLOW(F)={+,*,$,)}
    #   → las acciones de reduce NO solapan con ningún shift.
    {
        "label": (
            "CASO 1 — E→E+T|T, T→T*F|F, F→(E)|id\n"
            "         ✘ LR(0) falla  |  ✔ SLR(1) pasa  (cadena: 'id + id * id')"
        ),
        "input": {
            "gramatica":       "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id",
            "simbolo_inicial": "E",
            "cadena_entrada":  "id + id * id",
        },
        "compare_lr0": True,
    },

    # ── Caso 2 ──────────────────────────────────────────────────────────────
    # Misma gramática, cadena inválida.
    {
        "label": "CASO 2 — Misma gramática, cadena INVÁLIDA  (cadena: 'id + * id')",
        "input": {
            "gramatica":       "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id",
            "simbolo_inicial": "E",
            "cadena_entrada":  "id + * id",
        },
        "compare_lr0": False,
    },

    # ── Caso 3 ──────────────────────────────────────────────────────────────
    # Gramática con conflicto Reduce/Reduce en SLR(1).
    # S -> A a | b A c | B c | b B a
    # A -> d        B -> d
    # Estado que contiene [A->d.] y [B->d.]:
    #   FOLLOW(A) = {a, c},  FOLLOW(B) = {a, c}  → solapamiento → R/R
    {
        "label": "CASO 3 — Conflicto Reduce/Reduce en SLR(1)  (S→Aa|bAc|Bc|bBa, A→d, B→d)",
        "input": {
            "gramatica": (
                "S -> A a | b A c | B c | b B a\n"
                "A -> d\n"
                "B -> d"
            ),
            "simbolo_inicial": "S",
            "cadena_entrada":  "d a",
        },
        "compare_lr0": False,
    },

    # ── Caso 4 ──────────────────────────────────────────────────────────────
    # Gramática simple con ε (eps): S -> A b, A -> a | eps
    # SLR(1) debería detectar el mismo S/R que LR(0) porque eps amplía FOLLOW.
    {
        "label": "CASO 4 — Gramática con ε  (S→Ab, A→a|eps, cadena: 'b')",
        "input": {
            "gramatica":       "S -> A b\nA -> a | eps",
            "simbolo_inicial": "S",
            "cadena_entrada":  "b",
        },
        "compare_lr0": False,
    },
]


def run_tests() -> None:
    print(f"\n{BOLD}{'═'*72}")
    print("   SLR(1) PARSER — SUITE DE PRUEBAS")
    print(f"{'═'*72}{RESET}")

    for case in CASES:
        result = run_analysis(case["input"])
        show_banner(case["label"], result)
        show_input(case["input"])
        show_afn(result.get("afn_clausura", {}))

        if "conjuntos_first_follow" in result:
            show_first_follow(result["conjuntos_first_follow"])

        show_slr_table(result["construccion_tablas"])

        if case.get("compare_lr0"):
            compare_lr0(case["input"], case["label"])

        show_conflict_detail(result)
        show_steps(result["proceso_paso_a_paso"])
        print()

    print(f"\n{BOLD}{GREEN}  Todos los casos ejecutados.{RESET}\n")


if __name__ == "__main__":
    run_tests()
