"""Vercel FastAPI service entrypoint; local development can still use the factory."""

from app.main import create_app

app = create_app()
