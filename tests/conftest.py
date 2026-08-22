import pytest


@pytest.fixture(autouse=True)
def allow_demo_mode(monkeypatch):
    monkeypatch.setenv("ALLOW_DEMO_MODE", "true")
