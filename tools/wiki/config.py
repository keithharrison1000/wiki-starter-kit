"""Loads and updates vaults.toml, the registry of vault (OKF bundle) roots.

Hand-rolled TOML read/write for this one narrow, fixed schema
(a list of [[vault]] tables) rather than pulling in a TOML-writing
dependency just for this.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VAULTS_TOML = REPO_ROOT / "vaults.toml"


@dataclass
class Vault:
    name: str
    path: Path
    sensitive: bool = False


def load_vaults() -> dict[str, Vault]:
    if not VAULTS_TOML.exists():
        return {}
    data = tomllib.loads(VAULTS_TOML.read_text(encoding="utf-8"))
    vaults = {}
    for entry in data.get("vault", []):
        name = entry["name"]
        path = Path(entry["path"]).expanduser()
        if not path.is_absolute():
            path = REPO_ROOT / path
        vaults[name] = Vault(
            name=name,
            path=path,
            sensitive=bool(entry.get("sensitive", False)),
        )
    return vaults


def save_vaults(vaults: dict[str, Vault]) -> None:
    lines = ["# Registry of wiki vaults (OKF bundles). Edit by hand or via wiki-new-vault.", ""]
    for v in sorted(vaults.values(), key=lambda v: v.name):
        lines.append("[[vault]]")
        lines.append(f'name = "{v.name}"')
        lines.append(f'path = "{v.path}"')
        lines.append(f"sensitive = {str(v.sensitive).lower()}")
        lines.append("")
    VAULTS_TOML.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def resolve_vault(name: str) -> Vault:
    vaults = load_vaults()
    if name not in vaults:
        available = ", ".join(sorted(vaults)) or "(none registered)"
        raise KeyError(f"No vault named {name!r} in vaults.toml. Available: {available}")
    return vaults[name]


def data_dir() -> Path:
    """Local, gitignored directory for per-vault vector indexes."""
    d = REPO_ROOT / "tools" / "wiki" / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d
