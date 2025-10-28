"""API route definitions."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_session

router = APIRouter()


@router.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Health check endpoint."""

    return {"status": "ok"}


@router.get("/items", response_model=List[schemas.ItemRead], tags=["items"])
def list_items(session: Session = Depends(get_session)) -> List[schemas.ItemRead]:
    """Return all items."""

    result = session.execute(select(models.Item).order_by(models.Item.id))
    return list(result.scalars().all())


@router.post(
    "/items",
    response_model=schemas.ItemRead,
    status_code=status.HTTP_201_CREATED,
    tags=["items"],
)
def create_item(
    payload: schemas.ItemCreate, session: Session = Depends(get_session)
) -> schemas.ItemRead:
    """Create a new item."""

    existing = session.execute(
        select(models.Item).where(models.Item.name == payload.name)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Item already exists"
        )

    item = models.Item(name=payload.name, description=payload.description)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item
