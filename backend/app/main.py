"""FastAPI application factory and middleware setup."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import APP_DESCRIPTION, APP_NAME, APP_VERSION
from app.routers.analysis import router as analysis_router

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router)


@app.get("/")
async def root() -> dict[str, object]:
    return {
        "service": APP_NAME,
        "version": APP_VERSION,
        "status": "ok",
        "endpoints": ["POST /analyze", "POST /"],
        "supported_parsers": ["LL1", "RD", "DR", "LR0", "SLR1", "LR1", "LALR1"],
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        content = detail
    else:
        content = {"error": str(detail)}
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": "Datos de entrada invalidos.", "detalles": exc.errors()},
    )
