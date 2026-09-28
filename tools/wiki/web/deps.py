"""Access control for the read-only web app: which vaults it may ever serve.

This is the one gate the whole app depends on. `vaults.toml` already marks
some vaults `sensitive` (work, finance, ...); this module is the single
place that turns that flag into an enforced rule, applied per-request, not
just reflected in what the home page happens to link to.
"""

from __future__ import annotations

from fastapi import HTTPException

from wiki import config


def exposed_vaults() -> dict[str, config.Vault]:
    """Non-sensitive vaults, recomputed fresh on every call.

    Never cached at process start: vaults.toml can change while the server
    is running (e.g. `wiki-new-vault`), and the security property this app
    needs — never serve a sensitive vault — has to hold on every request
    regardless of when that request arrives relative to a registry change.
    """
    return {name: vault for name, vault in config.load_vaults().items() if not vault.sensitive}


def get_exposed_vault(vault: str) -> config.Vault:
    """FastAPI dependency (and a plain callable) gating every vault-scoped
    request. Raises 404 — never 403 — for both an unknown vault name and a
    registered-but-sensitive one, so the response carries no signal that
    would let someone distinguish "doesn't exist" from "exists, but hidden."

    Use via `Depends(get_exposed_vault)` on path-parameterized routes, and
    call it directly wherever a vault name arrives some other way (e.g. an
    HTML form field) — see the `POST /ask` handler for the case that matters.
    """
    vaults = exposed_vaults()
    if vault not in vaults:
        raise HTTPException(status_code=404, detail="Vault not found")
    return vaults[vault]
