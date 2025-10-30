from collections.abc import Generator
from importlib import invalidate_caches
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
sys.modules.pop("app", None)
invalidate_caches()

from app.main import app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app, base_url="https://testserver") as client:
        yield client
