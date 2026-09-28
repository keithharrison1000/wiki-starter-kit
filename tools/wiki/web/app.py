"""`wiki-web`: a read-only browser + Q&A app for people who aren't going to
open a terminal or an IDE to use the wiki.

Serves only vaults that aren't marked `sensitive` in vaults.toml (see
wiki.web.deps) and never writes to a vault — browsing and asking questions
only. Binds to localhost by default; see main() for --host/--port.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from wiki import config, okf
from wiki.web.ask import AskError, ask_question
from wiki.web.deps import exposed_vaults, get_exposed_vault
from wiki.web.render import render_note_body

APP_DIR = Path(__file__).parent
DEFAULT_PORT = 8420

# Entity/Topic/Concept/Foundation/Synthesis/Note/Daily are the primary
# reading content and render open, in this order. Source/MOC are citation
# anchors / navigation scaffolding (long raw-OCR text, or link-only pages),
# not primary reading, and render collapsed.
PROMINENT_TYPES = ["Entity", "Topic", "Concept", "Foundation", "Synthesis", "Note", "Daily"]
COLLAPSED_TYPES = ["Source", "MOC"]

app = FastAPI(title="Wiki")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")


def _vault_notes(vault: config.Vault) -> list[tuple[str, okf.Concept]]:
    """(relative-path string, Concept) for every note in the vault."""
    notes = [(str(path.relative_to(vault.path)), concept) for path, concept in okf.iter_concepts(vault.path)]
    notes.sort(key=lambda item: (item[1].title or item[0]).lower())
    return notes


def _group_by_type(notes: list[tuple[str, okf.Concept]]) -> dict[str, list[tuple[str, okf.Concept]]]:
    groups: dict[str, list[tuple[str, okf.Concept]]] = {}
    for rel, concept in notes:
        groups.setdefault(concept.type, []).append((rel, concept))
    return groups


def _valid_note_paths(vault: config.Vault) -> set[str]:
    return {str(p.relative_to(vault.path)) for p, _ in okf.iter_concepts(vault.path)}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    vaults = sorted(exposed_vaults().values(), key=lambda v: v.name)
    vault_counts = {v.name: sum(1 for _ in okf.iter_concepts(v.path)) for v in vaults}
    return templates.TemplateResponse(request, "home.html", {"vaults": vaults, "vault_counts": vault_counts})


@app.get("/{vault}/", response_class=HTMLResponse)
def browse_vault(request: Request, vault_obj: config.Vault = Depends(get_exposed_vault)):
    groups = _group_by_type(_vault_notes(vault_obj))
    prominent = [(t, groups[t]) for t in PROMINENT_TYPES if t in groups]
    collapsed = [(t, groups[t]) for t in COLLAPSED_TYPES if t in groups]
    other = [t for t in groups if t not in PROMINENT_TYPES and t not in COLLAPSED_TYPES]
    prominent += [(t, groups[t]) for t in sorted(other)]
    return templates.TemplateResponse(request, "vault.html", {"vault": vault_obj, "prominent": prominent, "collapsed": collapsed})


@app.get("/{vault}/notes/{note_path:path}", response_class=HTMLResponse)
def view_note(request: Request, note_path: str, vault_obj: config.Vault = Depends(get_exposed_vault)):
    vault_root = vault_obj.path.resolve()
    candidate = (vault_obj.path / note_path).resolve()
    if not candidate.is_relative_to(vault_root) or note_path not in _valid_note_paths(vault_obj):
        raise HTTPException(status_code=404, detail="Note not found")

    concept = okf.parse_concept(candidate)
    body_html = render_note_body(concept.body, candidate, vault_obj)
    return templates.TemplateResponse(
        request,
        "note.html",
        {"vault": vault_obj, "note_path": note_path, "concept": concept, "body_html": body_html},
    )


def _ask_context(request: Request, q: str, scope: str, vault: str, result, error: str | None) -> dict:
    vaults = exposed_vaults()
    return {
        "request": request,
        "vaults": sorted(vaults.values(), key=lambda v: v.name),
        "preselected_vault": vault if vault in vaults else None,
        "scope": scope,
        "q": q,
        "result": result,
        "error": error,
    }


@app.get("/ask", response_class=HTMLResponse)
def ask_page(request: Request, vault: str | None = None):
    context = _ask_context(request, q="", scope="current" if vault else "all", vault=vault or "", result=None, error=None)
    return templates.TemplateResponse(request, "ask.html", context)


@app.post("/ask", response_class=HTMLResponse)
def ask_submit(request: Request, q: str = Form(...), scope: str = Form("all"), vault: str = Form("")):
    if scope == "current":
        # Raises 404 for an unknown OR sensitive vault name — deliberately not
        # caught here. A form field is just as untrusted as a URL path segment:
        # someone could POST scope=current&vault=work directly, bypassing the
        # <select> that only ever lists exposed vaults.
        vault_obj = get_exposed_vault(vault)
        vault_names = [vault_obj.name]
    else:
        vault_names = list(exposed_vaults())

    result = None
    error = None
    try:
        result = ask_question(q, vault_names)
    except AskError as exc:
        error = str(exc)

    context = _ask_context(request, q, scope, vault, result, error)
    template_name = "_ask_result.html" if request.headers.get("HX-Request") else "ask.html"
    return templates.TemplateResponse(request, template_name, context)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wiki-web", description="Serve the read-only wiki browser + Q&A web app.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1, local machine only).")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--reload", action="store_true", help="Auto-reload on code changes (development only).")
    args = parser.parse_args(argv)

    uvicorn.run("wiki.web.app:app", host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
