"""Base abstractions for the parser framework."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, Iterator, Mapping, Type

from sqlalchemy.orm import Session

from app.models import WorkspaceSource
from app.observability.logging import get_logger

from .anti_detect import AntiDetectToolkit
from .playwright import PlaywrightLaunchOptions, PlaywrightProvider
from .proxy import Socks5ProxyManager


@dataclass(frozen=True)
class ParserSettings:
    """Configuration payload associated with a parser."""

    parser_name: str
    options: Dict[str, Any] = field(default_factory=dict)
    user_agents: list[str] = field(default_factory=list)
    cookies: Dict[str, str] = field(default_factory=dict)
    use_playwright: bool = False

    def option(self, key: str, default: Any = None) -> Any:
        return self.options.get(key, default)


@dataclass(frozen=True)
class ParserContext:
    """Runtime context made available to parser implementations."""

    workspace: str
    source: WorkspaceSource
    settings: ParserSettings
    session: Session
    anti_detect: AntiDetectToolkit
    proxy_manager: Socks5ProxyManager | None = None
    playwright: PlaywrightProvider | None = None


@dataclass
class ParserRunResult:
    """Result of executing a parser."""

    items: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ParserError(RuntimeError):
    """Raised when a parser encounters a fatal execution error."""


class ParserNotRegisteredError(LookupError):
    """Raised when a requested parser has not been registered."""

    def __init__(self, parser_name: str) -> None:
        super().__init__(f"Parser '{parser_name}' is not registered")
        self.parser_name = parser_name


class ParserRegistry:
    """Global registry of available parser implementations."""

    _registry: Dict[str, Type["BaseParser"]] = {}

    @classmethod
    def register(cls, parser_cls: Type["BaseParser"]) -> Type["BaseParser"]:
        name = getattr(parser_cls, "name", None)
        if not name:
            raise ValueError("Registered parsers must define a non-empty 'name' attribute")
        if name in cls._registry and cls._registry[name] is not parser_cls:
            raise ValueError(f"Parser '{name}' is already registered")
        cls._registry[name] = parser_cls
        return parser_cls

    @classmethod
    def get(cls, name: str) -> Type["BaseParser"]:
        try:
            return cls._registry[name]
        except KeyError as exc:
            raise ParserNotRegisteredError(name) from exc

    @classmethod
    def list(cls) -> list[str]:
        return sorted(cls._registry.keys())


def register_parser(parser_cls: Type["BaseParser"]) -> Type["BaseParser"]:
    """Decorator for registering :class:`BaseParser` implementations."""

    return ParserRegistry.register(parser_cls)


class BaseParser:
    """Abstract base class for all parsers."""

    name: ClassVar[str]

    def __init__(self, context: ParserContext) -> None:
        self.context = context
        self.logger = get_logger(f"parsers.{self.name}")
        self._active_proxy: str | None = None

    @property
    def workspace(self) -> str:
        return self.context.workspace

    @property
    def source(self) -> WorkspaceSource:
        return self.context.source

    @property
    def session(self) -> Session:
        return self.context.session

    def get_option(self, key: str, default: Any = None) -> Any:
        return self.context.settings.option(key, default)

    def next_user_agent(self) -> str:
        return self.context.anti_detect.next_user_agent()

    def cookies(self) -> dict[str, str]:
        return self.context.anti_detect.cookies_dict()

    def cookie_header(self) -> str:
        return self.context.anti_detect.cookie_header()

    def acquire_proxy(self) -> str | None:
        if self._active_proxy is not None:
            return self._active_proxy
        manager = self.context.proxy_manager
        if manager is None:
            return None
        proxy = manager.acquire()
        self._active_proxy = proxy
        return proxy

    def release_proxy(self, success: bool = True) -> None:
        if self._active_proxy is None:
            return
        manager = self.context.proxy_manager
        if manager is not None and self._active_proxy is not None:
            manager.release(self._active_proxy, success)
        self._active_proxy = None

    @contextmanager
    def render_page(
        self,
        url: str,
        *,
        user_agent: str | None = None,
        cookies: Mapping[str, str] | None = None,
    ) -> Iterator[Any]:
        """Get a Playwright page for the provided URL."""

        provider = self.context.playwright
        if provider is None:
            raise ParserError("Playwright provider is not configured for this parser")

        resolved_user_agent = user_agent or self.context.anti_detect.next_user_agent()
        resolved_cookies = dict(cookies or self.context.anti_detect.cookies_dict())

        options = PlaywrightLaunchOptions(
            url=url,
            user_agent=resolved_user_agent,
            proxy=self.acquire_proxy(),
            cookies=resolved_cookies,
        )

        try:
            with provider.page(options) as page:
                yield page
        except Exception:
            self.release_proxy(success=False)
            raise

    def run(self) -> ParserRunResult:
        try:
            result = self.parse()
        except Exception:
            self.release_proxy(success=False)
            raise
        self.release_proxy(success=True)
        return result

    def parse(self) -> ParserRunResult:  # pragma: no cover - abstract method
        raise NotImplementedError


__all__ = [
    "BaseParser",
    "ParserContext",
    "ParserError",
    "ParserRegistry",
    "ParserRunResult",
    "ParserSettings",
    "ParserNotRegisteredError",
    "register_parser",
]
