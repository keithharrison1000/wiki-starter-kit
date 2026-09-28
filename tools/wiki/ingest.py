"""`wiki-ingest`: archive a file into a vault's raw/ as an immutable source
copy, then file it into inbox/ as an OKF 'Source' concept. PDFs go through
the vendored pdf2md converter, .xlsx through xlsx2md (one markdown table
per worksheet), and .md/.txt pass through as extracted text; every other
file type is still archived, just without text extraction yet (see
README) — it's discoverable and citable, not unsupported outright.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
from datetime import date
from pathlib import Path

from wiki import config, okf

TEXT_EXTRACTABLE_SUFFIXES = {".pdf", ".md", ".txt", ".xlsx"}
PLAIN_TEXT_SUFFIXES = {".md", ".txt"}

# pymupdf4llm (and docling) can flatten OCR'd text found inside
# picture-classified regions — charts, infographics, decorative elements —
# straight into the markdown, wrapped in these markers. There's no real
# layout information behind it ("we cannot be sure about the formatting so
# we simply write it line by line" per pymupdf4llm's own docstring), so in
# practice it's just noise: garbled label fragments, not usable content.
# Stripped rather than kept.
PICTURE_TEXT_RE = re.compile(r"<!-- Start of picture text -->.*?<!-- End of picture text -->\n?", re.DOTALL)


def _strip_picture_text(markdown: str) -> str:
    return PICTURE_TEXT_RE.sub("", markdown)


# OCR sometimes misreads a small graphical element — a crest, a decorative
# section-break icon, a social-media glyph — as a stray CJK character or
# two. Deliberately narrow: only isolated *short* runs (<=4 chars) of
# CJK-script text get stripped, so a genuine multi-character CJK word,
# name, or quoted term in some future document is left alone rather than
# assumed to be noise.
CJK_RUN_RE = re.compile(
    "["
    "　-〿"  # CJK symbols/punctuation (incl. the fullwidth colon seen in practice)
    "぀-ヿ"  # Hiragana + Katakana
    "㐀-䶿"  # CJK Unified Ideographs Extension A
    "一-鿿"  # CJK Unified Ideographs
    "가-힣"  # Hangul Syllables
    "＀-￯"  # Halfwidth and Fullwidth Forms
    "]+"
)
EMPTY_HEADING_RE = re.compile(r"^#{1,6}[ \t]*$\n?", re.MULTILINE)
EMPTY_TAG_RE = re.compile(r"<(\w+)>\s*</\1>")


def _strip_cjk_noise(markdown: str, max_run: int = 4) -> str:
    markdown = CJK_RUN_RE.sub(lambda m: "" if len(m.group(0)) <= max_run else m.group(0), markdown)
    markdown = EMPTY_HEADING_RE.sub("", markdown)
    # Removing a short CJK run can leave an empty inline tag behind (e.g. a
    # <mark> that wrapped nothing else) — collapse repeatedly since removing
    # one empty tag can expose another one nested around it.
    prev = None
    while prev != markdown:
        prev = markdown
        markdown = EMPTY_TAG_RE.sub("", markdown)
    return markdown


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "untitled"


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    n = 2
    while True:
        candidate = path.with_name(f"{stem}-{n}{suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def ingest_file(
    input_path: Path, vault_name: str, actor: str = "human:user", pdf_backend: str = "auto"
) -> Path:
    if not input_path.is_file():
        raise FileNotFoundError(f"No such file: {input_path}")

    vault = config.resolve_vault(vault_name)
    raw_dir = vault.path / "raw"
    inbox = vault.path / "inbox"

    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_dest = _unique_path(raw_dir / input_path.name)
    shutil.copy2(input_path, raw_dest)  # copy only — the external original is never touched

    # Everything from here until the concept is safely written can fail
    # (conversion in particular has real external dependencies). Roll back
    # the raw copy on any failure rather than leaving an orphaned,
    # unreferenced file behind — raw_dest isn't chmod'd read-only until
    # the whole ingest has actually succeeded, so it stays deletable here.
    try:
        # last_modified (OKF §5.1, date-only) is the spec-facing recency signal.
        # sha256 is our own extension (spec permits producer-defined extra keys)
        # and is what wiki-lint actually verifies against: mtime isn't reliable
        # for this — git checkout/clone resets mtimes to checkout time regardless
        # of real content history, which would false-positive every raw file as
        # "changed" right after a fresh clone. A content hash only changes when
        # the content actually does.
        last_modified = date.fromtimestamp(raw_dest.stat().st_mtime).isoformat()
        sha256 = hashlib.sha256(raw_dest.read_bytes()).hexdigest()

        suffix = input_path.suffix.lower()
        if suffix == ".pdf":
            from wiki.convert.pdf2md import convert

            markdown = _strip_cjk_noise(_strip_picture_text(convert(raw_dest, backend=pdf_backend).markdown))
        elif suffix == ".xlsx":
            from wiki.convert.xlsx2md import convert as convert_xlsx

            markdown = convert_xlsx(raw_dest)
        elif suffix in PLAIN_TEXT_SUFFIXES:
            markdown = raw_dest.read_text(encoding="utf-8")
        else:
            markdown = (
                f"No text extraction is available yet for `{suffix}` files — this note "
                "is a placeholder so the source is still discoverable and citable. See "
                f"the archived original at `{raw_dest.relative_to(vault.path)}`."
            )

        title = input_path.stem
        concept = okf.Concept(
            type="Source",
            title=title,
            description=f"Imported from {input_path.name}",
            generated={"by": actor, "at": okf.now_iso()},
            sources=[
                {
                    "id": "original",
                    "resource": f"/{raw_dest.relative_to(vault.path)}",
                    "title": input_path.name,
                    "last_modified": last_modified,
                    "sha256": sha256,
                }
            ],
            body=markdown,
        )

        dest = _unique_path(inbox / f"{_slugify(title)}.md")
        okf.write_concept(dest, concept)
    except Exception:
        raw_dest.unlink(missing_ok=True)
        raise

    raw_dest.chmod(0o444)  # read-only: a technical nudge toward immutability, not a hard lock
    okf.write_index(inbox, is_root=False)
    okf.append_log(
        vault.path,
        f"Imported [{title}]({dest.relative_to(vault.path)}) from `{input_path.name}` "
        f"(archived at `{raw_dest.relative_to(vault.path)}`).",
    )
    okf.write_index(vault.path, is_root=True)
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wiki-ingest", description="Archive a file into raw/ and file it into a vault's inbox."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--vault", required=True)
    parser.add_argument(
        "--actor", default="human:user", help="OKF actor recorded in generated.by (default: human:user)"
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "fast", "ocr"],
        default="auto",
        help="PDF conversion backend (default: auto). 'fast' (pymupdf4llm) is quicker but flattens "
        "charts/infographics into noisier text; 'ocr' (docling) is ~3x slower but handles "
        "picture-embedded data better — worth it on request for a source you know is chart-heavy, "
        "not as a default (see README).",
    )
    args = parser.parse_args(argv)

    try:
        dest = ingest_file(args.input, args.vault, actor=args.actor, pdf_backend=args.backend)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
