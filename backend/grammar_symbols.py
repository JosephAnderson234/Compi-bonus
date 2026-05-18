"""
grammar_symbols.py
Utilidades compartidas para generar nombres de símbolos nuevos (NT aumentado,
NTs de transformación LL(1)) sin colisionar con NTs, terminales ni reservados.
"""

from __future__ import annotations

from typing import Any, Iterable

DEFAULT_RESERVED = frozenset({"$", "eps"})


def symbols_in_production_bodies(productions: dict[str, Any]) -> set[str]:
    """Símbolos que aparecen en el cuerpo de las producciones (dict NT -> alts)."""
    found: set[str] = set()
    for alts in productions.values():
        for alt in alts:
            if isinstance(alt, (list, tuple)):
                for sym in alt:
                    if sym:
                        found.add(sym)
            elif isinstance(alt, str) and alt:
                found.add(alt)
    return found


def symbols_in_lr_productions(productions: list[Any]) -> set[str]:
    """Símbolos de una lista de Production (lr_base)."""
    found: set[str] = set()
    for prod in productions:
        found.add(prod.non_terminal)
        for sym in prod.transaction:
            if sym:
                found.add(sym)
    return found


def symbols_in_grammar(
    productions: dict[str, Any],
    terminals: Iterable[str] | None = None,
    extra_reserved: frozenset[str] = DEFAULT_RESERVED,
) -> set[str]:
    """
    Conjunto de símbolos ya usados: NTs (claves), cuerpos, terminales y reservados.
    """
    used = set(productions.keys()) | symbols_in_production_bodies(productions)
    if terminals is not None:
        used |= set(terminals)
    used |= set(extra_reserved)
    return used


def fresh_prime_name(base: str, used: set[str], suffix: str = "'") -> str:
    """
    Devuelve base', base'', ... hasta encontrar un nombre no presente en used.
    """
    candidate = base + suffix
    while candidate in used:
        suffix += "'"
        candidate = base + suffix
    return candidate
