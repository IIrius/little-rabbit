"""API route definitions."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, status
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_session
from app.security.audit import record_audit_event
from app.security.encryption import get_data_encryptor
from app.security.sanitization import sanitize_text
from app.services.moderation import (
    listen_for_client_messages,
    moderation_decision_to_dict,
    moderation_notifier,
    moderation_request_to_dict,
    notify_moderation_event,
)

router = APIRouter()


@router.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Health check endpoint."""

    return {"status": "ok"}


@router.get("/metrics", tags=["observability"])
def metrics() -> Response:
    """Expose Prometheus metrics for scraping."""

    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


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


@router.get(
    "/moderation/queue",
    response_model=List[schemas.ModerationRequestRead],
    tags=["moderation"],
)
def moderation_queue(
    session: Session = Depends(get_session),
) -> List[schemas.ModerationRequestRead]:
    """Return pending moderation requests ordered by submission time."""

    result = session.execute(
        select(models.ModerationRequest)
        .where(models.ModerationRequest.status == models.ModerationStatus.PENDING)
        .order_by(models.ModerationRequest.submitted_at.asc(), models.ModerationRequest.id.asc())
    )
    requests = result.scalars().all()
    return [
        schemas.ModerationRequestRead(**moderation_request_to_dict(item))
        for item in requests
    ]


@router.get(
    "/moderation/requests/{request_id}",
    response_model=schemas.ModerationRequestRead,
    tags=["moderation"],
)
def moderation_request_details(
    request_id: int, session: Session = Depends(get_session)
) -> schemas.ModerationRequestRead:
    """Return details for a specific moderation request."""

    request = session.get(models.ModerationRequest, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Moderation request not found")
    return schemas.ModerationRequestRead(**moderation_request_to_dict(request))


@router.post(
    "/moderation/requests/{request_id}/decision",
    response_model=schemas.ModerationDecisionRead,
    tags=["moderation"],
)
def decide_moderation_request(
    request_id: int,
    payload: schemas.ModerationDecisionCreate,
    session: Session = Depends(get_session),
) -> schemas.ModerationDecisionRead:
    """Apply a moderation decision to a request."""

    request = session.get(models.ModerationRequest, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Moderation request not found")
    if request.status != models.ModerationStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Moderation request already resolved")

    decision_enum = (
        models.ModerationStatus.APPROVED
        if payload.decision == "approved"
        else models.ModerationStatus.REJECTED
    )
    request.status = decision_enum
    decision = models.ModerationDecision(
        request=request,
        decision=decision_enum,
        decided_by=payload.actor or "console",
        reason=payload.reason,
    )
    session.add(decision)
    session.commit()
    session.refresh(request)
    session.refresh(decision)

    record_audit_event(
        "moderation.decision",
        request_id=request.id,
        decision=decision_enum.value,
        actor=decision.decided_by,
    )
    notify_moderation_event(
        {
            "type": "moderation.decision",
            "request": moderation_request_to_dict(request),
            "decision": moderation_decision_to_dict(decision),
        }
    )
    return schemas.ModerationDecisionRead(**moderation_decision_to_dict(decision))


@router.post(
    "/moderation/requests/bulk-decision",
    response_model=List[schemas.ModerationDecisionRead],
    tags=["moderation"],
)
def bulk_decide_moderation_requests(
    payload: schemas.ModerationBulkDecision,
    session: Session = Depends(get_session),
) -> List[schemas.ModerationDecisionRead]:
    """Apply a moderation decision to multiple requests."""

    result = session.execute(
        select(models.ModerationRequest).where(
            models.ModerationRequest.id.in_(payload.request_ids)
        )
    )
    requests = result.scalars().all()
    lookup = {item.id: item for item in requests}
    missing = [req_id for req_id in payload.request_ids if req_id not in lookup]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown moderation request IDs: {missing}",
        )

    already_resolved = [
        item.id for item in requests if item.status != models.ModerationStatus.PENDING
    ]
    if already_resolved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Moderation requests already resolved: {already_resolved}",
        )

    decision_enum = (
        models.ModerationStatus.APPROVED
        if payload.decision == "approved"
        else models.ModerationStatus.REJECTED
    )
    decisions: list[models.ModerationDecision] = []
    ordered_requests: list[models.ModerationRequest] = [
        lookup[req_id] for req_id in payload.request_ids
    ]
    for request in ordered_requests:
        request.status = decision_enum
        decision = models.ModerationDecision(
            request=request,
            decision=decision_enum,
            decided_by=payload.actor or "console",
            reason=payload.reason,
        )
        session.add(decision)
        decisions.append(decision)

    session.commit()
    for request in ordered_requests:
        session.refresh(request)
    for decision in decisions:
        session.refresh(decision)

    record_audit_event(
        "moderation.bulk_decision",
        count=len(decisions),
        decision=decision_enum.value,
        actor=payload.actor or "console",
    )
    notify_moderation_event(
        {
            "type": "moderation.bulk_decision",
            "decision": decision_enum.value,
            "requests": [
                moderation_request_to_dict(request) for request in ordered_requests
            ],
            "decisions": [
                moderation_decision_to_dict(decision) for decision in decisions
            ],
        }
    )
    return [
        schemas.ModerationDecisionRead(**moderation_decision_to_dict(decision))
        for decision in decisions
    ]


@router.get(
    "/moderation/history",
    response_model=List[schemas.ModerationDecisionRead],
    tags=["moderation"],
)
def moderation_history(
    status_filter: str | None = Query(None, alias="status"),
    workspace: str | None = Query(None),
    actor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> List[schemas.ModerationDecisionRead]:
    """Return moderation decision history with optional filters."""

    query = (
        select(models.ModerationDecision)
        .join(models.ModerationRequest)
        .order_by(desc(models.ModerationDecision.decided_at))
    )

    if status_filter:
        normalized = (sanitize_text(status_filter) or "").lower()
        valid_states = {models.ModerationStatus.APPROVED.value, models.ModerationStatus.REJECTED.value}
        if normalized not in valid_states:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid status filter",
            )
        query = query.where(models.ModerationDecision.decision == models.ModerationStatus(normalized))

    if workspace:
        workspace_clean = sanitize_text(workspace)
        if workspace_clean:
            query = query.where(
                models.ModerationRequest.workspace == workspace_clean
            )

    if actor:
        actor_clean = sanitize_text(actor)
        if actor_clean:
            query = query.where(
                models.ModerationDecision.decided_by == actor_clean
            )

    result = session.execute(query.limit(limit).offset(offset))
    decisions = result.scalars().all()
    return [
        schemas.ModerationDecisionRead(**moderation_decision_to_dict(decision))
        for decision in decisions
    ]


@router.websocket("/moderation/notifications")
async def moderation_notifications(websocket: WebSocket) -> None:
    """WebSocket endpoint for moderation decision notifications."""

    await moderation_notifier.connect(websocket)
    try:
        await websocket.send_json({"type": "moderation.connected"})
        await listen_for_client_messages(websocket)
    finally:
        moderation_notifier.disconnect(websocket)
