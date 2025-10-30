from collections.abc import Generator
from importlib import import_module, invalidate_caches
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        sys.modules.pop(module_name, None)
invalidate_caches()

backend_main = import_module("app.main")
assert (BACKEND_ROOT / "app" / "main.py").resolve() == Path(backend_main.__file__).resolve()
app = backend_main.app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app, base_url="https://testserver") as client:
        yield client
