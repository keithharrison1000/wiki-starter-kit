"""`wiki-refresh`: regenerate index.md and optionally append a log.md entry
for a vault, after notes were added/edited/removed directly (e.g. by the
librarian skill writing files rather than going through wiki-ingest).
"""

from __future__ import annotations

import argparse
import sys

from wiki import config, okf


def refresh(vault_name: str, log_message: str | None = None, log_kind: str = "Update") -> None:
    vault = config.resolve_vault(vault_name)

    # Regenerate index.md for the root, every subdirectory that has one
    # already (even if it's now empty of concepts — e.g. its last file
    # just moved elsewhere during triage, which would otherwise leave a
    # stale listing behind), and every subdirectory that currently
    # contains concept files.
    seen_dirs = {vault.path}
    okf.write_index(vault.path, is_root=True)

    for index_path in vault.path.rglob("index.md"):
        parent = index_path.parent
        if parent not in seen_dirs:
            okf.write_index(parent, is_root=False)
            seen_dirs.add(parent)

    for path, _ in okf.iter_concepts(vault.path):
        parent = path.parent
        if parent not in seen_dirs:
            okf.write_index(parent, is_root=False)
            seen_dirs.add(parent)

    if log_message:
        okf.append_log(vault.path, log_message, kind=log_kind)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wiki-refresh", description="Regenerate index.md / append to log.md for a vault."
    )
    parser.add_argument("--vault", required=True)
    parser.add_argument("--log", dest="log_message", help="Log entry to append to log.md.")
    parser.add_argument("--kind", default="Update", help="Log entry kind (Update/Creation/Deprecation).")
    args = parser.parse_args(argv)

    try:
        refresh(args.vault, log_message=args.log_message, log_kind=args.kind)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Refreshed index.md for vault {args.vault!r}" + (" and appended to log.md." if args.log_message else "."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
