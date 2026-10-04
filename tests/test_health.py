from __future__ import annotations

from fastapi.testclient import TestClient

from app.core import health as health_module
from app.main import create_app


def test_verify_startup_dependencies_requires_readonly_write_block(monkeypatch) -> None:
    class FakeSession:
        def __init__(self, allow_write: bool) -> None:
            self.allow_write = allow_write

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, statement, parameters=None):
            sql = str(statement).lower()
            if sql.startswith("select 1"):
                return None
            if "insert into signups" in sql and not self.allow_write:
                raise PermissionError("read-only")
            return None

        def rollback(self):
            return None

    monkeypatch.setattr(health_module, "SessionLocal", lambda: FakeSession(allow_write=False))
    monkeypatch.setattr(health_module, "ReadOnlySessionLocal", lambda: FakeSession(allow_write=False))
    monkeypatch.setattr(health_module, "_ping_redis", lambda: None)
    health_module.verify_startup_dependencies()

    monkeypatch.setattr(health_module, "ReadOnlySessionLocal", lambda: FakeSession(allow_write=True))
    try:
        health_module.verify_startup_dependencies()
    except RuntimeError as exc:
        assert "read-only database role accepted a write" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when readonly role can write")


def test_health_endpoint_reports_service_status(monkeypatch) -> None:
    monkeypatch.setattr("app.main.init_db", lambda: None)
    monkeypatch.setattr("app.main.verify_startup_dependencies", lambda: None)
    monkeypatch.setattr("app.main.check_service_health", lambda: {"postgres": "ok", "readonly_postgres": "ok", "redis": "ok"})

    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "postgres": "ok", "readonly_postgres": "ok", "redis": "ok"}