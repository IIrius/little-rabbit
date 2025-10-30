"""Tests for the parser framework infrastructure."""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.models import (
    ProxyProtocol,
    SourceKind,
    WorkspaceParserConfig,
    WorkspaceProxy,
    WorkspaceSource,
)
from app.parser.playwright import (
    PlaywrightLaunchOptions,
    PlaywrightProvider,
    set_playwright_provider,
)
from app.parser.tasks import run_parser_job


class _StubPage:
    def __init__(self, title: str) -> None:
        self._title = title

    def title(self) -> str:
        return self._title


class _StubPlaywrightProvider(PlaywrightProvider):
    def __init__(self) -> None:
        self.calls: list[PlaywrightLaunchOptions] = []

        def _factory(options: PlaywrightLaunchOptions):
            self.calls.append(options)

            @contextmanager
            def _manager():
                yield _StubPage(title=f"title::{options.url}")

            return _manager()

        super().__init__(page_factory=_factory)


def _create_workspace_source(session: Session) -> WorkspaceSource:
    source = WorkspaceSource(
        workspace="alpha",
        name="dummy-source",
        kind=SourceKind.CUSTOM,
    )
    session.add(source)
    session.flush()
    return source


def test_dummy_parser_runs_via_celery(db_session: Session) -> None:
    source = _create_workspace_source(db_session)

    parser_config = WorkspaceParserConfig(
        source_id=source.id,
        parser_name="dummy",
        options={"urls": ["https://example.com/alpha", "https://example.com/bravo"]},
        user_agents=["Agent-A", "Agent-B"],
        cookies={"session": "abc123"},
        use_playwright=True,
    )
    db_session.add(parser_config)

    db_session.add(
        WorkspaceProxy(
            workspace="alpha",
            name="primary",
            protocol=ProxyProtocol.SOCKS5,
            address="socks5://127.0.0.1:1080",
        )
    )
    db_session.commit()

    provider = _StubPlaywrightProvider()
    set_playwright_provider(provider)

    try:
        result = run_parser_job.apply(args=("alpha", "dummy-source")).get()
    finally:
        set_playwright_provider(None)

    assert result["workspace"] == "alpha"
    assert result["source"] == "dummy-source"
    assert result["parser"] == "dummy"

    items = result["items"]
    assert len(items) == 2
    assert {item["title"] for item in items} == {
        "title::https://example.com/alpha",
        "title::https://example.com/bravo",
    }
    assert items[0]["user_agent"] == "Agent-A"
    assert items[1]["user_agent"] == "Agent-B"
    assert items[0]["proxy"] == "socks5://127.0.0.1:1080"
    assert provider.calls[0].user_agent == "Agent-A"
    assert provider.calls[0].proxy == "socks5://127.0.0.1:1080"
    assert provider.calls[0].cookies["session"] == "abc123"
    assert result["metadata"]["count"] == 2
