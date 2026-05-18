"""Compatibility entry point for local development.

Vercel uses api/index.py, but keeping this file allows local imports such as
uvicorn main:app from the backend directory.
"""

from app.main import app

