"""The "ask a question" feature: retrieval (reused from wiki.query.search)
plus a from-scratch synthesis step, since this codebase has no importable
answer-generation logic anywhere else — the librarian skill's own answering
discipline is prose inside .claude/skills/librarian/SKILL.md, not code.

Mirrors that discipline directly: answer only from the retrieved excerpts,
say plainly when nothing relevant was found, and cite the notes an answer
actually drew from. Citations are the full set of notes given to the model
as context, not parsed out of its prose — every one of them genuinely was
part of what it saw, so this is both simpler and more reliable than trying
to extract citations from free-form text.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import anthropic

from wiki.query import search

DEFAULT_MODEL = os.environ.get("WIKI_ASK_MODEL", "claude-haiku-4-5")

SYSTEM_PROMPT = """You are answering a question about the contents of a personal wiki, using only the note excerpts provided below the question as context.

Rules:
- Answer using ONLY the information in the provided excerpts. Never use outside or general knowledge, even if you happen to know more about the topic.
- If the excerpts don't actually contain enough to answer the question, say so plainly rather than guessing or filling gaps from general knowledge.
- Be concise and direct.
- Don't invent note titles, facts, or details beyond what appears in the excerpts."""


@dataclass
class Citation:
    vault: str
    path: str
    title: str | None
    heading: str


@dataclass
class AnswerResult:
    answer: str
    citations: list[Citation]


class AskError(Exception):
    """An already-user-facing, friendly error message for the /ask route."""


def _build_context(chunks: list[dict]) -> str:
    parts = [
        f"[Excerpt {i}] vault={c['vault']} path={c['path']} heading={c['heading']}\n{c['text'].strip()}"
        for i, c in enumerate(chunks, start=1)
    ]
    return "\n\n".join(parts)


def _dedupe_citations(chunks: list[dict]) -> list[Citation]:
    seen: set[tuple[str, str]] = set()
    citations = []
    for c in chunks:
        key = (c["vault"], c["path"])
        if key in seen:
            continue
        seen.add(key)
        citations.append(Citation(vault=c["vault"], path=c["path"], title=c.get("title"), heading=c["heading"]))
    return citations


def ask_question(question: str, vault_names: list[str], k: int = 5) -> AnswerResult:
    try:
        chunks = search(question, vault_names, k=k)
    except RuntimeError as exc:
        raise AskError(
            "Search is temporarily unavailable (the local embedding service isn't running). "
            "Try again in a moment."
        ) from exc

    if not chunks:
        return AnswerResult(answer="Nothing in these vaults looks relevant to that question.", citations=[])

    # Checked explicitly, before ever touching the SDK: with no key at all,
    # the SDK's own client-side pre-flight check raises a plain TypeError
    # (not one of its own named exceptions, since it never got as far as
    # making a request) — catching that reliably would mean matching on a
    # generic exception type that could just as easily mean a real bug.
    # AuthenticationError (caught below) is reserved for a key that *is*
    # present but rejected by the API itself.
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise AskError("Ask isn't configured yet (no Anthropic API key set).")

    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nExcerpts:\n\n{_build_context(chunks)}",
                }
            ],
        )
    except anthropic.AuthenticationError as exc:
        raise AskError("Ask isn't configured yet (no valid Anthropic API key set).") from exc
    except anthropic.RateLimitError as exc:
        raise AskError("The AI service is rate-limited right now. Try again shortly.") from exc
    except anthropic.APIConnectionError as exc:
        raise AskError("Couldn't reach the AI service (no network connection to Anthropic).") from exc
    except anthropic.APIStatusError as exc:
        raise AskError("The AI service returned an error. Try again shortly.") from exc
    except Exception as exc:  # last-resort safety net — never leak a stack trace to end users
        raise AskError("Something went wrong answering that question.") from exc

    answer_text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")

    return AnswerResult(answer=answer_text, citations=_dedupe_citations(chunks))
