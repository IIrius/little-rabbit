# Backend Service

This directory contains the FastAPI-based backend service for the monorepo skeleton.

## Local development

```bash
cd backend
poetry install
poetry run uvicorn backend_app.main:app --reload
```

Refer to the repository root `README.md` for more information.

## Telegram integration

The FastAPI API exposes endpoints to register Telegram bots per workspace and
bind channels. Follow the step-by-step guide in `../docs/TELEGRAM.md` to set up
bot tokens and configure delivery strategies.
