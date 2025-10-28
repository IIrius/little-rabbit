"""Pydantic schemas for API responses and requests."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ItemCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ItemRead(ItemCreate):
    id: int

    class Config:
        orm_mode = True
