"""Utilities for applying anti-detect techniques in parsers."""
from __future__ import annotations

from typing import Mapping, Sequence

_DEFAULT_USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_1) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:118.0) Gecko/20100101 Firefox/118.0",
)


class UserAgentRotator:
    """Deterministic rotator cycling through configured user agents."""

    def __init__(self, user_agents: Sequence[str] | None = None) -> None:
        sanitized = [
            str(agent).strip()
            for agent in user_agents or ()
            if agent is not None and str(agent).strip()
        ]
        if not sanitized:
            sanitized = list(_DEFAULT_USER_AGENTS)
        self._user_agents = tuple(sanitized)
        self._position = 0

    def next(self) -> str:
        agent = self._user_agents[self._position]
        self._position = (self._position + 1) % len(self._user_agents)
        return agent


class CookieJar:
    """Minimal cookie jar that supports header rendering."""

    def __init__(self, cookies: Mapping[str, str] | None = None) -> None:
        self._cookies: dict[str, str] = {}
        if cookies:
            for key, value in cookies.items():
                key_str = str(key).strip()
                if not key_str:
                    continue
                self._cookies[key_str] = str(value)

    def set(self, name: str, value: str) -> None:
        self._cookies[str(name)] = str(value)

    def as_dict(self) -> dict[str, str]:
        return dict(self._cookies)

    def header(self) -> str:
        if not self._cookies:
            return ""
        return "; ".join(f"{key}={value}" for key, value in self._cookies.items())


class AntiDetectToolkit:
    """Container for user-agent rotation and cookie management."""

    def __init__(
        self,
        user_agents: Sequence[str] | None = None,
        cookies: Mapping[str, str] | None = None,
    ) -> None:
        self._rotator = UserAgentRotator(user_agents)
        self._jar = CookieJar(cookies)

    def next_user_agent(self) -> str:
        return self._rotator.next()

    def cookies_dict(self) -> dict[str, str]:
        return self._jar.as_dict()

    def cookie_header(self) -> str:
        return self._jar.header()

    def update_cookie(self, name: str, value: str) -> None:
        self._jar.set(name, value)


__all__ = ["AntiDetectToolkit"]
