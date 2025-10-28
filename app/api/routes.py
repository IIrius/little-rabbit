"""API route definitions."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_session
from app.security.audit import record_audit_event
from app.security.encryption import get_data_encryptor

router = APIRouter()


@router.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Health check endpoint."""

    return {"status": "ok"}


@router.get("/items", response_model=List[schemas.ItemRead], tags=["items"])
def list_items(session: Session = Depends(get_session)) -> List[schemas.ItemRead]:
    """Return all items."""

    encryptor = get_data_encryptor()
    result = session.execute(select(models.Item).order_by(models.Item.id))
    items = [
        schemas.ItemRead(
            id=item.id,
            name=item.name,
            description=encryptor.decrypt(item.description),
        )
        for item in result.scalars().all()
    ]
    record_audit_event("items.list", count=len(items))
    return items


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

    encryptor = get_data_encryptor()

    existing = session.execute(
        select(models.Item).where(models.Item.name == payload.name)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Item already exists"
        )

    item = models.Item(
        name=payload.name,
        description=encryptor.encrypt(payload.description),
    )
    session.add(item)
    session.commit()
    session.refresh(item)

    record_audit_event("items.create", item_id=item.id, name=item.name)
    return schemas.ItemRead(
        id=item.id,
        name=item.name,
        description=encryptor.decrypt(item.description),
    )
