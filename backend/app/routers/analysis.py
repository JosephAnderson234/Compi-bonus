"""HTTP routes for parser analysis."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app.schemas.analysis import AnalysisRequest
from app.services.parser_service import ParserService, parser_service

router = APIRouter(tags=["analysis"])


def get_parser_service() -> ParserService:
    return parser_service


@router.post("/analyze")
async def analyze(
    payload: AnalysisRequest,
    service: ParserService = Depends(get_parser_service),
) -> dict[str, Any]:
    return await run_in_threadpool(service.analyze, payload)


@router.post("/")
async def analyze_root(
    payload: AnalysisRequest,
    service: ParserService = Depends(get_parser_service),
) -> dict[str, Any]:
    return await run_in_threadpool(service.analyze, payload)
