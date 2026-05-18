"""Parser type definitions and normalization helpers."""

from __future__ import annotations

from enum import Enum


class ParserType(str, Enum):
    LL1 = "LL1"
    RD = "RD"
    DR = "DR"
    LR0 = "LR0"
    SLR1 = "SLR1"
    LR1 = "LR1"
    LALR1 = "LALR1"


def normalize_parser_type(value: str | ParserType | None, default: str) -> str:
    """Return a canonical parser type string, applying aliases and defaults."""

    if value is None:
        return default

    raw = value.value if isinstance(value, ParserType) else str(value)
    normalized = raw.strip().upper()

    if normalized == "DR":
        return "RD"

    valid = {item.value for item in ParserType}
    if normalized not in valid:
        supported = ", ".join(sorted(valid))
        raise ValueError(f"tipo_parser '{raw}' no soportado. Use uno de: {supported}")

    return normalized
