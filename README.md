# Deployment Service

A minimal FastAPI application demonstrating containerised deployment workflows, database migrations, and automated CI/CD.

## Repository layout

```
.
├── app/               # FastAPI application package (canonical backend)
├── alembic/           # Database migration environment and versions
├── docs/              # OpenAPI schema and security documentation
├── frontend/          # Vite + React placeholder workspace
├── infra/             # Infrastructure-as-code entry point
├── k8s/               # Kubernetes manifests
├── tests/             # Backend unit and integration tests
├── Dockerfile         # Production image definition
├── docker-compose.yml # Local development stack
└── requirements.txt   # Python dependencies
```

Only the root-level `app` package contains backend source code. All tooling and configuration reference this single location to avoid duplicate modules.

## Prerequisites

- Python 3.11+
- Docker with Docker Compose v2 (optional, for containerised runs)
- [pre-commit](https://pre-commit.com/#installation) for local quality checks

## Backend development

1. (Optional) Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the FastAPI application:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   Visit <http://127.0.0.1:8000/docs> for the interactive OpenAPI UI.

4. Apply database migrations when needed:
   ```bash
   alembic upgrade head
   ```

5. (Optional) Start Celery workers:
   ```bash
   celery -A app.celery_app.celery_app worker --loglevel=info
   ```

## Testing

Run the backend tests from the repository root:
```bash
pytest
```

## Linting and static analysis

The project standardises on:
- [Black](https://black.readthedocs.io/) for formatting
- [Ruff](https://docs.astral.sh/ruff/) for linting and import sorting
- [mypy](http://mypy-lang.org/) for static typing

Install pre-commit hooks to run the suite automatically:
```bash
pre-commit install
```
You can trigger individual tools manually:
```bash
ruff check app tests alembic
black app tests alembic
mypy app
```

## Docker Compose

Use the provided development composition to run API and database containers:
```bash
docker compose up --build
```
The API is exposed on <http://localhost:8000>. The production variant lives in `docker-compose.prod.yaml` and the Dockerfile runs Alembic migrations automatically on start-up.

## API documentation

The OpenAPI document is bundled at `docs/openapi.json`. Regenerate it after schema changes:
```bash
python docs/generate_openapi.py
```

## CI/CD

GitHub Actions workflows in `.github/workflows/` install dependencies with `pip`, enforce the linting suite, and run `pytest`. They use the single `app` package as the backend source of truth.
