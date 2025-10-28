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
