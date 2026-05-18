"""Service layer that dispatches requests to the existing parser engines."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Callable

from fastapi import HTTPException

from app.core.config import DEFAULT_PARSER_TYPE
from app.models.parser_type import ParserType, normalize_parser_type
from app.schemas.analysis import AnalysisRequest
from app.utils.parser_loader import ensure_parser_paths


ParserRunner = Callable[[dict[str, Any]], dict[str, Any]]


class ParserService:
    """Resolve the requested parser and execute the corresponding analysis."""

    def analyze(self, payload: AnalysisRequest) -> dict[str, Any]:
        request_data = payload.model_dump()
        parser_type = normalize_parser_type(
            request_data.get("tipo_parser"),
            default=DEFAULT_PARSER_TYPE,
        )
        request_data["tipo_parser"] = parser_type

        runner = self._resolve_runner(parser_type)

        try:
            result = runner(request_data)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - defensive guard
            raise HTTPException(
                status_code=500,
                detail="Error interno al ejecutar el analizador.",
            ) from exc

        if isinstance(result, dict) and "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    @staticmethod
    @lru_cache(maxsize=None)
    def _resolve_runner(parser_type: str) -> ParserRunner:
        ensure_parser_paths()

        if parser_type == ParserType.LL1.value:
            from ll1_parser import run_analysis as runner
            return runner

        if parser_type in {ParserType.RD.value, ParserType.DR.value}:
            from dr_parser import run_analysis as runner
            return runner

        if parser_type == ParserType.LR0.value:
            from lr0_parser import run_analysis as runner
            return runner

        if parser_type == ParserType.SLR1.value:
            from slr1_parser import run_analysis as runner
            return runner

        if parser_type == ParserType.LR1.value:
            from lr1_parser import run_analysis as runner
            return runner

        if parser_type == ParserType.LALR1.value:
            from lalr1_parser import run_analysis as runner
            return runner

        supported = ", ".join(sorted(item.value for item in ParserType))
        raise HTTPException(
            status_code=400,
            detail=f"tipo_parser '{parser_type}' no soportado. Use uno de: {supported}",
        )


parser_service = ParserService()
