"""Pydantic schemas for API responses and requests."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, validator

from app.security.sanitization import sanitize_text


class ItemCreate(BaseModel):
    name: str
    description: Optional[str] = None

    @validator("name", "description", pre=True)
    def _sanitize(cls, value: Optional[str]) -> Optional[str]:
        return sanitize_text(value)


class ItemRead(ItemCreate):
    id: int

    class Config:
        orm_mode = True
