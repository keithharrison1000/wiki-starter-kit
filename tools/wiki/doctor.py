"""`wiki-doctor`: environment/setup health check.

Distinct from `wiki-lint`, which checks vault *content* health (orphans,
broken links, raw-source integrity). This checks whether the tooling
itself is correctly set up: dependencies installed, Ollama reachable with
the embedding model pulled, every registered vault resolvable as a valid
bundle — the kind of thing that otherwise only surfaces as a confusing
error partway through a `wiki-ingest`/`wiki-index`/`wiki-query` run.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import subprocess
import sys
from importlib import import_module

from wiki import config
from wiki.embed import DEFAULT_MODEL

Check = tuple[str, str, str]  # (status, label, detail) — status: ok | warn | fail


def _importable(module_name: str) -> bool:
    try:
        import_module(module_name)
    except ImportError:
        return False
    return True


def run_checks() -> list[Check]:
    checks: list[Check] = []

    checks.append(("ok", "Python", sys.version.split()[0]))

    core = {
        "yaml": "pyyaml",
        "lancedb": "lancedb",
        "ollama": "ollama",
        "fitz": "pymupdf",
        "pymupdf4llm": "pymupdf4llm",
        "docling": "docling",
    }
    missing_core = [pkg for mod, pkg in core.items() if not _importable(mod)]
    if missing_core:
        checks.append(("fail", "Core dependencies", f"missing {', '.join(missing_core)} — run `uv sync`"))
    else:
        checks.append(("ok", "Core dependencies", "installed"))

    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        checks.append(("ok", "SQLite FTS5 (BM25 search)", "available"))
    except sqlite3.OperationalError:
        checks.append(("fail", "SQLite FTS5 (BM25 search)", "not compiled into this Python's sqlite3"))

    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        checks.append(
            ("fail", "Ollama", f"not installed — see https://ollama.com, then `ollama pull {DEFAULT_MODEL}`")
        )
    else:
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5, check=False)
        except (subprocess.TimeoutExpired, OSError) as exc:
            checks.append(("fail", "Ollama", f"installed but not reachable: {exc}"))
        else:
            if result.returncode != 0:
                checks.append(("fail", "Ollama", "installed but not running — start the app or `ollama serve`"))
            elif DEFAULT_MODEL not in result.stdout:
                checks.append(("warn", "Ollama", f"running, but not pulled — run `ollama pull {DEFAULT_MODEL}`"))
            else:
                checks.append(("ok", "Ollama", f"running, {DEFAULT_MODEL!r} available"))

    vaults = config.load_vaults()
    if not vaults:
        checks.append(("warn", "Registered vaults", "none in vaults.toml"))
    for name, vault in sorted(vaults.items()):
        if not vault.path.exists():
            checks.append(("fail", f"Vault {name!r}", f"path does not exist: {vault.path}"))
            continue
        if not (vault.path / "index.md").exists() or not (vault.path / "log.md").exists():
            checks.append(("fail", f"Vault {name!r}", "missing index.md/log.md — not a valid bundle"))
            continue
        indexed = (config.data_dir() / f"{name}.lance").exists()
        checks.append(
            (
                "ok" if indexed else "warn",
                f"Vault {name!r}",
                "valid bundle, indexed" if indexed else "valid bundle, not yet indexed — run `wiki-index`",
            )
        )

    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wiki-doctor", description="Check the wiki tooling's environment/setup health.")
    parser.parse_args(argv)

    checks = run_checks()
    for status, label, detail in checks:
        print(f"[{status}] {label} — {detail}")

    return 1 if any(status == "fail" for status, _, _ in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
