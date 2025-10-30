# Tooling and development guide

This document explains how the unified backend setup is configured and how to
run every developer workflow locally. All commands assume you are executing them
from the repository root so that the shared configuration in `pyproject.toml`
can take effect.

## Background and goals

### Tooling analysis (Ticket 1)

Ticket&nbsp;1 introduced a single canonical backend package (`app`) and merged all
tooling settings under `pyproject.toml`. The motivating constraints were:

- Avoid duplicate packages such as `application/` or `src/` that caused import
  ambiguity in the past.
- Share dependency versions across Docker, CI, and local environments by
  keeping `requirements.txt` as the single source of truth for application and
  testing dependencies.
- Configure pytest, mypy, Ruff, and Black once so they agree on the Python path
  (`app` is injected into `PYTHONPATH`) and import sorting rules.

Maintaining this structure keeps the environment reproducible and requires no
per-developer path overrides.

## Installing development dependencies

1. Create and activate a virtual environment (optional but recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install the pinned requirements that power both runtime and tooling:
   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   ```

3. Install the git hooks so the same checks run before each commit:
   ```bash
   pre-commit install
   ```

`pyproject.toml` configures `ruff`, `black`, `mypy`, and `pytest`. No additional
`PYTHONPATH` exports or ad-hoc config files are required.

## Running local quality checks

- Format and lint everything:
  ```bash
  pre-commit run --all-files
  ```

- Run individual tools (helpful for quick feedback):
  ```bash
  ruff check .
  black .
  mypy app
  ```

- Execute the test suite:
  ```bash
  pytest
  ```

These commands mirror the CI workflow so passing locally guarantees the checks
will pass remotely.

## CI parity command list

Use this sequence before opening a pull request:

```bash
ruff check .
black --check .
mypy app
pytest
```

All four commands use the settings in `pyproject.toml`, so they run consistently
on every machine and in GitHub Actions.

## Regenerating artefacts

- Refresh the OpenAPI specification after changing API routes:
  ```bash
  python docs/generate_openapi.py
  ```

- Apply the latest database schema with Alembic:
  ```bash
  alembic upgrade head
  ```

- Start the application and background worker locally:
  ```bash
  uvicorn app.main:app --reload
  celery -A app.celery_app.celery_app worker --loglevel=info
  ```

## Common pitfalls to avoid

- **Import order drift** – Always rely on Ruff's import sorting (`ruff check`) or
  Black to avoid accidental reorderings.
- **Manual `PYTHONPATH` changes** – Do not export custom paths; pytest already
  adds `app` to the import path via `pyproject.toml`.
- **Duplicate packages** – All backend code belongs under `app/`. Adding sibling
  packages breaks the unified configuration and confuses tooling discovery.
- **Forgetting to run hooks** – Run `pre-commit run --all-files` before pushing
  to benefit from the same formatting and linting that CI will enforce.

For a broader architectural view and historical decisions, consult the
[Tooling analysis (Ticket 1)](#tooling-analysis-ticket-1) section above before
modifying the setup.
