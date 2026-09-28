"""`wiki-outline`: inspect a markdown file's heading structure.

Useful before reading a large (potentially book-length) markdown file
end-to-end: prints the heading tree with each section's line range and
size, so you can target `Read` calls at the sections that matter instead
of guessing fixed-size chunk boundaries. Works on any markdown file, not
just files already inside a vault — including a raw source before it's
even triaged.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
MD_EMPHASIS_RE = re.compile(r"[*_`]")
DEFAULT_LARGE_THRESHOLD = 400


@dataclass
class Section:
    level: int
    title: str
    start_line: int  # 1-indexed, the heading line itself (0 for the preamble)
    end_line: int  # 1-indexed, inclusive — last line before the next heading at <= level


def parse_outline(text: str) -> list[Section]:
    """Walk the file once, recording each heading's line and level, then
    resolve each one's end_line as the line before the next heading at the
    same or shallower level (so a section's range includes its subsections).
    """
    lines = text.splitlines()
    headings: list[tuple[int, int, str]] = []  # (line_no, level, title)
    for i, line in enumerate(lines, start=1):
        match = HEADING_RE.match(line)
        if match:
            headings.append((i, len(match.group(1)), match.group(2).strip()))

    sections: list[Section] = []
    if headings and headings[0][0] > 1:
        sections.append(Section(level=0, title="(preamble)", start_line=1, end_line=headings[0][0] - 1))
    elif not headings and lines:
        sections.append(Section(level=0, title="(untitled)", start_line=1, end_line=len(lines)))

    for idx, (line_no, level, title) in enumerate(headings):
        end_line = len(lines)
        for next_line_no, next_level, _ in headings[idx + 1 :]:
            if next_level <= level:
                end_line = next_line_no - 1
                break
        sections.append(Section(level=level, title=title, start_line=line_no, end_line=end_line))

    return sections


def obsidian_anchor(title: str) -> str:
    """Heading anchor for an Obsidian markdown-style link. Unlike GitHub,
    Obsidian's link resolver matches a fragment against a heading's actual
    (rendered) text rather than a precomputed kebab-case id — so the
    anchor here is the literal heading text, markdown emphasis stripped,
    percent-encoded for use inside the link parens. Not guaranteed to
    match in every edge case (e.g. duplicate heading names) — a wrong
    anchor just lands at the top of the note in Obsidian rather than
    erroring, so this is a convenience, not a validated reference.
    """
    text = MD_EMPHASIS_RE.sub("", title).strip()
    return quote(text, safe="")


def format_markdown_links(sections: list[Section], link_target: str, max_depth: int) -> str:
    """Render the outline as an indented markdown bullet list of links to
    `link_target#<anchor>`, suitable for pasting into a Foundation note as
    a human-navigable map of a large source.
    """
    lines_out = []
    for s in sections:
        if s.level == 0 or s.level > max_depth:
            continue
        indent = "  " * (s.level - 1)
        display = MD_EMPHASIS_RE.sub("", s.title).strip()
        anchor = obsidian_anchor(s.title)
        lines_out.append(f"{indent}- [{display}]({link_target}#{anchor})")
    return "\n".join(lines_out) if lines_out else "(no headings)"


def format_outline(sections: list[Section], large_threshold: int, max_depth: int) -> str:
    rows = []
    for s in sections:
        if s.level > max_depth:
            continue
        count = s.end_line - s.start_line + 1
        indent = "  " * max(s.level - 1, 0)
        label = f"{indent}{'#' * s.level + ' ' if s.level else ''}{s.title}"
        flag = "  ⚠ large" if count >= large_threshold else ""
        rows.append((label, f"lines {s.start_line}-{s.end_line}", f"({count})", flag))

    if not rows:
        return "(no content)"

    label_width = min(max(len(r[0]) for r in rows), 70)
    range_width = max(len(r[1]) for r in rows)
    lines_out = []
    for label, rng, count, flag in rows:
        lines_out.append(f"{label:<{label_width}}  {rng:<{range_width}}  {count}{flag}")
    return "\n".join(lines_out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wiki-outline", description="Print a markdown file's heading structure with line ranges and sizes."
    )
    parser.add_argument("path", type=Path, help="Path to a markdown file")
    parser.add_argument(
        "--large-threshold",
        type=int,
        default=DEFAULT_LARGE_THRESHOLD,
        help=f"Flag sections with at least this many lines as large (default {DEFAULT_LARGE_THRESHOLD})",
    )
    parser.add_argument("--max-depth", type=int, default=6, help="Only show headings up to this level (default 6)")
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Emit a linked markdown bullet list instead of the aligned table (requires --link-to)",
    )
    parser.add_argument(
        "--link-to",
        metavar="PATH",
        help="Link target for --markdown output, e.g. sources/some-source.md (bundle-relative)",
    )
    args = parser.parse_args(argv)

    if not args.path.exists():
        print(f"error: {args.path} does not exist")
        return 1
    if args.markdown and not args.link_to:
        print("error: --markdown requires --link-to")
        return 1

    text = args.path.read_text(encoding="utf-8")
    total_lines = len(text.splitlines())
    sections = parse_outline(text)

    if args.markdown:
        print(format_markdown_links(sections, args.link_to, args.max_depth))
        return 0

    print(f"{args.path.name} — {total_lines} lines\n")
    print(format_outline(sections, args.large_threshold, args.max_depth))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
