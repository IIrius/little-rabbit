from __future__ import annotations

from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_ROOT_APP_DIR = _PACKAGE_DIR.parents[1] / "app"

__path__ = [str(_PACKAGE_DIR)]
if _ROOT_APP_DIR != _PACKAGE_DIR and _ROOT_APP_DIR.exists():
    __path__.append(str(_ROOT_APP_DIR))

__all__ = []
