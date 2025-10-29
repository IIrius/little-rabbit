"""API route definitions."""
from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timezone
from typing import Dict, List
from uuid import uuid4

<feat/moderation-console-ui-backend-ws
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, status
=======
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.encoders import jsonable_encoder
main
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import SessionLocal, get_session
from app.pipeline.runner import run_workspace_pipeline_sync
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


class PipelineStatusBroadcaster:
    """Manages workspace-specific queues for pipeline status broadcasts."""

    def __init__(self) -> None:
        self._queues: Dict[str, set[asyncio.Queue[dict[str, object]]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, workspace: str) -> asyncio.Queue[dict[str, object]]:
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        async with self._lock:
            listeners = self._queues.setdefault(workspace, set())
            listeners.add(queue)
        return queue

    async def unsubscribe(
        self, workspace: str, queue: asyncio.Queue[dict[str, object]]
    ) -> None:
        async with self._lock:
            listeners = self._queues.get(workspace)
            if listeners is None:
                return
            listeners.discard(queue)
            if not listeners:
                self._queues.pop(workspace, None)

    async def publish(self, workspace: str, payload: dict[str, object]) -> None:
        async with self._lock:
            listeners = list(self._queues.get(workspace, set()))
        for queue in listeners:
            await queue.put(payload)


pipeline_status_broadcaster = PipelineStatusBroadcaster()


def _encode_run(run: models.PipelineRun) -> dict[str, object]:
    model = schemas.PipelineRunRead.from_orm(run)
    return jsonable_encoder(model)


def _serialize_run_event(run: models.PipelineRun) -> dict[str, object]:
    return {
        "event": "update",
        "workspace": run.workspace,
        "run": _encode_run(run),
    }


def _snapshot_payload(workspace: str, runs: List[models.PipelineRun]) -> dict[str, object]:
    return {
        "event": "snapshot",
        "workspace": workspace,
        "runs": [_encode_run(run) for run in runs],
    }


async def _execute_pipeline_run(run_id: int, workspace: str) -> None:
    session = SessionLocal()
    try:
        run = session.get(models.PipelineRun, run_id)
        if run is None:
            return

        run.status = models.PipelineRunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(run)
        await pipeline_status_broadcaster.publish(workspace, _serialize_run_event(run))

        try:
            result = await asyncio.to_thread(run_workspace_pipeline_sync, workspace)
        except Exception as exc:  # pragma: no cover - defensive
            run.status = models.PipelineRunStatus.FAILURE
            run.finished_at = datetime.now(timezone.utc)
            run.message = str(exc)
            session.commit()
            session.refresh(run)
            await pipeline_status_broadcaster.publish(workspace, _serialize_run_event(run))
            return

        run.status = models.PipelineRunStatus.SUCCESS
        run.finished_at = datetime.now(timezone.utc)
        published = result.get("published", 0)
        run.message = f"published {published} articles"
        session.commit()
        session.refresh(run)
        await pipeline_status_broadcaster.publish(workspace, _serialize_run_event(run))
    finally:
        session.close()


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
feat/moderation-console-ui-backend-ws
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
=======
    "/workspaces/{workspace}/sources",
    response_model=List[schemas.WorkspaceSourceRead],
    tags=["workspaces"],
)
def list_workspace_sources(
    workspace: str, session: Session = Depends(get_session)
) -> List[schemas.WorkspaceSourceRead]:
    result = session.execute(
        select(models.WorkspaceSource)
        .where(models.WorkspaceSource.workspace == workspace)
        .order_by(models.WorkspaceSource.name)
    )
    return [schemas.WorkspaceSourceRead.from_orm(source) for source in result.scalars().all()]


@router.post(
    "/workspaces/{workspace}/sources",
    response_model=schemas.WorkspaceSourceRead,
    status_code=status.HTTP_201_CREATED,
    tags=["workspaces"],
)
def create_workspace_source(
    workspace: str,
    payload: schemas.WorkspaceSourceCreate,
    session: Session = Depends(get_session),
) -> schemas.WorkspaceSourceRead:
    existing = session.execute(
        select(models.WorkspaceSource).where(
            models.WorkspaceSource.workspace == workspace,
            models.WorkspaceSource.name == payload.name,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source already exists in workspace",
        )

    source = models.WorkspaceSource(
        workspace=workspace,
        name=payload.name,
        kind=payload.kind,
        endpoint=str(payload.endpoint) if payload.endpoint else None,
        is_active=payload.is_active,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    record_audit_event(
        "workspace.source.create",
        workspace=workspace,
        source_id=source.id,
        kind=source.kind.value,
    )
    return schemas.WorkspaceSourceRead.from_orm(source)


@router.put(
    "/workspaces/{workspace}/sources/{source_id}",
    response_model=schemas.WorkspaceSourceRead,
    tags=["workspaces"],
)
def update_workspace_source(
    workspace: str,
    source_id: int,
    payload: schemas.WorkspaceSourceUpdate,
    session: Session = Depends(get_session),
) -> schemas.WorkspaceSourceRead:
    source = session.get(models.WorkspaceSource, source_id)
    if source is None or source.workspace != workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    duplicate = session.execute(
        select(models.WorkspaceSource).where(
            models.WorkspaceSource.workspace == workspace,
            models.WorkspaceSource.name == payload.name,
            models.WorkspaceSource.id != source_id,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source already exists in workspace",
        )

    source.name = payload.name
    source.kind = payload.kind
    source.endpoint = str(payload.endpoint) if payload.endpoint else None
    source.is_active = payload.is_active
    session.commit()
    session.refresh(source)
    record_audit_event(
        "workspace.source.update", workspace=workspace, source_id=source.id
    )
    return schemas.WorkspaceSourceRead.from_orm(source)


@router.delete(
    "/workspaces/{workspace}/sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["workspaces"],
)
def delete_workspace_source(
    workspace: str, source_id: int, session: Session = Depends(get_session)
) -> Response:
    source = session.get(models.WorkspaceSource, source_id)
    if source is None or source.workspace != workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    session.delete(source)
    session.commit()
    record_audit_event(
        "workspace.source.delete", workspace=workspace, source_id=source_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/workspaces/{workspace}/proxies",
    response_model=List[schemas.WorkspaceProxyRead],
    tags=["workspaces"],
)
def list_workspace_proxies(
    workspace: str, session: Session = Depends(get_session)
) -> List[schemas.WorkspaceProxyRead]:
    result = session.execute(
        select(models.WorkspaceProxy)
        .where(models.WorkspaceProxy.workspace == workspace)
        .order_by(models.WorkspaceProxy.name)
    )
    return [schemas.WorkspaceProxyRead.from_orm(proxy) for proxy in result.scalars().all()]


@router.post(
    "/workspaces/{workspace}/proxies",
    response_model=schemas.WorkspaceProxyRead,
    status_code=status.HTTP_201_CREATED,
    tags=["workspaces"],
)
def create_workspace_proxy(
    workspace: str,
    payload: schemas.WorkspaceProxyCreate,
    session: Session = Depends(get_session),
) -> schemas.WorkspaceProxyRead:
    existing = session.execute(
        select(models.WorkspaceProxy).where(
            models.WorkspaceProxy.workspace == workspace,
            models.WorkspaceProxy.name == payload.name,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proxy already exists in workspace",
        )

    address = str(payload.address)
    duplicate_address = session.execute(
        select(models.WorkspaceProxy).where(
            models.WorkspaceProxy.workspace == workspace,
            models.WorkspaceProxy.address == address,
        )
    ).scalar_one_or_none()
    if duplicate_address is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proxy address already registered",
        )

    proxy = models.WorkspaceProxy(
        workspace=workspace,
        name=payload.name,
        protocol=payload.protocol,
        address=address,
        is_active=payload.is_active,
    )
    session.add(proxy)
    session.commit()
    session.refresh(proxy)
    record_audit_event(
        "workspace.proxy.create", workspace=workspace, proxy_id=proxy.id
    )
    return schemas.WorkspaceProxyRead.from_orm(proxy)


@router.put(
    "/workspaces/{workspace}/proxies/{proxy_id}",
    response_model=schemas.WorkspaceProxyRead,
    tags=["workspaces"],
)
def update_workspace_proxy(
    workspace: str,
    proxy_id: int,
    payload: schemas.WorkspaceProxyUpdate,
    session: Session = Depends(get_session),
) -> schemas.WorkspaceProxyRead:
    proxy = session.get(models.WorkspaceProxy, proxy_id)
    if proxy is None or proxy.workspace != workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy not found")

    name_conflict = session.execute(
        select(models.WorkspaceProxy).where(
            models.WorkspaceProxy.workspace == workspace,
            models.WorkspaceProxy.name == payload.name,
            models.WorkspaceProxy.id != proxy_id,
        )
    ).scalar_one_or_none()
    if name_conflict is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proxy already exists in workspace",
        )

    address = str(payload.address)
    address_conflict = session.execute(
        select(models.WorkspaceProxy).where(
            models.WorkspaceProxy.workspace == workspace,
            models.WorkspaceProxy.address == address,
            models.WorkspaceProxy.id != proxy_id,
        )
    ).scalar_one_or_none()
    if address_conflict is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proxy address already registered",
        )

    proxy.name = payload.name
    proxy.protocol = payload.protocol
    proxy.address = address
    proxy.is_active = payload.is_active
    session.commit()
    session.refresh(proxy)
    record_audit_event(
        "workspace.proxy.update", workspace=workspace, proxy_id=proxy.id
    )
    return schemas.WorkspaceProxyRead.from_orm(proxy)


@router.delete(
    "/workspaces/{workspace}/proxies/{proxy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["workspaces"],
)
def delete_workspace_proxy(
    workspace: str, proxy_id: int, session: Session = Depends(get_session)
) -> Response:
    proxy = session.get(models.WorkspaceProxy, proxy_id)
    if proxy is None or proxy.workspace != workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy not found")

    session.delete(proxy)
    session.commit()
    record_audit_event(
        "workspace.proxy.delete", workspace=workspace, proxy_id=proxy_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/workspaces/{workspace}/telegram-channels",
    response_model=List[schemas.WorkspaceTelegramChannelRead],
    tags=["workspaces"],
)
def list_workspace_channels(
    workspace: str, session: Session = Depends(get_session)
) -> List[schemas.WorkspaceTelegramChannelRead]:
    result = session.execute(
        select(models.WorkspaceTelegramChannel)
        .where(models.WorkspaceTelegramChannel.workspace == workspace)
        .order_by(models.WorkspaceTelegramChannel.name)
    )
    return [
        schemas.WorkspaceTelegramChannelRead.from_orm(channel)
        for channel in result.scalars().all()
    ]


@router.post(
    "/workspaces/{workspace}/telegram-channels",
    response_model=schemas.WorkspaceTelegramChannelRead,
    status_code=status.HTTP_201_CREATED,
    tags=["workspaces"],
)
def create_workspace_channel(
    workspace: str,
    payload: schemas.WorkspaceTelegramChannelCreate,
    session: Session = Depends(get_session),
) -> schemas.WorkspaceTelegramChannelRead:
    existing_name = session.execute(
        select(models.WorkspaceTelegramChannel).where(
            models.WorkspaceTelegramChannel.workspace == workspace,
            models.WorkspaceTelegramChannel.name == payload.name,
        )
    ).scalar_one_or_none()
    if existing_name is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Telegram channel already exists in workspace",
        )

    existing_chat = session.execute(
        select(models.WorkspaceTelegramChannel).where(
            models.WorkspaceTelegramChannel.workspace == workspace,
            models.WorkspaceTelegramChannel.chat_id == payload.chat_id,
        )
    ).scalar_one_or_none()
    if existing_chat is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Telegram chat already registered",
        )

    channel = models.WorkspaceTelegramChannel(
        workspace=workspace,
        name=payload.name,
        chat_id=payload.chat_id,
        is_active=payload.is_active,
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    record_audit_event(
        "workspace.telegram.create", workspace=workspace, channel_id=channel.id
    )
    return schemas.WorkspaceTelegramChannelRead.from_orm(channel)


@router.put(
    "/workspaces/{workspace}/telegram-channels/{channel_id}",
    response_model=schemas.WorkspaceTelegramChannelRead,
    tags=["workspaces"],
)
def update_workspace_channel(
    workspace: str,
    channel_id: int,
    payload: schemas.WorkspaceTelegramChannelUpdate,
    session: Session = Depends(get_session),
) -> schemas.WorkspaceTelegramChannelRead:
    channel = session.get(models.WorkspaceTelegramChannel, channel_id)
    if channel is None or channel.workspace != workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Telegram channel not found"
        )

    name_conflict = session.execute(
        select(models.WorkspaceTelegramChannel).where(
            models.WorkspaceTelegramChannel.workspace == workspace,
            models.WorkspaceTelegramChannel.name == payload.name,
            models.WorkspaceTelegramChannel.id != channel_id,
        )
    ).scalar_one_or_none()
    if name_conflict is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Telegram channel already exists in workspace",
        )

    chat_conflict = session.execute(
        select(models.WorkspaceTelegramChannel).where(
            models.WorkspaceTelegramChannel.workspace == workspace,
            models.WorkspaceTelegramChannel.chat_id == payload.chat_id,
            models.WorkspaceTelegramChannel.id != channel_id,
        )
    ).scalar_one_or_none()
    if chat_conflict is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Telegram chat already registered",
        )

    channel.name = payload.name
    channel.chat_id = payload.chat_id
    channel.is_active = payload.is_active
    session.commit()
    session.refresh(channel)
    record_audit_event(
        "workspace.telegram.update", workspace=workspace, channel_id=channel.id
    )
    return schemas.WorkspaceTelegramChannelRead.from_orm(channel)


@router.delete(
    "/workspaces/{workspace}/telegram-channels/{channel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["workspaces"],
)
def delete_workspace_channel(
    workspace: str, channel_id: int, session: Session = Depends(get_session)
) -> Response:
    channel = session.get(models.WorkspaceTelegramChannel, channel_id)
    if channel is None or channel.workspace != workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Telegram channel not found"
        )

    session.delete(channel)
    session.commit()
    record_audit_event(
        "workspace.telegram.delete", workspace=workspace, channel_id=channel_id
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/workspaces/{workspace}/pipeline/runs",
    response_model=List[schemas.PipelineRunRead],
    tags=["workspaces", "pipeline"],
)
def list_pipeline_runs(
    workspace: str, session: Session = Depends(get_session)
) -> List[schemas.PipelineRunRead]:
    result = session.execute(
        select(models.PipelineRun)
        .where(models.PipelineRun.workspace == workspace)
        .order_by(models.PipelineRun.created_at.desc())
        .limit(20)
    )
    return [schemas.PipelineRunRead.from_orm(run) for run in result.scalars().all()]


@router.post(
    "/workspaces/{workspace}/pipeline/trigger",
    response_model=schemas.PipelineRunRead,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["workspaces", "pipeline"],
)
async def trigger_pipeline_run(
    workspace: str, session: Session = Depends(get_session)
) -> schemas.PipelineRunRead:
    run = models.PipelineRun(
        workspace=workspace,
        task_id=str(uuid4()),
        status=models.PipelineRunStatus.QUEUED,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    await pipeline_status_broadcaster.publish(workspace, _serialize_run_event(run))
    record_audit_event(
        "workspace.pipeline.trigger",
        workspace=workspace,
        pipeline_run_id=run.id,
    )
    asyncio.create_task(_execute_pipeline_run(run.id, workspace))
    return schemas.PipelineRunRead.from_orm(run)


@router.get(
    "/workspaces/{workspace}/dashboard",
    response_model=schemas.WorkspaceDashboardSnapshot,
    tags=["workspaces"],
)
def workspace_dashboard(
    workspace: str, session: Session = Depends(get_session)
) -> schemas.WorkspaceDashboardSnapshot:
    sources = session.execute(
        select(models.WorkspaceSource)
        .where(models.WorkspaceSource.workspace == workspace)
        .order_by(models.WorkspaceSource.name)
    ).scalars().all()
    proxies = session.execute(
        select(models.WorkspaceProxy)
        .where(models.WorkspaceProxy.workspace == workspace)
        .order_by(models.WorkspaceProxy.name)
    ).scalars().all()
    channels = session.execute(
        select(models.WorkspaceTelegramChannel)
        .where(models.WorkspaceTelegramChannel.workspace == workspace)
        .order_by(models.WorkspaceTelegramChannel.name)
    ).scalars().all()
    runs = session.execute(
        select(models.PipelineRun)
        .where(models.PipelineRun.workspace == workspace)
        .order_by(models.PipelineRun.created_at.desc())
        .limit(20)
    ).scalars().all()

    counts = schemas.WorkspaceDashboardCounts(
        sources=len(sources),
        proxies=len(proxies),
        telegram_channels=len(channels),
        pipeline_runs=len(runs),
    )

    return schemas.WorkspaceDashboardSnapshot(
        workspace=workspace,
        counts=counts,
        sources=[schemas.WorkspaceSourceRead.from_orm(source) for source in sources],
        proxies=[schemas.WorkspaceProxyRead.from_orm(proxy) for proxy in proxies],
        telegram_channels=[
            schemas.WorkspaceTelegramChannelRead.from_orm(channel) for channel in channels
        ],
        pipeline_runs=[schemas.PipelineRunRead.from_orm(run) for run in runs],
    )


@router.websocket("/workspaces/{workspace}/pipeline/status")
async def workspace_pipeline_status_stream(websocket: WebSocket, workspace: str) -> None:
    await websocket.accept()
    session = SessionLocal()
    queue = await pipeline_status_broadcaster.subscribe(workspace)

    try:
        runs = session.execute(
            select(models.PipelineRun)
            .where(models.PipelineRun.workspace == workspace)
            .order_by(models.PipelineRun.created_at.desc())
            .limit(20)
        ).scalars().all()
        await websocket.send_json(_snapshot_payload(workspace, runs))

        receiver = asyncio.create_task(websocket.receive_text())
        try:
            while True:
                producer = asyncio.create_task(queue.get())
                done, _ = await asyncio.wait(
                    {receiver, producer}, return_when=asyncio.FIRST_COMPLETED
                )
                if receiver in done:
                    producer.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await producer
                    break
                payload = producer.result()
                await websocket.send_json(payload)
        except WebSocketDisconnect:
            pass
        finally:
            receiver.cancel()
            with contextlib.suppress(Exception):
                await receiver
    finally:
        await pipeline_status_broadcaster.unsubscribe(workspace, queue)
        session.close()
main
