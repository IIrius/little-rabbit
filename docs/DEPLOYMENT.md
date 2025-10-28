# Deployment Guide

This document outlines how to build, test, and deploy the Deployment Service.

## Prerequisites

- Docker and Docker Compose v2
- Python 3.11 (for local development utilities)
- Access to a PostgreSQL instance (optional for local development - Docker Compose provides one)
- For Kubernetes deployments, access to a cluster and `kubectl`

## Local Development

1. Copy the environment template and adjust as needed:
   ```bash
   cp .env.example .env
   ```
2. Start the local stack:
   ```bash
   docker compose up --build
   ```
3. The API will be available at http://localhost:8000. Health check endpoint: `GET /api/health`.
4. Run tests locally:
   ```bash
   source .venv/bin/activate  # optional if you have a virtual environment
   pytest
   ```

## Production Docker Compose

1. Ensure the `.env.prod` file contains production-ready values.
2. Build and start the production stack:
   ```bash
   docker compose -f docker-compose.prod.yaml up --build
   ```
   The app container runs migrations automatically before starting.
3. To run the services in detached mode:
   ```bash
   docker compose -f docker-compose.prod.yaml up --build -d
   ```
4. To apply database migrations manually:
   ```bash
   docker compose -f docker-compose.prod.yaml run --rm app alembic upgrade head
   ```

## Alembic Migrations

- Create a new migration:
  ```bash
  alembic revision -m "describe change"
  ```
- Apply migrations:
  ```bash
  alembic upgrade head
  ```
- Downgrade migrations:
  ```bash
  alembic downgrade -1
  ```

Alembic reads the `DATABASE_URL` from environment variables. For local usage, ensure `.env` (or the `DATABASE_URL` env var) points to the correct database.

## Kubernetes Deployment (Optional)

1. Build and push the Docker image to your registry (adjust registry and tags accordingly):
   ```bash
   docker build -t ghcr.io/<your-org>/deployment-service:latest .
   docker push ghcr.io/<your-org>/deployment-service:latest
   ```
2. Create a secret containing environment variables:
   ```bash
   kubectl create secret generic deployment-service-env \
     --from-literal=APP_NAME="Deployment Service" \
     --from-literal=APP_ENV=production \
     --from-literal=DATABASE_URL="postgresql+psycopg2://user:password@postgres:5432/app"
   ```
3. Apply manifests:
   ```bash
   kubectl apply -f k8s/deployment.yaml
   kubectl apply -f k8s/service.yaml
   ```
4. Verify rollout:
   ```bash
   kubectl rollout status deployment/deployment-service
   ```

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/ci.yml`) executes three stages:

1. **Build** – installs dependencies and runs a basic compilation check.
2. **Test** – repeats dependency installation and runs the test suite against PostgreSQL.
3. **Deploy** – (main branch only) builds the production Docker image and publishes a deployment summary artifact.

Pipeline runs automatically on pushes to `main` and `deploy/*`, and for all pull requests.

## Generating API Documentation

The OpenAPI definition is stored in `docs/openapi.json` and can be regenerated with:
```bash
python docs/generate_openapi.py
```
The resulting JSON can be imported into tooling such as Swagger UI or Stoplight.

## Troubleshooting

- **Database connection errors**: confirm the `DATABASE_URL` value points at a reachable PostgreSQL instance.
- **Migrations failing**: ensure the database user has privileges to create and alter tables.
- **Kubernetes deployment pending**: verify image availability and pull secrets.
