chore/init-monorepo-skeleton-fastapi-backend-poetry-precommit
# Monorepo Skeleton

This repository provides a minimal monorepo skeleton with a FastAPI backend, and
placeholders for future frontend, infrastructure, and documentation workspaces.

## Repository layout

```
.
├── backend/   # FastAPI application managed with Poetry
├── frontend/  # Reserved for frontend implementation
├── infra/     # Reserved for infrastructure-as-code assets
└── docs/      # Project documentation
```

## Prerequisites

- Python 3.11
- [Poetry](https://python-poetry.org/docs/#installation)
- [pre-commit](https://pre-commit.com/#installation)

## Getting started

1. **Install backend dependencies**

   ```bash
   cd backend
   poetry install
   ```

2. **Install pre-commit hooks** (run from the repository root):

   ```bash
   pre-commit install
   ```

3. **Run the FastAPI app locally**

   ```bash
   cd backend
   poetry run uvicorn app.main:app --reload
   ```

   The application will be available at <http://127.0.0.1:8000>. Visit
   `/docs` for the interactive OpenAPI documentation.

4. **Execute the test suite**

   ```bash
   cd backend
   poetry run pytest
   ```

## Tooling

- **Formatting**: [Black](https://black.readthedocs.io/) (enforced via pre-commit)
- **Linting**: [Ruff](https://docs.astral.sh/ruff/)
- **Static typing**: [mypy](http://mypy-lang.org/)

All tools are wired into pre-commit; they will run automatically on commit. You
can also run them manually:

```bash
cd backend
poetry run black --check app
poetry run ruff check app
poetry run mypy app
```

## Documentation

The `docs/` directory is the home for project documentation content. Start by
adding Markdown files or adopt your documentation generator of choice.

## Continuous integration

Placeholder GitHub Actions workflows are located under `.github/workflows/`.
They install backend dependencies and run linting and tests to validate
contributions. Update them as the project evolves.
=======
# Deployment Service

A minimal FastAPI application demonstrating containerized deployment workflows, database migrations, and automated CI/CD.

## Features

- FastAPI application with health and item endpoints
- SQLAlchemy models with Alembic migrations
- Docker and Docker Compose definitions for development and production
- Optional Kubernetes manifests
- GitHub Actions pipeline covering build, test, and deploy stages
- Pre-generated OpenAPI specification (`docs/openapi.json`)

## Prerequisites

- Python 3.11+
- Docker with Docker Compose v2

## Local Development

1. Create and activate a virtual environment (optional):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the development stack:
   ```bash
   docker compose up --build
   ```
   The API will be served from http://localhost:8000.
4. Run the test suite:
   ```bash
   pytest
   ```

## Production Docker Compose

Use the optimized production configuration:
```bash
docker compose -f docker-compose.prod.yaml up --build
```
The application container automatically runs database migrations before starting the API server.

## Database Migrations

Alembic is configured to use the `DATABASE_URL` environment variable.

- Generate a new migration:
  ```bash
  alembic revision -m "describe change"
  ```
- Apply migrations:
  ```bash
  alembic upgrade head
  ```

## API Documentation

Generate the OpenAPI document with:
```bash
python docs/generate_openapi.py
```
The generated schema is stored at `docs/openapi.json`.

## CI/CD

The GitHub Actions workflow (`.github/workflows/ci.yml`) performs:
1. **Build** – dependency installation and bytecode compilation.
2. **Test** – unit tests against PostgreSQL.
3. **Deploy** – Docker image build and artifact publication (main branch only).

## Deployment Guide

Detailed deployment instructions are available in `docs/DEPLOYMENT.md`.
main
