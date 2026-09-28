---
type: MOC
title: Conventions
description: Wiki-wide frontmatter and type conventions, kept in sync across every vault.
status: stable
generated: { by: claude-code/sonnet-5, at: 2026-08-16T18:15:00Z }
---

# Why this file exists in every vault

Vaults are isolated Obsidian vaults with no cross-vault linking, so a
conventions doc living in only one vault would be invisible from every
other one. This note is copied — not linked — into every vault for that
reason. `vaults/general/conventions.md` in the main `wiki` repo is the
canonical source; the librarian keeps every other vault's copy in sync
whenever it changes (see `.claude/skills/librarian/SKILL.md`).

# Frontmatter

Every note is an [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
concept: YAML frontmatter with a required `type`, plus `title`,
`description`, `tags` as useful.

`type` vocabulary:

- `Note` — the default, for anything that isn't cleanly one of the below.
- `Source` — raw imported material (from `wiki-ingest`), pending triage
  in `inbox/`. Always moves to `sources/` once triaged, unchanged — the
  permanent citation anchor, never reshaped into a `Note` itself. The
  folder, not the type, distinguishes pending from triaged.
- `Foundation` — a condensed summary of one triaged `Source`, citing it.
  The mandatory first output of triage, before any `Concept`/`Topic`/
  `Entity` extraction — see "Workflow" below.
- `MOC` — a curated entry point for a vault's own content. Linked *from*,
  not *to* — exempt from `wiki-lint`'s orphan check.
- `Daily` — daily notes. Also exempt from the orphan check.
- `Synthesis` — an answer the librarian compiled across notes and filed
  back into the wiki, rather than losing it to chat history.
- `Concept` — a broad, abstract, timeless idea. Example: *Innovation*,
  *Gravity*.
- `Topic` — a specific, concrete subject that falls under a concept.
  Example: *The History of Smartphones*, *Black Holes*. A hub that
  `Concept`/`Entity` notes should link *up to* — unlike `MOC`, it is
  checked for inbound links, since that's its whole purpose.
- `Entity` — a distinct, uniquely identifiable person, place,
  organization, or object. Example: *Apple iPhone 16*.

`generated.by` records who wrote a note: `human:user` for notes you
write directly, `claude-code/<model>` when the librarian skill files
something, `process:<id>` for automated imports.

# Workflow

New, unfiled notes land in `inbox/` (e.g. via `wiki-ingest`) as `type:
Source`. Triage is one uniform process regardless of how much the source
turns out to be worth: move it to `sources/`, check `meta/` (if this
vault has a triage guide for this kind of document) *before* writing
anything, write a `Foundation` note summarizing it, then extract whatever
`Concept`/`Topic`/`Entity` pages are actually worth it — extending
existing ones where they already exist, rather than always creating new
ones. The result is a fixed citation chain, each link citing only the
level below it: `Concept`/`Topic`/`Entity` → `Foundation` → `Source` →
`raw/`. Full detail in `.claude/skills/librarian/SKILL.md`'s "Triaging"
section.

`meta/` (when a vault has one) holds `type: MOC` triage guides — one per
kind of document that vault regularly receives — describing what that
document type is like, a suggested Foundation-note structure, and which
kinds of things it typically yields `Concept`/`Topic`/`Entity` pages for,
so triage draws on accumulated domain knowledge rather than one
read-through's judgment alone.

`wiki-lint` flags two ways triage can go wrong: a `Source` still sitting
in `inbox/` (not triaged yet — expected, not a defect) and *any other
type* sitting in `inbox/` (`inbox/` should only ever hold pending Source
concepts — a real mistake). See the `note.md` template in the `general`
vault's `templates/` folder for the starter frontmatter to begin a new
note from (a plain reference, not a link — it's in a different bundle).
