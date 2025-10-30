"""Parser framework exports and default registrations."""
from __future__ import annotations

from app.parser.anti_detect import AntiDetectToolkit
from app.parser.base import (
    BaseParser,
    ParserContext,
    ParserError,
    ParserNotRegisteredError,
    ParserRegistry,
    ParserRunResult,
    ParserSettings,
    register_parser,
)
from app.parser.playwright import (
    PlaywrightLaunchOptions,
    PlaywrightProvider,
    get_playwright_provider,
    set_playwright_provider,
)
from app.parser.proxy import RoundRobinSocks5ProxyManager, Socks5ProxyManager

# Ensure built-in parsers register with the framework on import.
from app.parser import dummy as _builtin_dummy  # noqa: F401

__all__ = [
    "AntiDetectToolkit",
    "BaseParser",
    "ParserContext",
    "ParserError",
    "ParserNotRegisteredError",
    "ParserRegistry",
    "ParserRunResult",
    "ParserSettings",
    "register_parser",
    "PlaywrightLaunchOptions",
    "PlaywrightProvider",
    "get_playwright_provider",
    "set_playwright_provider",
    "RoundRobinSocks5ProxyManager",
    "Socks5ProxyManager",
]
