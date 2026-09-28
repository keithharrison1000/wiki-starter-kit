---
type: Note
title: Example note
description: Shows the frontmatter every note in this wiki uses.
tags: [example]
status: draft
generated: { by: human:user, at: 2026-08-15T00:00:00Z }
---

# Renaming this vault

This is a placeholder hobby knowledge base. To turn it into a real one:

1. Rename the `vaults/hobby-example/` folder (or copy it as a starting
   point for a new one) to something like `vaults/woodworking/`.
2. Update its entry — or add a new one — in the root `vaults.toml`.
3. Delete this note, or replace it with real content.
4. Open the folder directly in Obsidian as its own vault.

# Adding content

- Write notes directly, following the template at `templates/note.md` in
  the `general` vault (a plain reference, not a link — OKF links only
  resolve within one bundle, and each vault is its own bundle).
- Or import a file: `uv run wiki-ingest some.pdf --vault <name>` — PDFs go
  through the vendored `pdf2md` converter and land in `inbox/` as an OKF
  `Source` concept, citing the original file in `sources`.

# Searching

After adding notes, refresh the local semantic index and query it:

```bash
uv run wiki-index --vault <name>
uv run wiki-query "some question" --vault <name>
```
