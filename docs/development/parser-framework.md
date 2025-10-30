# Parser framework

This document describes the modular parser subsystem that powers source-specific
extraction workflows. It covers the building blocks that parsers interact with,
how Celery orchestrates execution, and the guardrails that keep traffic
indistinguishable from regular users.

## Overview

Parsers turn workspace sources into structured payloads. Each active source has
an accompanying database record in `workspace_parser_configs` that specifies the
parser implementation, runtime options, and anti-detect preferences. Celery
entrances the parser via `app.parser.tasks.run_parser_job`, so invoking the
framework is as simple as scheduling that task with a workspace and source name.

```
run_parser_job.delay("workspace-id", "source-name")
```

The task loads the source configuration, builds the parser context, and dispatches
the registered parser. Results are returned as a dictionary containing the items
and parser metadata, making it easy to fan the output into downstream systems.

## BaseParser contract

All parsers inherit from `app.parser.base.BaseParser`. Concrete classes must
provide a unique `name` attribute and implement the `parse()` method, returning a
`ParserRunResult`.

```python
from app.parser.base import BaseParser, ParserRunResult, register_parser

@register_parser
class ExampleParser(BaseParser):
    name = "example"

    def parse(self) -> ParserRunResult:
        # obtain configuration values
        base_url = self.get_option("base_url")

        # rotate user agents and acquire proxies
        proxy = self.acquire_proxy()
        user_agent = self.next_user_agent()

        # drive Playwright if desired
        if self.context.settings.use_playwright and self.context.playwright:
            with self.render_page(base_url, user_agent=user_agent) as page:
                headline = page.title()
        else:
            headline = "offline"

        # assemble results
        items = [{"url": base_url, "headline": headline, "proxy": proxy}]
        metadata = {"workspace": self.workspace, "source": self.source.name}
        return ParserRunResult(items=items, metadata=metadata)
```

### Helper methods

`BaseParser` exposes several helpers:

- `get_option(key, default=None)` – read parser-specific configuration.
- `next_user_agent()` – rotate through the configured user agent pool.
- `cookie_header()` / `cookies()` – access anti-detect cookies.
- `acquire_proxy()` / `release_proxy()` – manage SOCKS5 proxies.
- `render_page(url, *, user_agent=None, cookies=None)` – launch a Playwright
  page with the current anti-detect profile.

The base class automatically releases proxies after `parse()` completes and will
propagate exceptions with the proxy marked as failed.

## Playwright integration scaffold

`PlaywrightProvider` wraps Playwright's `sync_playwright()` entrypoint. The
framework exposes `get_playwright_provider()` / `set_playwright_provider()` so
that tests and runtime environments can inject custom providers. When enabled
via `use_playwright=True` in the database configuration, parsers receive a
provider instance through their context and can call `render_page()` to work
with fully-rendered pages.

Tests mock the provider by supplying a custom page factory, avoiding the need for
Playwright binaries or browser downloads during CI runs.

## SOCKS5 proxies

`RoundRobinSocks5ProxyManager` reads active SOCKS5 proxies from the
`workspace_proxies` table and distributes them round-robin. The base parser
tracks the currently assigned proxy and releases it after execution, allowing
future strategies (pool exhaustion, health checks, etc.) to slot in without code
changes in parser implementations.

## Anti-detect toolkit

The framework rotates user agents and manages cookies through
`AntiDetectToolkit`. Parsers can request the next rotation at any point and can
update cookies if they persist session state. The toolkit also exports cookie
headers so HTTP clients outside of Playwright can reuse the configuration.

## Database configuration

Each `WorkspaceSource` may own exactly one `WorkspaceParserConfig` record. The
schema stores:

- `parser_name` – registry key for the implementation.
- `options` – arbitrary JSON options passed to the parser.
- `user_agents` – list of user agents for rotation.
- `cookies` – name/value pairs applied to outbound requests.
- `use_playwright` – opt-in flag for Playwright orchestration.

The example dummy parser demonstrates the plumbing and is used by the automated
tests to assert Celery integration end-to-end. Extending the system is a matter
of implementing a new parser class, registering it with `@register_parser`, and
creating a `WorkspaceParserConfig` entry that references it.
