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
