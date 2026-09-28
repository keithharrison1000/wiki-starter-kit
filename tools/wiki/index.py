"""`wiki-index`: build/update a vault's local hybrid search index.

Builds two indexes per vault under tools/wiki/data/ (gitignored): a
LanceDB vector index (embeddings via Ollama) and a SQLite FTS5 keyword
index (fts.py), fused at query time in query.py. Notes whose file mtime
hasn't changed since the last run are reused from the existing table
rather than re-embedded, unless --rebuild is passed; the FTS5 table is
cheap enough to always rebuild in full from the resulting row set.
"""

from __future__ import annotations

import argparse
import sys

import lancedb

from wiki import chunk, config, fts, okf
from wiki.embed import DEFAULT_MODEL, get_embedding


def build_index(vault_name: str, rebuild: bool = False, model: str = DEFAULT_MODEL) -> int:
    vault = config.resolve_vault(vault_name)
    db = lancedb.connect(str(config.data_dir()))

    existing_by_path: dict[str, list[dict]] = {}
    if not rebuild and vault_name in db.table_names():
        table = db.open_table(vault_name)
        for row in table.to_arrow().to_pylist():
            existing_by_path.setdefault(row["path"], []).append(row)

    rows: list[dict] = []
    for path, concept in okf.iter_concepts(vault.path):
        rel_path = str(path.relative_to(vault.path))
        mtime = path.stat().st_mtime
        cached = existing_by_path.get(rel_path)
        if cached and cached[0]["mtime"] == mtime:
            rows.extend(cached)
            continue
        for i, ch in enumerate(chunk.chunk_body(concept.body)):
            vector = get_embedding(ch.text, model=model)
            rows.append(
                {
                    "id": f"{rel_path}#{i}",
                    "path": rel_path,
                    "title": concept.title or path.stem,
                    "heading": ch.heading_path,
                    "text": ch.text,
                    "mtime": mtime,
                    "vector": vector,
                }
            )

    if not rows:
        raise RuntimeError(f"No concepts found in vault {vault_name!r} at {vault.path}")

    db.create_table(vault_name, data=rows, mode="overwrite")
    fts.build_fts_index(vault_name, rows)
    return len(rows)


def stale_notes(vault_name: str) -> list[str]:
    """Relative paths of notes whose content may not be reflected in the
    current index: new since last index, edited (mtime changed) since last
    index, or indexed but since deleted. Returns [] for an unregistered
    vault name or one that hasn't been indexed at all — those are reported
    elsewhere (as "no matches" / "no such vault"), not as staleness.
    """
    try:
        vault = config.resolve_vault(vault_name)
    except KeyError:
        return []

    db = lancedb.connect(str(config.data_dir()))
    if vault_name not in db.table_names():
        return []

    indexed_mtime: dict[str, float] = {
        row["path"]: row["mtime"] for row in db.open_table(vault_name).to_arrow().to_pylist()
    }

    current_paths: set[str] = set()
    stale: list[str] = []
    for path, _ in okf.iter_concepts(vault.path):
        rel_path = str(path.relative_to(vault.path))
        current_paths.add(rel_path)
        mtime = path.stat().st_mtime
        if rel_path not in indexed_mtime or indexed_mtime[rel_path] != mtime:
            stale.append(rel_path)

    stale.extend(sorted(set(indexed_mtime) - current_paths))
    return stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wiki-index", description="Build/update a vault's local semantic search index."
    )
    parser.add_argument("--vault", help="Comma-separated vault name(s). Default: all registered vaults.")
    parser.add_argument("--rebuild", action="store_true", help="Recompute embeddings for every note.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args(argv)

    names = [n.strip() for n in args.vault.split(",")] if args.vault else list(config.load_vaults())
    if not names:
        print("No vaults registered in vaults.toml.", file=sys.stderr)
        return 1

    for name in names:
        try:
            count = build_index(name, rebuild=args.rebuild, model=args.model)
        except Exception as exc:
            print(f"error indexing {name!r}: {exc}", file=sys.stderr)
            return 1
        print(f"Indexed {count} chunk(s) for vault {name!r}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
