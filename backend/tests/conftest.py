from collections.abc import Generator
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from backend_app.main import app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app, base_url="https://testserver") as client:
        yield client
