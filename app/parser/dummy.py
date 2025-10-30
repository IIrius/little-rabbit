"""Built-in dummy parser used for smoke testing the framework."""
from __future__ import annotations

from collections.abc import Iterable

from .base import BaseParser, ParserRunResult, register_parser


@register_parser
class DummyParser(BaseParser):
    """Parser that emits deterministic payloads from configuration."""

    name = "dummy"

    def parse(self) -> ParserRunResult:
        urls_option = self.get_option("urls", [])
        if isinstance(urls_option, str):
            urls = [urls_option]
        elif isinstance(urls_option, Iterable):
            urls = [str(url) for url in urls_option]
        else:
            urls = []

        proxy = self.acquire_proxy()
        cookie_header = self.cookie_header()

        items: list[dict[str, object]] = []
        for index, url in enumerate(urls, start=1):
            url = str(url)
            user_agent = self.next_user_agent()
            title = None

            if self.context.settings.use_playwright and self.context.playwright:
                with self.render_page(url, user_agent=user_agent) as page:
                    title_fn = getattr(page, "title", None)
                    if callable(title_fn):
                        title = title_fn()

            items.append(
                {
                    "index": index,
                    "url": url,
                    "user_agent": user_agent,
                    "proxy": proxy,
                    "cookie_header": cookie_header,
                    "title": title,
                }
            )

        metadata = {
            "workspace": self.workspace,
            "source": self.source.name,
            "count": len(items),
        }
        return ParserRunResult(items=items, metadata=metadata)


__all__ = ["DummyParser"]
