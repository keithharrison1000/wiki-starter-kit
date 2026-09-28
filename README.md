# wiki

Personal, LLM-curated knowledge base infrastructure: multiple independent
vaults (work + hobbies), stored as plain markdown in the
[Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
(OKF v0.2), opened in Obsidian, searched locally via embeddings, and
curated by Claude Code acting as librarian (`.claude/skills/librarian/`).

## Architecture: three layers

Each vault is built on three layers, cleanly separated by who's allowed
to touch what:

- **`raw/`** — the immutable source-of-truth layer. Original documents
  (`wiki-ingest` archives whatever you feed it: PDFs, articles, images,
  data files), read-only by convention, never edited or deleted by the
  librarian. This is what everything else in the vault ultimately derives
  from.
- **The wiki** — every other `.md` file in the vault: notes, entity/concept
  pages, `Source` write-ups, `Synthesis` pages, `index.md`/`log.md`. The
  librarian owns creating and maintaining these; you read and steer.
- **The schema** — `.claude/skills/librarian/SKILL.md`, which tells the
  librarian how the wiki is structured, what the conventions are, and what
  to do when ingesting, answering questions, or linting. You and the
  librarian co-evolve this as you find what works.

## Layout

```
vaults/                  vaults that live in this repo (non-sensitive)
  general/                shared conventions, templates, the root MOC
    conventions.md          canonical frontmatter/type reference — every
                             vault carries a copy, see "Conventions" below
    raw/                   immutable archive of general's source documents
    inbox/                 freshly ingested notes awaiting triage
    sources/                triaged Source notes kept as citation anchors
                             (only appears once something's been triaged there)
    meta/                   triage guides for document types this vault
                             regularly receives (only appears once one exists)
  hobby-example/          starter vault — rename/duplicate for a real one
tools/wiki/               all the Python tooling (see below)
vaults.toml               registry of every vault (incl. external ones)
.claude/skills/librarian/ the curator skill
```

The sensitive `work` vault deliberately lives **outside** this repo, in
its own local-only git repo at `~/dev/wiki-work` (no remote), so
work/employer content can never end up in a repo that might get pushed
somewhere shared. It's still registered in `vaults.toml` (`sensitive =
true`) so the tooling below can index and search it like any other vault.

Each vault folder is its own Obsidian vault — open it directly in Obsidian
(`File > Open Vault`). There's no single top-level Obsidian vault spanning
all of them; the Python tooling is what bridges knowledge bases (semantic
search across vaults), while Obsidian's own graph view stays scoped to one
vault at a time. This also keeps `work` visually and structurally
separate from everything else.

`meta/` is optional and vault-specific: a triage guide per kind of
document that vault regularly receives (e.g. `meta/university-financial-statements.md`
in `finance`), used as a completeness check during triage rather than
relying on a single read-through's judgment alone. See "Triaging" and
"meta/: triage guides" in `.claude/skills/librarian/SKILL.md`.

## Format: OKF

Every note is an OKF "concept": a markdown file with YAML frontmatter
whose only required field is `type` — `Note`, `Source`, `MOC`, `Daily`,
`Synthesis` (an answer the librarian compiles across multiple notes and
files back into the wiki, rather than letting it disappear into chat
history), `Foundation` (a condensed summary of one triaged `Source`, the
mandatory first step of triage — see "Triaging: Source → Foundation →
Concept/Topic/Entity" in `.claude/skills/librarian/SKILL.md`), or
`Concept`/`Topic`/`Entity` (abstract idea / specific subject that falls
under a concept / uniquely identifiable thing — see
"Concept vs Topic vs Entity vs Note" in `.claude/skills/librarian/SKILL.md`
for the full distinction). See `vaults/general/templates/note.md` for the
starter frontmatter.
`index.md` (directory listing) and `log.md` (dated changelog) are
OKF-reserved filenames present in every vault — don't hand-edit them,
regenerate via `wiki-refresh` (below) instead.

**Conventions**: since vaults are isolated Obsidian vaults with no
cross-vault linking, `conventions.md` — the fuller frontmatter/type
writeup — is copied, not linked, into every vault (`wiki-new-vault` does
this automatically for new ones). `vaults/general/conventions.md` is the
canonical source; the librarian keeps every other copy in sync when it
changes (see "Keeping conventions.md in sync" in
`.claude/skills/librarian/SKILL.md`).

We use the provenance/trust/lifecycle parts of the spec
(`generated`, `verified`, `status`, `stale_after`, `sources`), plus one
producer-defined extension the spec explicitly permits (§4.1): a `sha256`
key on `sources[]` entries pointing into `raw/`, letting `wiki-lint` detect
when a source has been tampered with (see "Architecture" above and
"Linting" below). We don't use the Attested Computation family (§10) — that's built for data-catalog use
cases (BigQuery tables, dbt models) with no analog in a personal wiki.

## Setup

```bash
uv sync
```

Installs everything, including PDF conversion (pymupdf, docling) — not
split into an optional extra, since a plain `uv sync` run for an
unrelated reason would silently drop it, which kept happening in
practice. `wiki-doctor` checks all of it in one pass.

Local semantic search needs [Ollama](https://ollama.com) running with an
embedding model pulled:

```bash
brew install ollama
ollama pull nomic-embed-text
```

## CLI tools

| Command | Purpose |
|---|---|
| `wiki-ingest <file> --vault NAME [--backend auto\|fast\|ocr]` | Archive a read-only copy into `raw/`, then convert (PDF via vendored `pdf2md`, `.xlsx` as one markdown table per worksheet, `.md`/`.txt` as extracted text, anything else as a placeholder) into an OKF `Source` concept in `inbox/`. `--backend` forces the PDF conversion path — see "PDF backend: fast vs ocr" below; default `auto` is right for almost everything. |
| `wiki-index --vault NAME [--rebuild]` | Build/update a vault's local hybrid index — LanceDB (vector) + SQLite FTS5 (BM25), both under `tools/wiki/data/`, gitignored. Omit `--vault` to index every registered vault. |
| `wiki-query "question" --vault NAME` | Local hybrid search (vector + BM25, fused via Reciprocal Rank Fusion); prints matching chunks with source path, snippet, and which signal(s) matched. |
| `wiki-refresh --vault NAME --log "message"` | Regenerate `index.md` and append a `log.md` entry after hand-editing notes. |
| `wiki-new-vault NAME [--external PATH] [--sensitive]` | Scaffold a new vault under `vaults/`, or register an existing external folder (like `work`). |
| `wiki-lint --vault NAME [--strict]` | Mechanical health checks: orphan notes, broken internal links, notes past `stale_after`, untriaged/half-triaged notes in `inbox/`, and raw/-source integrity (changed/missing/unregistered). `--strict` exits 1 on broken links, half-triaged notes, or raw-integrity issues (used by the pre-commit hook below); orphan/stale/untriaged findings never block. |
| `wiki-doctor` | Environment/setup health check — deps installed, Ollama reachable with the embedding model pulled, every registered vault a valid bundle. Content health is `wiki-lint`'s job, not this command's. |
| `wiki-outline <file> [--large-threshold N] [--max-depth N]` | Print a markdown file's heading structure — title, line range, line count per section — so a large/book-length file can be read section-by-section instead of in blind fixed-size chunks. Works on any markdown file, including an untriaged raw source. `--markdown --link-to PATH` emits a linked bullet-list outline instead, for pasting into a Foundation note as a navigable map back to the source. |
| `pdf2md file.pdf -o out.md` | The vendored converter directly, if you just want a one-off conversion outside the wiki flow. |
| `wiki-web [--host 127.0.0.1] [--port 8420]` | Serve the read-only web app (browse notes, ask questions) — see "Web app" below. |

All are also runnable as `uv run <command>`.

### PDF backend: fast vs ocr

`wiki-ingest` defaults to `--backend auto`, which picks per-document
based on whether pymupdf4llm's "fast" native-text extraction looks
sufficient (`tools/wiki/convert/pdf2md/detection.py`, vendored,
unmodified). Two backends are available:

- **`fast`** (pymupdf4llm) — used for most documents. Quick, but flattens
  chart/infographic content into noisier inline text (which
  `wiki-ingest` already cleans up — see picture-text/CJK-noise stripping
  in `tools/wiki/ingest.py`).
- **`ocr`** (docling) — proper layout analysis; keeps a chart's
  underlying data as a clean table instead of flattening the image's
  pixels into text. Measured on the same 76-page real-world PDF: **`fast`
  took 37s, `ocr` took 115s — about 3x slower.**

Given the speed cost applies to every ingest while the quality gap only
matters for chart/infographic-heavy documents (and is largely closed
already by the cleanup step), `auto` stays the default rather than always
using `ocr`. Pass `--backend ocr` explicitly when you know a specific
document is chart-heavy enough that the difference is worth the wait.

### Search: hybrid vector + BM25

`wiki-index` builds two indexes per vault: a LanceDB vector index
(semantic/paraphrase search, via Ollama embeddings) and a SQLite FTS5
keyword index (`tools/wiki/fts.py` — exact terms, jargon, tool/proper
names; porter-stemmed, stopwords excluded so matches reflect real
overlap). `wiki-query` runs both and fuses the two ranked lists via
Reciprocal Rank Fusion, the same approach [tobi/qmd](https://github.com/tobi/qmd)
uses. Each result line shows which signal(s) found it (`via vector`,
`via bm25`, or `via bm25+vector` when both agree — the strongest
signal). No extra dependency: FTS5 ships in Python's stdlib `sqlite3`.

Indexing covers the whole vault, including `sources/` — the full
converted text of triaged Source concepts is searchable alongside
curated `Foundation`/`Concept`/`Entity`/`Note` pages, so a query can
still surface a granular detail that never made it into a curated note.
Only `raw/` (the original binaries, not text-searchable anyway) and the
reserved/non-concept files (`index.md`, `log.md`, `README.md`) are
excluded.

Indexing isn't automatic — nothing watches the vaults for edits, so a note
changed directly in Obsidian won't be reflected in search until `wiki-index`
is re-run. `wiki-query` guards against this silently going unnoticed: it
compares each queried vault's current file mtimes against what's in the
index and prints a warning (to stderr) listing how many notes have changed
since the last index, rather than just returning stale results with no
indication anything's out of date.

### Linting

`wiki-lint` catches what's mechanically checkable: notes nothing else
links to (`MOC`/`Daily` types excluded — they're expected entry points),
broken internal links, notes past their `stale_after` date, imported
`Source` concepts still sitting untriaged in `inbox/` (expected, not a
defect), any *non*-`Source` concept in `inbox/` (`inbox/` should only
ever hold pending Source concepts — a real defect), and two checks on
`raw/` — a source that's changed or gone missing since it was ingested
(comparing a SHA-256 of its current bytes against the hash `wiki-ingest`
recorded in `sources[].sha256`; deliberately not mtime, since `git
clone`/`checkout` reset mtimes to checkout time regardless of real content
history, which would false-positive every raw file right after a fresh
clone), and a raw file no concept's `sources` cites (dropped in by hand
outside `wiki-ingest`). It can't catch contradictions between notes,
a concept that keeps coming up but has no page of its own, or genuine
data gaps — that needs actual reading and judgment, which is the
librarian skill's job (see "Linting the wiki" in
`.claude/skills/librarian/SKILL.md`), not this script's.

**Pre-commit hook**: `.githooks/pre-commit` runs `wiki-lint --strict` on
whichever vault(s) live in the current repo before every commit, blocking
on broken links or raw-integrity issues (never on orphans/stale/untriaged
— those are normal ongoing state). One generic script for every wiki
repo, since it looks up `vaults.toml` rather than hardcoding vault names
per repo. It's already installed in `wiki`, `wiki-work`, and
`wiki-finance`; for a new external vault repo, install it with:

```bash
cp ~/dev/wiki/.githooks/pre-commit "$(git rev-parse --show-toplevel)/.git/hooks/pre-commit"
chmod +x "$(git rev-parse --show-toplevel)/.git/hooks/pre-commit"
```

## Adding a new knowledge base

```bash
uv run wiki-new-vault woodworking
```

This scaffolds `vaults/woodworking/` as a fresh OKF bundle and registers
it in `vaults.toml`. Open the new folder in Obsidian, start writing notes
following `vaults/general/templates/note.md`, then:

```bash
uv run wiki-index --vault woodworking
```

For something sensitive that shouldn't live in this repo at all (like
`work`), scaffold it elsewhere first (its own git repo, no remote) and
register it with `--external`:

```bash
uv run wiki-new-vault myvault --external ~/dev/myvault --sensitive
```

## The librarian

`.claude/skills/librarian/SKILL.md` is a Claude Code skill: ask a question
and it searches the relevant vault(s) locally and answers with citations;
ask it to file something and it writes a properly-frontmattered note and
keeps `index.md`/`log.md` current. See that file for the exact rules it
follows, including never touching `work` unprompted.

## Web app

`wiki-web` serves a small, read-only web app for people who aren't going
to open a terminal or an IDE to use the wiki — browse notes and ask
questions, nothing else (no editing, no ingestion). Run it with:

```bash
uv run wiki-web
```

and open `http://127.0.0.1:8420`. It binds to `127.0.0.1` by default —
reachable only from the same machine — since there's no authentication
layer built yet; pass `--host` deliberately if you need it reachable on a
trusted local network, understanding that's a conscious tradeoff, not a
default.

It only ever serves vaults where `sensitive` is not `true` in
`vaults.toml` (today: `general`, `hobby-example`), enforced on every
request — not just left off the home page's navigation.

Asking a question needs an [Anthropic API key](https://console.anthropic.com/settings/keys)
set as `ANTHROPIC_API_KEY` — this is separate from anything Claude-Code-related,
and every question asked spends real money (unlike the free-to-you
librarian skill inside your own Claude Code session). Browsing works
fine without it; only the ask page needs it. It defaults to
`claude-haiku-4-5`; override with `WIKI_ASK_MODEL` if you want a
different model.

## Not built yet

Text extraction for formats beyond PDF/`.xlsx`/`.md`/`.txt` (images,
other data files — they're archived to `raw/` on ingest, just not yet
converted to searchable markdown), authentication for the web app (so it could serve
sensitive vaults or be reachable beyond a trusted local network),
auto-installing Ollama, and cross-vault Obsidian linking are explicitly
out of scope for this pass — see the plan history if picking these up
later.
