"""`wiki-query`: local hybrid search over one or more vaults.

Fuses vector search (LanceDB, semantic/paraphrase-friendly) with BM25
keyword search (fts.py, exact-term-friendly — proper nouns, jargon, code
identifiers) via Reciprocal Rank Fusion, the same approach QMD/tobi's qmd
use. Pure retrieval — prints matching chunks with their source note and
vault so a human (or the librarian skill) can read/cite them. Synthesis of
an answer from the results is the librarian skill's job, not this CLI's.
"""

from __future__ import annotations

import argparse
import sys

import lancedb

from wiki import config, fts, index
from wiki.embed import DEFAULT_MODEL, get_embedding

RRF_K = 60


def _rrf_merge(vector_hits: list[dict], fts_hits: list[dict], k: int = RRF_K) -> list[dict]:
    """Combine two best-first ranked lists into one, scoring each item by
    the sum of 1/(k + rank) over whichever list(s) it appears in.
    """
    scores: dict[str, float] = {}
    info: dict[str, dict] = {}
    sources: dict[str, set] = {}

    for label, ranked in (("vector", vector_hits), ("bm25", fts_hits)):
        for rank, item in enumerate(ranked, start=1):
            key = f"{item['vault']}::{item['id']}"
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            info.setdefault(key, item)
            sources.setdefault(key, set()).add(label)

    merged = []
    for key, score in scores.items():
        row = dict(info[key])
        row["rrf_score"] = score
        row["matched_via"] = sorted(sources[key])
        merged.append(row)

    merged.sort(key=lambda r: r["rrf_score"], reverse=True)
    return merged


def search(query_text: str, vault_names: list[str], k: int = 5, model: str = DEFAULT_MODEL) -> list[dict]:
    db = lancedb.connect(str(config.data_dir()))
    vector = get_embedding(query_text, model=model)
    pool_size = max(k * 4, 20)

    vector_hits: list[dict] = []
    fts_hits: list[dict] = []
    for name in vault_names:
        if name in db.table_names():
            for hit in db.open_table(name).search(vector).limit(pool_size).to_list():
                hit["vault"] = name
                vector_hits.append(hit)
        for hit in fts.search_fts(name, query_text, limit=pool_size):
            hit["vault"] = name
            fts_hits.append(hit)

    vector_hits.sort(key=lambda r: r.get("_distance", 0.0))
    fts_hits.sort(key=lambda r: r.get("score", 0.0))  # bm25(): more negative = better

    return _rrf_merge(vector_hits, fts_hits, k=RRF_K)[:k]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wiki-query", description="Hybrid (vector + BM25) search over wiki vaults.")
    parser.add_argument("query")
    parser.add_argument("--vault", help="Comma-separated vault name(s). Default: all registered vaults.")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args(argv)

    names = [n.strip() for n in args.vault.split(",")] if args.vault else list(config.load_vaults())

    try:
        results = search(args.query, names, k=args.k, model=args.model)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for name in names:
        stale = index.stale_notes(name)
        if stale:
            note_word = "note" if len(stale) == 1 else "notes"
            print(
                f"warning: {len(stale)} {note_word} in vault {name!r} changed since last index — "
                f"results may be stale. Run `uv run wiki-index --vault {name}` to refresh.",
                file=sys.stderr,
            )

    if not results:
        print("No matches. Has this vault been indexed yet? (wiki-index --vault NAME)")
        return 0

    for r in results:
        via = "+".join(r["matched_via"])
        print(f"[{r['vault']}] {r['path']} — {r['heading']}  (rrf {r['rrf_score']:.4f}, via {via})")
        snippet = r["text"].strip().replace("\n", " ")
        print(f"  {snippet[:200]}{'…' if len(snippet) > 200 else ''}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
