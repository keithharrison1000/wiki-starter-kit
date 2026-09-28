"""Smoke tests for the one place a regression in the web app has real
(not cosmetic) cost: never serving a vault marked `sensitive`.

Uses a fabricated vault registry (monkeypatched) rather than the real
vaults.toml, so these tests are deterministic and don't depend on whatever
external vaults happen to be registered on a given machine.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from wiki import config
from wiki.web import deps
from wiki.web.app import app

FAKE_VAULTS = {
    "open": config.Vault(name="open", path=Path("/tmp/does-not-need-to-exist/open"), sensitive=False),
    "secret": config.Vault(name="secret", path=Path("/tmp/does-not-need-to-exist/secret"), sensitive=True),
}


@pytest.fixture(autouse=True)
def fake_registry(monkeypatch):
    monkeypatch.setattr(config, "load_vaults", lambda: dict(FAKE_VAULTS))


def test_exposed_vaults_excludes_sensitive():
    exposed = deps.exposed_vaults()
    assert "open" in exposed
    assert "secret" not in exposed


def test_get_exposed_vault_returns_non_sensitive_vault():
    assert deps.get_exposed_vault("open") is FAKE_VAULTS["open"]


def test_get_exposed_vault_404s_for_sensitive_name_even_when_it_exists():
    with pytest.raises(HTTPException) as exc_info:
        deps.get_exposed_vault("secret")
    assert exc_info.value.status_code == 404


def test_get_exposed_vault_404s_identically_for_unknown_name():
    with pytest.raises(HTTPException) as sensitive_exc:
        deps.get_exposed_vault("secret")

    with pytest.raises(HTTPException) as unknown_exc:
        deps.get_exposed_vault("no-such-vault")

    # Same status and same detail message — nothing distinguishes "exists,
    # but sensitive" from "doesn't exist at all."
    assert sensitive_exc.value.status_code == unknown_exc.value.status_code == 404
    assert sensitive_exc.value.detail == unknown_exc.value.detail


def test_sensitive_vault_route_404s_end_to_end():
    client = TestClient(app)
    sensitive_resp = client.get("/secret/")
    unknown_resp = client.get("/no-such-vault/")
    assert sensitive_resp.status_code == unknown_resp.status_code == 404

    notes_resp = client.get("/secret/notes/anything.md")
    assert notes_resp.status_code == 404


def test_ask_rejects_sensitive_vault_posted_directly_bypassing_the_ui():
    client = TestClient(app)
    resp = client.post("/ask", data={"q": "anything", "scope": "current", "vault": "secret"})
    assert resp.status_code == 404
