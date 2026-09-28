"""Markdown -> HTML rendering for the web app, with internal wiki links
rewritten to in-app note URLs before rendering.

Reuses wiki.lint's own link-matching/resolution (LINK_RE, _resolve_link)
rather than reimplementing link parsing — the two need to agree on what
counts as an in-vault link.
"""

from __future__ import annotations

import re
from pathlib import Path

import markdown as _markdown

from wiki import config
from wiki.lint import LINK_RE, _resolve_link

MARKDOWN_EXTENSIONS = ["tables", "sane_lists", "fenced_code", "toc"]

# A fenced code block or inline code span — link-rewriting must skip over
# these so a documentation example showing `[text](url)` literally isn't
# mistaken for a real in-vault link. Same reasoning as wiki.lint._strip_code,
# but here we need to *keep* the code (unchanged), not drop it.
_CODE_RE = re.compile(r"```.*?```|`[^`\n]+`", re.DOTALL)


def _rewrite_links_outside_code(text: str, from_path: Path, vault: config.Vault) -> str:
    vault_root = vault.path.resolve()

    def replace(match: re.Match[str]) -> str:
        whole = match.group(0)
        target = match.group(1)
        resolved = _resolve_link(target, from_path, vault.path)
        if resolved is None:
            return whole
        try:
            rel = resolved.relative_to(vault_root)
        except ValueError:
            return whole  # resolves outside this vault; leave untouched
        new_target = f"/{vault.name}/notes/{rel.as_posix()}"
        prefix = whole[: whole.index("](") + 2]
        return f"{prefix}{new_target})"

    return LINK_RE.sub(replace, text)


def rewrite_links(markdown_text: str, from_path: Path, vault: config.Vault) -> str:
    """Rewrite in-vault markdown links to `/​{vault}/notes/{path}` URLs.

    Leaves untouched: fenced code blocks, inline code spans, external links
    (http(s)://, mailto:), fragment-only links, and links that resolve
    outside the vault or to a non-.md target — exactly what
    `wiki.lint._resolve_link` already treats as "not an in-vault link."
    """
    pieces: list[str] = []
    last_end = 0
    for m in _CODE_RE.finditer(markdown_text):
        pieces.append(_rewrite_links_outside_code(markdown_text[last_end : m.start()], from_path, vault))
        pieces.append(m.group(0))
        last_end = m.end()
    pieces.append(_rewrite_links_outside_code(markdown_text[last_end:], from_path, vault))
    return "".join(pieces)


def render_note_body(markdown_text: str, from_path: Path, vault: config.Vault) -> str:
    """A note's markdown body -> HTML, with internal links pointing at
    in-app note URLs instead of raw filesystem-relative `.md` paths."""
    rewritten = rewrite_links(markdown_text, from_path, vault)
    return _markdown.markdown(rewritten, extensions=MARKDOWN_EXTENSIONS)
