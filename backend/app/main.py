from typing import Final

from fastapi import FastAPI

APP_TITLE: Final[str] = "Backend API"

app = FastAPI(title=APP_TITLE)


@app.get("/", tags=["root"])
async def read_root() -> dict[str, str]:
    return {"message": "Welcome to the backend API"}


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
