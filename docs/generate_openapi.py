"""Utility to generate an OpenAPI document for the service."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure application package is importable when running from this directory
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402


def main() -> None:
    settings = get_settings()
    openapi_schema = app.openapi()

    output_path = Path(settings.docs_output_path)
    if not output_path.is_absolute():
        output_path = Path(__file__).resolve().parents[1] / output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(openapi_schema, indent=2))
    print(f"OpenAPI schema written to {output_path}")


if __name__ == "__main__":
    main()
