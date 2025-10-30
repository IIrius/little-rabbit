from typing import Final

from fastapi import FastAPI

from app.api.telegram import router as telegram_router

APP_TITLE: Final[str] = "Backend API"

app = FastAPI(title=APP_TITLE)
app.include_router(telegram_router)


@app.get("/", tags=["root"])
async def read_root() -> dict[str, str]:
    return {"message": "Welcome to the backend API"}


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
