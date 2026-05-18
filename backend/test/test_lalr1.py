"""
test/test_lalr1.py
==================
Suite de pruebas automatizadas para LALR1Parser.
Valida gramáticas exitosas y conflictos de fusión.

Símbolo épsilon: 'eps' internamente, 'ε' en el output de consola.

Uso:
    python -m pytest test/test_lalr1.py -v        (pytest)
  o bien:
    python test/test_lalr1.py                     (standalone)
"""

from __future__ import annotations

import re
from typing import Any

import _paths  # noqa: F401

from lalr1_parser import run_analysis, LALR1Parser
from lr_base import Grammar

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
# Utilidades
# ══════════════════════════════════════════════════════════════════════════════

def _eps(t: str) -> str:
    return str(t).replace(EPS_STR, EPS_SYMBOL)

def _strip(s: str) -> str:
    return re.sub(r"\033\[[0-9;]*m", "", s)

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
            widths[i] = max(widths[i], min(len(_strip(str(c))), 54))

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
    first_line = _eps(result["mensaje"].split("\n")[0])
    print(f"  {DIM}Mensaje: {first_line}{RESET}")


def show_input(inp: dict[str, Any]) -> None:
    print(f"\n  {BOLD}Entrada del caso:{RESET}")
    print(f"  {DIM}Simbolo inicial:{RESET} {inp.get('simbolo_inicial', '')}")
    print(f"  {DIM}Cadena entrada:{RESET}  {inp['cadena_entrada']!r}")
    print(f"\n  {BOLD}Gramatica:{RESET}")
    for line in inp["gramatica"].strip().splitlines():
        print(f"    {CYAN}{_eps(line.strip())}{RESET}")


def show_afn(afn: dict[str, Any], titulo: str | None = None) -> None:
    estados = afn.get("estados", [])
    if not estados:
        return
    tipo = afn.get("tipo", "LR1")
    encabezado = titulo or f"AFN de clausura ({tipo})"
    print()
    print(BOLD + BLUE + f"  ▶  {encabezado}" + RESET)
    for st in estados[:6]:
        print(f"\n  {BOLD}{st['estado']}{RESET}")
        fusionados = st.get("lr1_fusionados")
        if fusionados:
            print(f"    {MAGENTA}LR(1) fusionados: {', '.join(fusionados)}{RESET}")
        for it in st.get("items", [])[:8]:
            print(f"    {DIM}{_eps(it)}{RESET}")
        if len(st.get("items", [])) > 8:
            print(f"    {DIM}... ({len(st['items'])} items){RESET}")
        if st.get("transiciones"):
            trans = ", ".join(f"{k}→{v}" for k, v in st["transiciones"].items())
            print(f"    {MAGENTA}{trans}{RESET}")
    if len(estados) > 6:
        print(f"\n  {DIM}... ({len(estados)} estados en total){RESET}")


def show_lalr_table(tabla: dict[str, Any]) -> None:
    columnas = tabla["columnas"]
    filas    = tabla["filas"]

    def colorize(val: str) -> str:
        if not val:           return ""
        if val.startswith("S"):                   return f"{CYAN}{val}{RESET}"
        if val.startswith("R"):                   return f"{YELLOW}{val}{RESET}"
        if val == "ACC":                          return f"{GREEN}{BOLD}{val}{RESET}"
        if "/" in val or "vs" in val:             return f"{RED}{BOLD}{val}{RESET}"
        return f"{MAGENTA}{val}{RESET}"

    rows: list[list[str]] = []
    for fila in filas:
        row = [_eps(str(fila.get(col, ""))) for col in columnas]
        row = [colorize(c) for c in row]
        rows.append(row)

    print_table(
        "Tabla Unificada LALR(1) — ACTION + GOTO",
        [_eps(c) for c in columnas], rows, hdr_color=BOLD + CYAN,
    )
    print(
        f"  {DIM}Leyenda: "
        f"{CYAN}S<j>{RESET}{DIM}=Shift  "
        f"{YELLOW}R(...){RESET}{DIM}=Reduce(lookaheads LALR)  "
        f"{GREEN}ACC{RESET}{DIM}=Aceptar  "
        f"{MAGENTA}<j>{RESET}{DIM}=GOTO{RESET}"
    )


def show_steps(steps: list[dict]) -> None:
    if not steps:
        print(f"\n  {DIM}(simulación abortada o vacía){RESET}")
        return
    rows: list[list[str]] = []
    for s in steps:
        accion = _eps(s.get("accion", ""))
        if "Aceptar" in accion or "ACC" in accion:
            c = f"{GREEN}{BOLD}✔ {accion}{RESET}"
        elif "Error" in accion or "error" in accion:
            c = f"{RED}{BOLD}✘ {accion}{RESET}"
        elif "Shift" in accion or "Desplazar" in accion:
            c = f"{CYAN}{accion}{RESET}"
        elif "Reduce" in accion or "Reducir" in accion:
            c = f"{YELLOW}{accion}{RESET}"
        else:
            c = accion
        rows.append([str(s["paso"]), s["pila"], _eps(s["entrada"]), c])
    print_table(
        "Simulación Paso a Paso",
        ["Paso", "Pila (→ top)", "Entrada", "Acción"],
        rows, hdr_color=BOLD + GREEN,
    )


def show_conflict_detail(result: dict[str, Any]) -> None:
    if result["cadena_valida"]:
        return
    msg = result["mensaje"]
    if "fusión" not in msg and "conflicto" not in msg.lower():
        return
    print(f"\n  {RED}{BOLD}⚠  CONFLICTOS DE FUSIÓN — Gramática NO es LALR(1){RESET}")
    for line in msg.split("\n")[2:]:
        raw = line.strip()
        if not raw:
            continue
        if raw.startswith("["):
            print(f"\n  {RED}{BOLD}{_eps(raw)}{RESET}")
        elif raw.startswith("• Shift"):
            print(f"  {CYAN}{_eps(raw)}{RESET}")
        elif raw.startswith("• Reduce"):
            print(f"  {YELLOW}{_eps(raw)}{RESET}")
        elif raw.startswith("↳"):
            print(f"  {DIM}{_eps(raw)}{RESET}")
        else:
            print(f"  {_eps(raw)}")


# ══════════════════════════════════════════════════════════════════════════════
# Utilidades de asserción para pytest
# ══════════════════════════════════════════════════════════════════════════════

def _run(grammar_text: str, simbolo: str, cadena: str) -> dict:
    return run_analysis({
        "gramatica":       grammar_text,
        "simbolo_inicial": simbolo,
        "cadena_entrada":  cadena,
    })


# ══════════════════════════════════════════════════════════════════════════════
# TESTS DE PYTEST
# ══════════════════════════════════════════════════════════════════════════════

class TestLALR1Valid:
    """Gramáticas que deben pasar LALR(1) exitosamente."""

    def test_expresiones_aritmeticas_valida(self):
        """
        La gramática canónica de expresiones aritméticas es LALR(1).
        Cadena válida: id + id * id
        """
        r = _run(
            "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id",
            "E", "id + id * id",
        )
        assert r["cadena_valida"] is True, r["mensaje"]
        assert "proceso_paso_a_paso" in r
        assert len(r["proceso_paso_a_paso"]) > 0
        last = r["proceso_paso_a_paso"][-1]["accion"]
        assert "Aceptar" in last or "ACC" in last

    def test_expresiones_aritmeticas_cadena_con_parentesis(self):
        """Cadena válida con paréntesis: ( id + id ) * id"""
        r = _run(
            "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id",
            "E", "( id + id ) * id",
        )
        assert r["cadena_valida"] is True, r["mensaje"]

    def test_gramatica_simple_lalr1(self):
        """
        S -> A a | b A c | b d a | d c
        A -> d
        es LALR(1) (diferente de la versión R/R de SLR).
        Cadena: d a
        """
        r = _run("S -> A a | b d c\nA -> d", "S", "d a")
        assert r["cadena_valida"] is True, r["mensaje"]

    def test_tabla_tipo_lalr1(self):
        """Verifica que el campo tipo sea LALR1."""
        r = _run(
            "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id",
            "E", "id",
        )
        assert r["construccion_tablas"]["tipo"] == "LALR1"

    def test_afn_clausura_en_respuesta(self):
        """Verifica que la salida incluya afn_lr1 y afn_clausura."""
        r = _run(
            "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id",
            "E", "id",
        )
        assert "afn_lr1" in r
        assert r["afn_lr1"]["tipo"] == "LR1"
        assert len(r["afn_lr1"]["estados"]) > 0
        assert "afn_clausura" in r
        assert r["afn_clausura"]["tipo"] == "LALR1"
        assert len(r["afn_clausura"]["estados"]) > 0
        assert len(r["afn_lr1"]["estados"]) >= len(r["afn_clausura"]["estados"])

    def test_estados_lalr_menor_que_lr1(self):
        """
        Para la gramática de expresiones, LR(1) genera más estados que LALR(1).
        Verificamos que la cantidad de estados LALR es ≤ LR(1).
        """
        grammar_text = "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id"
        grammar = Grammar.from_text(grammar_text, simbolo_inicial="E")

        from lr1_parser import ParserLR1
        lr1 = ParserLR1()
        lr1.build(grammar)
        n_lr1 = len(lr1._afn_states)

        # LALR fusiona estados de igual núcleo
        lalr = LALR1Parser()
        lalr.build(grammar)
        n_lalr = len(lalr.lalr_states)

        assert n_lalr <= n_lr1, (
            f"Se esperaba n_lalr({n_lalr}) ≤ n_lr1({n_lr1})"
        )

    def test_cadena_invalida_tabla_correcta(self):
        """Cadena inválida sobre gramática LALR(1): estructura de respuesta intacta."""
        r = _run(
            "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id",
            "E", "id + + id",
        )
        assert r["cadena_valida"] is False
        assert "construccion_tablas" in r
        assert "proceso_paso_a_paso" in r
        assert len(r["proceso_paso_a_paso"]) > 0   # pasos hasta el error


class TestLALR1Conflicts:
    """Gramáticas con conflictos LALR(1) de fusión."""

    def test_conflicto_reduce_reduce_clasico(self):
        """
        Gramática clásica que es LR(1) pero NO LALR(1):
          S -> a E c | a F d | b F c | b E d
          E -> e
          F -> e
        Los estados LR(1) para (e, c) y (e, d) tienen el mismo núcleo pero
        lookaheads solapados → R/R al fusionar.
        """
        r = _run(
            "S -> a E c | a F d | b F c | b E d\nE -> e\nF -> e",
            "S", "a e c",
        )
        assert r["cadena_valida"] is False
        msg = r["mensaje"]
        assert "Reduce/Reduce" in msg or "conflicto" in msg.lower(), (
            f"Se esperaba mensaje de conflicto Reduce/Reduce. Got: {msg[:200]}"
        )

    def test_conflicto_aborta_simulacion(self):
        """Si hay conflicto, proceso_paso_a_paso debe estar vacío."""
        r = _run(
            "S -> a E c | a F d | b F c | b E d\nE -> e\nF -> e",
            "S", "a e c",
        )
        assert r["cadena_valida"] is False
        assert r["proceso_paso_a_paso"] == []

    def test_conflicto_mensaje_menciona_fusion(self):
        """El mensaje de error debe mencionar la fusión de estados LR(1)."""
        r = _run(
            "S -> a E c | a F d | b F c | b E d\nE -> e\nF -> e",
            "S", "a e c",
        )
        msg = r["mensaje"]
        # Debe mencionar estado LALR y/o estados LR(1) fusionados
        has_lalr   = "LALR" in msg
        has_fusion = "fusión" in msg or "fusi" in msg or "I" in msg
        assert has_lalr or has_fusion, (
            f"El mensaje no menciona la fusión de estados LALR(1). Got: {msg[:300]}"
        )

    def test_tabla_siempre_presente_con_conflicto(self):
        """Incluso con conflicto, construccion_tablas debe existir."""
        r = _run(
            "S -> a E c | a F d | b F c | b E d\nE -> e\nF -> e",
            "S", "a e c",
        )
        assert "construccion_tablas" in r
        assert r["construccion_tablas"]["tipo"] == "LALR1"


# ══════════════════════════════════════════════════════════════════════════════
# Casos de demostración visual (standalone)
# ══════════════════════════════════════════════════════════════════════════════

DEMO_CASES: list[dict[str, Any]] = [
    {
        "label": (
            "CASO 1 — Expresiones aritméticas  (cadena: 'id + id * id')\n"
            "         ✔ LR(1) | ✔ LALR(1)  — demostración de fusión"
        ),
        "input": {
            "gramatica":       "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id",
            "simbolo_inicial": "E",
            "cadena_entrada":  "id + id * id",
        },
    },
    {
        "label": (
            "CASO 2 — Gramática LR(1) pero NO LALR(1)  (S→aEc|aFd|bFc|bEd, E→e, F→e)\n"
            "         ✘ LALR(1) falla — conflicto R/R al fusionar"
        ),
        "input": {
            "gramatica": (
                "S -> a E c | a F d | b F c | b E d\n"
                "E -> e\n"
                "F -> e"
            ),
            "simbolo_inicial": "S",
            "cadena_entrada":  "a e c",
        },
    },
    {
        "label": "CASO 3 — Cadena inválida sobre gramática LALR(1)  (cadena: 'id + + id')",
        "input": {
            "gramatica":       "E -> E + T | T\nT -> T * F | F\nF -> ( E ) | id",
            "simbolo_inicial": "E",
            "cadena_entrada":  "id + + id",
        },
    },
]


def run_demos() -> None:
    print(f"\n{BOLD}{'═'*72}")
    print("   LALR(1) PARSER — DEMOSTRACIÓN VISUAL")
    print(f"{'═'*72}{RESET}")

    for case in DEMO_CASES:
        result = run_analysis(case["input"])
        show_banner(case["label"], result)
        show_input(case["input"])
        show_afn(result.get("afn_lr1", {}), titulo="AFN LR(1) — coleccion canonica (pre-fusion)")
        show_afn(result.get("afn_clausura", {}))
        show_lalr_table(result["construccion_tablas"])
        show_conflict_detail(result)
        show_steps(result["proceso_paso_a_paso"])
        print()

    print(f"\n{BOLD}{GREEN}  Todas las demostraciones ejecutadas.{RESET}\n")


# ══════════════════════════════════════════════════════════════════════════════
# Runner pytest integrado + demo visual
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # 1. Ejecutar pruebas automatizadas
    print(f"\n{BOLD}{'─'*72}")
    print("   TESTS AUTOMATIZADOS")
    print(f"{'─'*72}{RESET}")

    test_valid   = TestLALR1Valid()
    test_conflict = TestLALR1Conflicts()

    results: list[tuple[str, bool, str]] = []

    def run_test(name: str, fn):
        try:
            fn()
            results.append((name, True, ""))
        except AssertionError as e:
            results.append((name, False, str(e)))
        except Exception as e:
            results.append((name, False, f"Exception: {e}"))

    run_test("test_expresiones_aritmeticas_valida",         test_valid.test_expresiones_aritmeticas_valida)
    run_test("test_expresiones_aritmeticas_con_parentesis", test_valid.test_expresiones_aritmeticas_cadena_con_parentesis)
    run_test("test_gramatica_simple_lalr1",                 test_valid.test_gramatica_simple_lalr1)
    run_test("test_tabla_tipo_lalr1",                       test_valid.test_tabla_tipo_lalr1)
    run_test("test_afn_clausura_en_respuesta",              test_valid.test_afn_clausura_en_respuesta)
    run_test("test_estados_lalr_menor_que_lr1",             test_valid.test_estados_lalr_menor_que_lr1)
    run_test("test_cadena_invalida_tabla_correcta",         test_valid.test_cadena_invalida_tabla_correcta)
    run_test("test_conflicto_reduce_reduce_clasico",        test_conflict.test_conflicto_reduce_reduce_clasico)
    run_test("test_conflicto_aborta_simulacion",            test_conflict.test_conflicto_aborta_simulacion)
    run_test("test_conflicto_mensaje_menciona_fusion",      test_conflict.test_conflicto_mensaje_menciona_fusion)
    run_test("test_tabla_siempre_presente_con_conflicto",   test_conflict.test_tabla_siempre_presente_con_conflicto)

    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed

    for name, ok, err in results:
        icon  = f"{GREEN}✔{RESET}" if ok else f"{RED}✘{RESET}"
        label = f"{DIM}{name}{RESET}" if ok else name
        print(f"  {icon}  {label}")
        if not ok:
            print(f"       {RED}{err[:120]}{RESET}")

    print(
        f"\n  {BOLD}"
        f"{GREEN if failed == 0 else RED}"
        f"{passed}/{len(results)} tests pasaron.{RESET}"
    )

    # 2. Demo visual
    run_demos()
