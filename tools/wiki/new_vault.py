"""`wiki-new-vault`: scaffold a new knowledge base as an OKF bundle (or
register an existing external one, e.g. the sensitive work vault) in
vaults.toml.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from wiki import config, okf


def _copy_conventions(path: Path) -> None:
    """Copy the canonical conventions.md into a freshly scaffolded vault.
    Vaults can't link to each other, so this is a real copy, not a link —
    the librarian keeps every vault's copy in sync (see SKILL.md)
    whenever vaults/general/conventions.md, the canonical source, changes.
    """
    canonical = config.REPO_ROOT / "vaults" / "general" / "conventions.md"
    if canonical.exists():
        shutil.copy2(canonical, path / "conventions.md")


def new_vault(name: str, external_path: str | None = None, sensitive: bool = False) -> Path:
    vaults = config.load_vaults()
    if name in vaults:
        raise ValueError(f"Vault {name!r} is already registered in vaults.toml")

    if external_path:
        path = Path(external_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"External vault path does not exist: {path}")
        if not (path / "index.md").exists():
            okf.init_bundle(path)
            _copy_conventions(path)
            okf.write_index(path, is_root=True)
    else:
        path = config.REPO_ROOT / "vaults" / name
        if path.exists():
            raise FileExistsError(f"{path} already exists")
        okf.init_bundle(path)
        (path / "inbox").mkdir(exist_ok=True)
        (path / "raw").mkdir(exist_ok=True)
        _copy_conventions(path)
        okf.write_index(path, is_root=True)

    vaults[name] = config.Vault(name=name, path=path, sensitive=sensitive)
    config.save_vaults(vaults)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wiki-new-vault", description="Scaffold or register a new vault (OKF bundle)."
    )
    parser.add_argument("name")
    parser.add_argument("--external", help="Path to an existing folder outside vaults/ to register instead of scaffolding a new one.")
    parser.add_argument("--sensitive", action="store_true", help="Mark this vault as sensitive (e.g. never push to a shared remote).")
    args = parser.parse_args(argv)

    try:
        path = new_vault(args.name, external_path=args.external, sensitive=args.sensitive)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Registered vault {args.name!r} at {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
