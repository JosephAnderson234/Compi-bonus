"""Pydantic schemas for parser requests."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.parser_type import ParserType


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    gramatica: str = Field(..., min_length=1)
    simbolo_inicial: str = Field(..., min_length=1)
    cadena_entrada: str = Field(..., min_length=0)
    tipo_parser: ParserType | None = None


class ErrorResponse(BaseModel):
    error: str
    detalles: list[Any] | None = None
