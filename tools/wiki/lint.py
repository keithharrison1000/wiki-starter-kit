"""`wiki-lint`: mechanical health checks for a vault.

Covers what's checkable without reading/reasoning: orphan concepts (no
other concept's body links to them), broken internal links, notes past
their stale_after date, Source concepts still sitting untriaged in
inbox/, non-Source concepts left behind in inbox/ (triage started —
retyped — but never finished, since finishing means moving the file
out), and two checks on the raw/ immutable-source archive — a raw file
that's changed or gone missing since it was ingested, and a raw file no
concept's sources[] cites. Contradiction-detection, "this concept is
mentioned everywhere but has no page of its own," and data-gap analysis
need actual understanding of the content — that's the librarian skill's
job (see "Linting the wiki" in .claude/skills/librarian/SKILL.md), not
this script's.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import date, datetime
from pathlib import Path

from wiki import config, okf

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def _strip_code(body: str) -> str:
    """Drop fenced and inline code spans before scanning for links — a link
    shown as a documentation example inside backticks isn't a real link.
    """
    return INLINE_CODE_RE.sub("", FENCED_CODE_RE.sub("", body))

# MOC (whole-vault entry point, navigated into via index.md) and Daily
# (date-sequential, not typically cross-referenced) aren't expected to
# have inbound links the way content pages are. Topic is NOT exempt here
# despite also being a hub — its whole purpose is to be linked to *from*
# the Concept/Entity notes that fall under it, so a Topic with zero
# inbound links genuinely does mean nothing's been categorized under it
# yet, which is exactly the kind of thing this check should catch.
# Foundation is checked too, for the same reason as Topic: Concept/Topic/
# Entity notes extracted during triage are expected to link back to it.
ORPHAN_CHECK_TYPES = {"Note", "Source", "Synthesis", "Concept", "Entity", "Topic", "Foundation"}

# --strict (used by the pre-commit hook) exits 1 if any of these are found.
# Orphans/stale/untriaged are normal ongoing-curation state — e.g. an
# ingested-but-not-yet-triaged Source sitting in inbox/ is completely
# expected and shouldn't block a commit. Broken links, raw-integrity
# issues, and half-triaged notes are real defects — evidence of an
# incomplete or mistaken operation — worth stopping for.
BLOCKING_KEYS = {"broken_links", "modified_raw", "unregistered_raw", "half_triaged"}


def _resolve_link(target: str, from_path: Path, vault_root: Path) -> Path | None:
    """Resolve a markdown link target to a concept file's resolved path, or
    None if it's external (http(s)://, mailto:) or doesn't target a .md file.
    """
    if target.startswith(("http://", "https://", "mailto:", "#")):
        return None
    target = target.split("#", 1)[0]
    if not target.endswith(".md"):
        return None
    if target.startswith("/"):
        return (vault_root / target.lstrip("/")).resolve()
    return (from_path.parent / target).resolve()


def _raw_relative_path(resource: str) -> str | None:
    """If a sources[].resource string points into this bundle's raw/, return
    the raw/-relative path; otherwise None (external URL, other bundle path,
    scope descriptor, etc. — not something this vault's raw/ can be checked
    against).
    """
    if not resource.startswith("/raw/"):
        return None
    return resource[len("/raw/"):]


def lint_vault(vault_name: str) -> dict[str, list[str]]:
    vault = config.resolve_vault(vault_name)
    concepts = list(okf.iter_concepts(vault.path))
    concept_by_path = {path.resolve(): concept for path, concept in concepts}

    inbound: dict[Path, int] = {p: 0 for p in concept_by_path}
    broken_links: list[str] = []

    for path, concept in concepts:
        for match in LINK_RE.finditer(_strip_code(concept.body)):
            resolved = _resolve_link(match.group(1), path, vault.path)
            if resolved is None:
                continue
            if resolved in concept_by_path:
                inbound[resolved] += 1
            else:
                rel = path.relative_to(vault.path)
                broken_links.append(f"{rel} -> {match.group(1)}")

    orphans = sorted(
        str(p.relative_to(vault.path))
        for p, count in inbound.items()
        if count == 0 and concept_by_path[p].type in ORPHAN_CHECK_TYPES
    )

    today = date.today()
    stale: list[str] = []
    untriaged: list[str] = []
    half_triaged: list[str] = []
    for path, concept in concepts:
        rel_path = path.relative_to(vault.path)
        if concept.stale_after:
            try:
                stale_date = datetime.strptime(concept.stale_after, "%Y-%m-%d").date()
            except ValueError:
                pass
            else:
                if today >= stale_date:
                    stale.append(str(rel_path))
        if "inbox" in rel_path.parts:
            if concept.type == "Source":
                untriaged.append(str(rel_path))
            else:
                # inbox/ should only ever hold pending Source concepts —
                # a different type sitting there means triage started
                # (retyped) but was never finished (never moved out).
                half_triaged.append(str(rel_path))

    raw_dir = vault.path / "raw"
    cited_raw: set[str] = set()
    modified_raw: list[str] = []
    for path, concept in concepts:
        rel_path = path.relative_to(vault.path)
        for src in concept.sources:
            raw_rel = _raw_relative_path(src.get("resource", ""))
            if raw_rel is None:
                continue
            cited_raw.add(raw_rel)
            raw_path = raw_dir / raw_rel
            recorded_hash = src.get("sha256")
            if not raw_path.exists():
                modified_raw.append(f"{rel_path}: raw/{raw_rel} is missing")
            elif recorded_hash:
                # Content hash, not mtime: git checkout/clone resets mtimes to
                # checkout time regardless of real content history, so mtime
                # alone would false-positive every raw file after a fresh
                # clone. A hash only changes when the content actually does.
                current_hash = hashlib.sha256(raw_path.read_bytes()).hexdigest()
                if current_hash != recorded_hash:
                    modified_raw.append(f"{rel_path}: raw/{raw_rel} changed since ingest (sha256 mismatch)")

    unregistered_raw: list[str] = []
    if raw_dir.is_dir():
        for raw_file in sorted(raw_dir.rglob("*")):
            if raw_file.is_file():
                rel = str(raw_file.relative_to(raw_dir))
                if rel not in cited_raw:
                    unregistered_raw.append(f"raw/{rel}")

    return {
        "orphans": orphans,
        "broken_links": sorted(broken_links),
        "stale": sorted(stale),
        "untriaged": sorted(untriaged),
        "half_triaged": sorted(half_triaged),
        "modified_raw": sorted(modified_raw),
        "unregistered_raw": sorted(unregistered_raw),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wiki-lint", description="Mechanical health checks for a vault.")
    parser.add_argument("--vault", help="Comma-separated vault name(s). Default: all registered vaults.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if broken links or raw-source integrity issues are found (used by the pre-commit "
        "hook). Orphan/stale/untriaged findings never block, even with --strict.",
    )
    args = parser.parse_args(argv)

    names = [n.strip() for n in args.vault.split(",")] if args.vault else list(config.load_vaults())
    if not names:
        print("No vaults registered in vaults.toml.", file=sys.stderr)
        return 1

    exit_code = 0
    labels = {
        "orphans": "Orphan concepts (no inbound links from other notes)",
        "broken_links": "Broken internal links",
        "stale": "Past stale_after",
        "untriaged": "Untriaged Source concepts still in inbox/",
        "half_triaged": "Retyped but still in inbox/ (triage left incomplete)",
        "modified_raw": "Raw sources changed or missing since ingest",
        "unregistered_raw": "Raw files not cited by any concept",
    }
    for name in names:
        try:
            report = lint_vault(name)
        except Exception as exc:
            print(f"error linting {name!r}: {exc}", file=sys.stderr)
            exit_code = 1
            continue

        print(f"== {name} ==")
        if not any(report.values()):
            print("  Clean — no orphans, broken links, stale/untriaged/half-triaged notes, or raw-source issues.")
        for key, label in labels.items():
            if report[key]:
                print(f"  {label}: {len(report[key])}")
                for item in report[key]:
                    print(f"    - {item}")
        print()

        if args.strict and any(report[key] for key in BLOCKING_KEYS):
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
