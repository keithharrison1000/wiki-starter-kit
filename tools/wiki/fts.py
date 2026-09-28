"""SQLite FTS5 (BM25) full-text index — the keyword-search half of the
hybrid retrieval pipeline, fused with the LanceDB vector index (index.py/
query.py) via Reciprocal Rank Fusion. No extra dependency: FTS5 ships in
the stdlib sqlite3 module.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from wiki import config

# FTS5's tokenizers don't filter stopwords. Left in, a natural-language query
# like "how do I make my notes discoverable again" OR-matches on "how"/"do"/
# "my"/"again" as readily as on the words that actually carry meaning, which
# makes near enough every chunk register a spurious BM25 hit. Dropped instead.
_STOPWORDS = {
    "a", "about", "after", "again", "all", "an", "and", "any", "are", "as", "at",
    "be", "been", "but", "by", "can", "did", "do", "does", "doing", "down", "for",
    "from", "had", "has", "have", "how", "i", "if", "in", "into", "is", "it", "its",
    "just", "me", "my", "no", "not", "of", "on", "or", "our", "out", "over", "own",
    "so", "some", "than", "that", "the", "their", "them", "then", "there", "this",
    "to", "up", "was", "we", "were", "what", "when", "where", "which", "who", "why",
    "will", "with", "you", "your",
}


def fts_path(vault_name: str) -> Path:
    return config.data_dir() / f"{vault_name}.sqlite"


def build_fts_index(vault_name: str, rows: list[dict]) -> None:
    """Rebuild the FTS5 table wholesale from the same chunk rows used to
    build the vector index. BM25 needs no embeddings, so this is cheap
    enough to always do in full rather than caching incrementally.

    Uses the porter stemmer so e.g. a query for "refreshing" still matches
    text containing "refresh".
    """
    path = fts_path(vault_name)
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    try:
        con.execute(
            "CREATE VIRTUAL TABLE chunks_fts USING fts5("
            "id, path, title, heading, text, tokenize='porter unicode61')"
        )
        con.executemany(
            "INSERT INTO chunks_fts (id, path, title, heading, text) VALUES (?, ?, ?, ?, ?)",
            [(r["id"], r["path"], r["title"], r["heading"], r["text"]) for r in rows],
        )
        con.commit()
    finally:
        con.close()


def _sanitize_query(query_text: str) -> str:
    """FTS5 query syntax treats punctuation like -, ", *, ( as operators.
    For free-text natural-language input: drop stopwords, quote each
    remaining token as its own phrase, and OR them together rather than
    passing the raw string through.
    """
    tokens = [t for t in query_text.replace('"', " ").split() if t]
    tokens = [t for t in tokens if t.lower() not in _STOPWORDS] or tokens
    if not tokens:
        return '""'
    return " OR ".join(f'"{t}"' for t in tokens)


def search_fts(vault_name: str, query_text: str, limit: int = 20) -> list[dict]:
    """Return BM25 hits best-first (FTS5's bm25() is more-negative-is-better,
    so the default ascending ORDER BY already sorts best-first)."""
    path = fts_path(vault_name)
    if not path.exists():
        return []
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT id, path, title, heading, text, bm25(chunks_fts) AS score "
            "FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY score LIMIT ?",
            (_sanitize_query(query_text), limit),
        ).fetchall()
    except sqlite3.OperationalError:
        # Malformed/empty derived query (e.g. all-punctuation input) — no matches.
        return []
    finally:
        con.close()
    return [dict(r) for r in rows]
