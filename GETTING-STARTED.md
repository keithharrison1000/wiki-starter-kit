# Getting started

This is a starter kit for a personal knowledge base ("wiki") that you
build up over time by feeding it documents, and that [Claude
Code](https://claude.com/claude-code) reads, organises, and answers
questions from — like having a research assistant who's read everything
you've ever given it and keeps its own notes tidy.

It's plain markdown files on your own computer (opened in a free app
called [Obsidian](https://obsidian.md) if you want to browse them
visually), backed by a small set of Python tools, plus one file —
`.claude/skills/librarian/SKILL.md` — that teaches Claude Code how this
particular wiki is organised, so it acts consistently every time you
use it.

You don't need to understand all of that before you start. This guide
gets you from "just cloned the repo" to "asked Claude to file my first
document" in about fifteen minutes. `README.md` in this same folder is
the fuller reference — come back to it once you want to know *why*
something works the way it does, or want the full list of commands.

## What you'll need

1. **A terminal.** On a Mac, that's the Terminal app (Spotlight search
   → "Terminal"). Everything below is typed there.
2. **[Claude Code](https://claude.com/claude-code)** — this is what
   actually does the reading, organising, and answering. Install it
   and make sure you can run `claude` from your terminal before going
   further.
3. **[uv](https://docs.astral.sh/uv/getting-started/installation/)** —
   the tool that installs everything this wiki needs (Python and all
   its dependencies) in one step, without you having to manage Python
   versions yourself. Install it, then check it worked:
   ```bash
   uv --version
   ```
4. **[Obsidian](https://obsidian.md)** (optional but recommended) — a
   free app for browsing and reading your notes with proper formatting
   and a graph view. Not required for anything to *work*, just makes
   the notes nicer to read.
5. **[Ollama](https://ollama.com)** (optional) — only needed if you
   want fast local search across your notes (`wiki-query`). Skip this
   for now; you can add it later. If you do want it:
   ```bash
   brew install ollama
   ollama pull nomic-embed-text
   ```

## Step 1: get the code

Clone this repository to your own computer — pick somewhere sensible,
e.g. a `dev` folder in your home directory:

```bash
cd ~
mkdir -p dev && cd dev
git clone <the repo URL you were given> wiki
cd wiki
```

## Step 2: install everything

```bash
uv sync
```

This reads `pyproject.toml` and installs every Python package the
tools need (including PDF-reading libraries) into a private, local
environment inside this folder — it won't touch anything else on your
computer. Takes a minute or two the first time.

Check everything's healthy:

```bash
uv run wiki-doctor
```

This tells you what's installed correctly and what (if anything) still
needs attention — e.g. it'll say if Ollama isn't running, but that's
fine to ignore for now if you skipped step 5 above.

## Step 3: look around

This starter kit ships with two example vaults already set up, so you
can see the shape of things before creating your own:

- **`vaults/general/`** — shared conventions and a couple of template
  files.
- **`vaults/hobby-example/`** — a tiny example vault with one note in
  it, showing what a finished note actually looks like.

Open `vaults/hobby-example/` directly in Obsidian (`File → Open
Vault`) if you installed it, and have a look at `example-note.md` —
that's the target shape everything else will follow.

## Step 4: create your first real vault

This is where it becomes *yours*. Pick a name for what you want to
build a knowledge base about — a hobby, a research project, a
household/family archive, whatever. From inside the `wiki` folder:

```bash
uv run wiki-new-vault my-topic-name
```

Replace `my-topic-name` with something short, lowercase, and
hyphenated (e.g. `home-renovation`, `family-history`,
`sourdough-baking`). This creates `vaults/my-topic-name/` and registers
it automatically in `vaults.toml` — you don't need to edit that file by
hand.

## Step 5: open Claude Code and try it

From inside the `wiki` folder, start Claude Code:

```bash
claude
```

Now just talk to it in plain English. A few things to try:

- *"What vaults do I have set up?"*
- *"I want to add this PDF to my [topic name] vault: ~/Downloads/whatever.pdf"*
  — Claude will archive it, convert it to text, and file it as a
  pending note for you to review.
- *"Can you check the [topic name] vault for anything broken?"* — this
  runs the built-in health check (broken links, orphaned notes, etc.)
  and reports back in plain terms.
- Just tell it things directly: *"Make a note that the boiler was
  serviced on the 3rd of March by ABC Heating, cost £180."* — it'll
  write a properly-formatted note for you, no markdown knowledge
  required on your end.

Claude Code reads `.claude/skills/librarian/SKILL.md` automatically
and follows the conventions written there — that's the whole point of
this kit. You don't need to read that file yourself unless you're
curious how it works under the hood, or want to change how Claude
behaves in your wiki.

## What "good" looks like day to day

- Feed it documents as you get them (receipts, articles, PDFs, your
  own typed notes) — ask Claude to file them.
- Every so often, ask Claude to *"tidy up the [topic] vault"* or
  *"check for anything untriaged"* — freshly-imported documents sit in
  an `inbox/` folder until they've been read and turned into a proper
  note; Claude will work through that queue when asked.
- Ask it questions any time: *"What do I know about X?"* — it searches
  your own notes and answers with citations back to where the
  information came from, rather than guessing.
- Everything lives in plain markdown files in a git repository, so
  nothing is ever locked into a proprietary format, and your full
  history of changes is recoverable.

## If something goes sensitive or private

If you ever want a vault that should **never** end up in a shared or
public place (personal medical records, something for a specific
employer, anything like that), say so — Claude can set it up as a
separate, local-only folder with its own git history and no remote,
kept out of this repo entirely. See "Adding a new knowledge base" in
`README.md` for the exact mechanism (`--external --sensitive`).

## Where to go next

- `README.md` in this folder — the full reference: every command,
  what each one does, and the reasoning behind the OKF format this
  wiki uses.
- `.claude/skills/librarian/SKILL.md` — only if you're curious exactly
  how Claude decides what to do; you never need to edit this to use
  the wiki day to day, though you're welcome to tweak it as you find
  your own preferences.

Don't feel you need to understand the whole system before starting —
the whole point of having Claude Code as the librarian is that you can
just talk to it, and it handles the mechanics.
