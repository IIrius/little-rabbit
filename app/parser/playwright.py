"""Playwright integration scaffolding for the parser framework."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from typing import Callable, ContextManager, Mapping
from urllib.parse import urlparse

PlaywrightPageFactory = Callable[["PlaywrightLaunchOptions"], ContextManager[object]]


@dataclass(frozen=True)
class PlaywrightLaunchOptions:
    """Parameters passed to launch a Playwright page."""

    url: str
    user_agent: str
    proxy: str | None = None
    cookies: Mapping[str, str] | None = None


class PlaywrightProvider:
    """Wrapper around a page factory to decouple from Playwright internals."""

    def __init__(self, page_factory: PlaywrightPageFactory | None = None) -> None:
        self._page_factory = page_factory or _default_page_factory

    def page(self, options: PlaywrightLaunchOptions) -> ContextManager[object]:
        return self._page_factory(options)


def _default_page_factory(options: PlaywrightLaunchOptions) -> ContextManager[object]:
    try:  # pragma: no cover - optional dependency, exercised via mocks
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - missing dependency path
        raise RuntimeError("Playwright is not installed") from exc

    @contextmanager
    def _launch() -> ContextManager[object]:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                proxy=_build_proxy(options.proxy),
            )
            context = browser.new_context(user_agent=options.user_agent)
            if options.cookies:
                context.add_cookies(_format_cookies(options.url, options.cookies))
            page = context.new_page()
            page.goto(options.url)
            try:
                yield page
            finally:
                context.close()
                browser.close()

    return _launch()


def _build_proxy(proxy: str | None) -> dict[str, str] | None:
    if not proxy:
        return None
    return {"server": proxy}


def _format_cookies(url: str, cookies: Mapping[str, str]) -> list[dict[str, str]]:
    parsed = urlparse(url)
    domain = parsed.hostname or ""
    path = parsed.path or "/"
    if not path.startswith("/"):
        path = f"/{path}"
    formatted: list[dict[str, str]] = []
    for name, value in cookies.items():
        formatted.append(
            {
                "name": str(name),
                "value": str(value),
                "domain": domain,
                "path": path,
            }
        )
    return formatted


_provider: PlaywrightProvider | None = None
_provider_lock = Lock()


def get_playwright_provider() -> PlaywrightProvider:
    global _provider
    if _provider is not None:
        return _provider

    with _provider_lock:
        if _provider is None:
            _provider = PlaywrightProvider()
    return _provider


def set_playwright_provider(provider: PlaywrightProvider | None) -> None:
    global _provider
    with _provider_lock:
        _provider = provider


__all__ = [
    "PlaywrightLaunchOptions",
    "PlaywrightProvider",
    "get_playwright_provider",
    "set_playwright_provider",
]
