# Deployment Service

The Deployment Service is a FastAPI backend that ships everything through a single
canonical Python package, `app`. All supporting tooling is configured at the
repository root so quality gates, local runs, and CI pipelines share the same
entry points. The `pyproject.toml` file defines the behaviour of our formatters,
linting rules, type checker, and pytest settings, while pinned development
requirements guarantee identical environments locally, in Docker, and in CI.

## Repository layout

```
.
├── app/                  FastAPI application package (only backend source)
├── alembic/              Database migration environment and versions
├── docs/                 Developer documentation, OpenAPI artefacts, security notes
├── frontend/             Vite + React placeholder workspace
├── infra/                Infrastructure-as-code entry point
├── k8s/                  Kubernetes manifests
├── tests/                Backend unit and integration tests
├── Dockerfile            Production image definition
├── docker-compose.yml    Local development stack
├── pyproject.toml        Shared tooling configuration (formatting, lint, mypy, pytest)
├── requirements.txt      Application dependencies shared across all environments
└── requirements-dev.txt  Developer tooling pinned for linting, typing, and hooks
```

The backend code must live inside `app/`. Avoid creating additional top-level
packages—tooling assumes `app` is the single import namespace.

## Getting started

Prerequisites:

- Python 3.11+
- Docker with Docker Compose v2 (optional, for containerised runs)
- [pre-commit](https://pre-commit.com/#installation) for local quality checks

1. (Optional) Create an isolated Python environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install application and tooling dependencies:
   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   ```

3. Register the git hooks so formatting and linting run automatically:
   ```bash
   pre-commit install
   ```

Configuration from `pyproject.toml` adds `app` to `PYTHONPATH`, makes pytest and
typing aware of the single package, and aligns import sorting across tools.

## Quality checks

These commands run the same validations that CI enforces. Execute them from the
repository root.

### Linting and formatting

```bash
pre-commit run --all-files
```

To run individual tools:

```bash
ruff check .
black .
```

### Type checking

```bash
mypy app
```

### Tests

```bash
pytest
```

## Application runtime

### FastAPI application

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Visit <http://127.0.0.1:8000/docs> for the interactive OpenAPI UI.

### Celery worker

chore-centralize-tooling-config
Tooling dependencies are pinned in `requirements-dev.txt`, which layers on top of `requirements.txt` so local runs match CI.

Install pre-commit hooks to run the suite automatically:

main
```bash
celery -A app.celery_app.celery_app worker --loglevel=info
```

### Database migrations

```bash
chore-centralize-tooling-config
ruff check app tests alembic
black app tests alembic
mypy app tests alembic

alembic upgrade head
main
```

### Docker workflow

```bash
docker compose up --build
```

The API is exposed on <http://localhost:8000>. The production variant lives in
`docker-compose.prod.yaml`. The Dockerfile runs Alembic migrations before
launching Uvicorn.

### API schema regeneration

```bash
python docs/generate_openapi.py
```

## Additional documentation

- [Tooling and development guide](docs/development/tooling.md) — deeper
  reasoning, CI parity commands, and best practices.
- [Tooling analysis (Ticket 1)](docs/development/tooling.md#tooling-analysis-ticket-1) —
  historical context on the unified setup and how to keep it stable.
- [Security posture and mitigations](docs/SECURITY.md)
- [Deployment reference](docs/DEPLOYMENT.md)
