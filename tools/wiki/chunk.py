"""A small markdown-aware chunker: splits a concept body on headings, then
further splits any section that's still too long by paragraph. Deliberately
simple — avoids pulling in a full text-splitting library for this.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
MAX_CHUNK_CHARS = 1500


@dataclass
class Chunk:
    heading_path: str
    text: str


def _split_sections(body: str) -> list[tuple[str, str]]:
    """Split body into (heading_path, section_text) pairs, tracking heading
    depth so a chunk under '## Steps' inside '# Trigger' keeps both in its path.
    """
    sections: list[tuple[str, str]] = []
    stack: list[str] = []
    current_lines: list[str] = []

    def flush():
        text = "\n".join(current_lines).strip()
        if text:
            sections.append((" > ".join(stack) or "(untitled)", text))

    for line in body.splitlines():
        match = HEADING_RE.match(line)
        if match:
            flush()
            current_lines = []
            level = len(match.group(1))
            title = match.group(2).strip()
            stack = stack[: level - 1]
            stack.append(title)
        else:
            current_lines.append(line)
    flush()

    if not sections and body.strip():
        sections.append(("(untitled)", body.strip()))
    return sections


def _split_long_lines(text: str, max_chars: int) -> list[str]:
    """Split a single over-long paragraph (e.g. a wide markdown table with
    no blank lines to split on) by line, so no chunk is ever left too large
    to embed.
    """
    lines = text.splitlines()
    parts: list[str] = []
    current_lines: list[str] = []
    current_len = 0
    for line in lines:
        line_len = len(line) + 1
        if current_lines and current_len + line_len > max_chars:
            parts.append("\n".join(current_lines))
            current_lines = [line]
            current_len = line_len
        else:
            current_lines.append(line)
            current_len += line_len
    if current_lines:
        parts.append("\n".join(current_lines))
    return parts or [text]


def _split_long_section(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    paragraphs = re.split(r"\n\s*\n", text)
    parts: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) > max_chars and current:
            parts.append(current)
            current = para
        else:
            current = candidate
    if current:
        parts.append(current)
    parts = parts or [text]

    final: list[str] = []
    for part in parts:
        if len(part) <= max_chars:
            final.append(part)
        else:
            final.extend(_split_long_lines(part, max_chars))
    return final


def chunk_body(body: str, max_chars: int = MAX_CHUNK_CHARS) -> list[Chunk]:
    chunks: list[Chunk] = []
    for heading_path, section_text in _split_sections(body):
        for part in _split_long_section(section_text, max_chars):
            chunks.append(Chunk(heading_path=heading_path, text=part))
    return chunks
