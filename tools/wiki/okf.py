"""Minimal read/write layer for Open Knowledge Format (OKF) v0.2 bundles.

Spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
Implements the subset relevant to a personal wiki: concept frontmatter
(type/title/description/tags/status/generated/verified/stale_after/sources),
the actor convention, and the reserved index.md/log.md files. The
Attested Computation family (spec §10) is out of scope — no analog for
personal notes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

OKF_VERSION = "0.2"
RESERVED_FILENAMES = {"index.md", "log.md"}

# Not part of the OKF spec (which reserves only the two above) — README.md
# is common in bundles distributed as git repos, for GitHub's own rendering,
# and isn't meant to be a concept. Excluded from concept scanning/listing
# so it doesn't need a frontmatter block.
NON_CONCEPT_FILENAMES = RESERVED_FILENAMES | {"README.md"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def actor_human(user_id: str) -> str:
    return f"human:{user_id}"


def actor_agent(producer: str, version: str) -> str:
    return f"{producer}/{version}"


def actor_process(process_id: str) -> str:
    return f"process:{process_id}"


@dataclass
class Concept:
    """An OKF concept document: YAML frontmatter + markdown body."""

    type: str
    title: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    status: str | None = None
    generated: dict | None = None
    verified: dict | list[dict] | None = None
    stale_after: str | None = None
    sources: list[dict] = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    body: str = ""

    def to_frontmatter(self) -> dict:
        fm: dict = {"type": self.type}
        if self.title is not None:
            fm["title"] = self.title
        if self.description is not None:
            fm["description"] = self.description
        if self.tags:
            fm["tags"] = self.tags
        if self.status is not None:
            fm["status"] = self.status
        if self.generated is not None:
            fm["generated"] = self.generated
        if self.verified is not None:
            fm["verified"] = self.verified
        if self.stale_after is not None:
            fm["stale_after"] = self.stale_after
        if self.sources:
            fm["sources"] = self.sources
        fm.update(self.extra)
        return fm

    def render(self) -> str:
        fm_yaml = yaml.safe_dump(
            self.to_frontmatter(), sort_keys=False, allow_unicode=True
        ).strip()
        return f"---\n{fm_yaml}\n---\n\n{self.body.strip()}\n"


def parse_concept(path: Path) -> Concept:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing OKF frontmatter block")
    _, _, rest = text.partition("---\n")
    fm_text, sep, body = rest.partition("\n---\n")
    if not sep:
        raise ValueError(f"{path}: unterminated frontmatter block")
    fm = yaml.safe_load(fm_text) or {}
    if not fm.get("type"):
        raise ValueError(f"{path}: OKF concept missing required 'type' field (spec §11)")

    known = {"type", "title", "description", "tags", "status", "generated", "verified", "stale_after", "sources"}
    extra = {k: v for k, v in fm.items() if k not in known}

    # PyYAML auto-parses an unquoted YYYY-MM-DD scalar into a date/datetime
    # object rather than a string. Normalize so Concept.stale_after is
    # always a str (as its type hint promises), regardless of how the note
    # happened to quote the value.
    stale_after = fm.get("stale_after")
    if isinstance(stale_after, datetime):
        stale_after = stale_after.date().isoformat()
    elif isinstance(stale_after, date):
        stale_after = stale_after.isoformat()

    return Concept(
        type=fm["type"],
        title=fm.get("title"),
        description=fm.get("description"),
        tags=fm.get("tags") or [],
        status=fm.get("status"),
        generated=fm.get("generated"),
        verified=fm.get("verified"),
        stale_after=stale_after,
        sources=fm.get("sources") or [],
        extra=extra,
        body=body.strip(),
    )


def write_concept(path: Path, concept: Concept) -> None:
    if path.name in NON_CONCEPT_FILENAMES:
        raise ValueError(f"{path.name} is a reserved/non-concept filename; not usable for a concept")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(concept.render(), encoding="utf-8")


# Top-level directories that hold real files but never OKF concepts:
# raw/ is the immutable source archive (originals, sometimes themselves
# .md); outputs/ is scratch working files for something outside the
# wiki (a paper, a report draft) that just happens to live alongside it.
NON_CONCEPT_DIRS = {"raw", "outputs"}


def iter_concepts(bundle_root: Path):
    """Yield (path, Concept) for every non-reserved, non-README .md file in
    the bundle, excluding NON_CONCEPT_DIRS (raw/, outputs/) at the top level.
    """
    for path in sorted(bundle_root.rglob("*.md")):
        if path.name in NON_CONCEPT_FILENAMES:
            continue
        if path.relative_to(bundle_root).parts[0] in NON_CONCEPT_DIRS:
            continue
        yield path, parse_concept(path)


def write_index(bundle_root: Path, is_root: bool = False) -> None:
    """(Re)generate index.md for a single directory (spec §8): a flat listing
    of concepts and subdirectories in that directory only, newest first isn't
    required by the spec — sorted by title/filename for stability instead.
    """
    entries_concepts = []
    entries_dirs = []
    for child in sorted(bundle_root.iterdir()):
        if child.name.startswith(".") or child.name in NON_CONCEPT_FILENAMES:
            continue
        if child.is_dir():
            entries_dirs.append(child)
        elif child.suffix == ".md":
            entries_concepts.append(child)

    lines = []
    if is_root:
        lines.append("---")
        lines.append(f'okf_version: "{OKF_VERSION}"')
        lines.append("---")
        lines.append("")

    lines.append(f"# {bundle_root.name}")
    lines.append("")

    if entries_concepts:
        lines.append("# Notes")
        lines.append("")
        for p in entries_concepts:
            concept = parse_concept(p)
            title = concept.title or p.stem
            desc = f" - {concept.description}" if concept.description else ""
            lines.append(f"* [{title}]({p.name}){desc}")
        lines.append("")

    if entries_dirs:
        lines.append("# Subdirectories")
        lines.append("")
        for d in entries_dirs:
            lines.append(f"* [{d.name}]({d.name}/)")
        lines.append("")

    (bundle_root / "index.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def append_log(bundle_root: Path, entry: str, kind: str = "Update") -> None:
    """Append a dated entry to log.md (spec §9)."""
    log_path = bundle_root / "log.md"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_line = f"* **{kind}**: {entry}"

    if not log_path.exists():
        log_path.write_text(
            f"# Directory Update Log\n\n## {today}\n{new_line}\n", encoding="utf-8"
        )
        return

    text = log_path.read_text(encoding="utf-8")
    heading = f"## {today}"
    if heading in text:
        text = text.replace(heading, f"{heading}\n{new_line}", 1)
    else:
        text = text.rstrip() + f"\n\n{heading}\n{new_line}\n"
    log_path.write_text(text, encoding="utf-8")


def init_bundle(bundle_root: Path) -> None:
    """Scaffold a fresh OKF bundle: root index.md + log.md."""
    bundle_root.mkdir(parents=True, exist_ok=True)
    write_index(bundle_root, is_root=True)
    append_log(bundle_root, "Established the bundle.", kind="Creation")
