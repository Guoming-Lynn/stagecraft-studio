"""Send the loopback Host the browser uses. TestClient's default host is testserver."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _loopback_host(monkeypatch: pytest.MonkeyPatch) -> None:
    original = TestClient.__init__

    def init_with_loopback(self: TestClient, *args: object, **kwargs: object) -> None:
        kwargs.setdefault("base_url", "http://127.0.0.1")
        original(self, *args, **kwargs)

    monkeypatch.setattr(TestClient, "__init__", init_with_loopback)
