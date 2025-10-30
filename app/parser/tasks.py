"""Celery tasks for orchestrating parser execution."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import (
    ProxyProtocol,
    WorkspaceParserConfig,
    WorkspaceProxy,
    WorkspaceSource,
)
from app.observability.logging import get_logger
from app.parser import (
    AntiDetectToolkit,
    ParserContext,
    ParserRegistry,
    ParserRunResult,
    ParserSettings,
    get_playwright_provider,
)
from app.parser.proxy import RoundRobinSocks5ProxyManager

logger = get_logger("parser.tasks")


@celery_app.task(bind=True, name="app.parser.tasks.run_parser_job")
def run_parser_job(self, workspace: str, source_name: str) -> dict[str, Any]:
    """Execute the configured parser for the given workspace source."""

    session: Session = SessionLocal()
    parser_settings: ParserSettings | None = None
    run_result: ParserRunResult | None = None

    try:
        source = session.execute(
            select(WorkspaceSource).where(
                WorkspaceSource.workspace == workspace,
                WorkspaceSource.name == source_name,
            )
        ).scalar_one_or_none()
        if source is None:
            raise ValueError(f"Unknown source '{source_name}' for workspace '{workspace}'")
        if not source.is_active:
            logger.info(
                "source inactive; skipping parser execution",
                extra={"workspace": workspace, "source": source_name},
            )
            return {
                "workspace": workspace,
                "source": source_name,
                "parser": None,
                "items": [],
                "metadata": {"inactive": True},
            }

        parser_config = session.execute(
            select(WorkspaceParserConfig).where(
                WorkspaceParserConfig.source_id == source.id
            )
        ).scalar_one_or_none()
        if parser_config is None:
            raise ValueError(
                f"No parser configuration found for source '{source_name}' "
                f"in workspace '{workspace}'"
            )

        parser_settings = ParserSettings(
            parser_name=parser_config.parser_name,
            options=parser_config.options or {},
            user_agents=list(parser_config.user_agents or []),
            cookies=dict(parser_config.cookies or {}),
            use_playwright=bool(parser_config.use_playwright),
        )

        parser_cls = ParserRegistry.get(parser_settings.parser_name)

        proxies = session.execute(
            select(WorkspaceProxy.address)
            .where(
                WorkspaceProxy.workspace == workspace,
                WorkspaceProxy.protocol == ProxyProtocol.SOCKS5,
                WorkspaceProxy.is_active.is_(True),
            )
            .order_by(WorkspaceProxy.id)
        ).scalars().all()
        proxy_manager = (
            RoundRobinSocks5ProxyManager(proxies) if proxies else None
        )

        anti_detect = AntiDetectToolkit(
            user_agents=parser_settings.user_agents,
            cookies=parser_settings.cookies,
        )
        playwright_provider = (
            get_playwright_provider() if parser_settings.use_playwright else None
        )

        context = ParserContext(
            workspace=workspace,
            source=source,
            settings=parser_settings,
            session=session,
            anti_detect=anti_detect,
            proxy_manager=proxy_manager,
            playwright=playwright_provider,
        )

        parser = parser_cls(context)
        run_result = parser.run()
        session.commit()
    except Exception:
        session.rollback()
        logger.exception(
            "parser execution failed",
            extra={"workspace": workspace, "source": source_name},
        )
        raise
    finally:
        session.close()

    logger.info(
        "parser execution completed",
        extra={
            "workspace": workspace,
            "source": source_name,
            "parser": parser_settings.parser_name if parser_settings else None,
            "items": len(run_result.items) if run_result else 0,
        },
    )
    return {
        "workspace": workspace,
        "source": source_name,
        "parser": parser_settings.parser_name if parser_settings else None,
        "items": run_result.items if run_result else [],
        "metadata": run_result.metadata if run_result else {},
    }


__all__ = ["run_parser_job"]
