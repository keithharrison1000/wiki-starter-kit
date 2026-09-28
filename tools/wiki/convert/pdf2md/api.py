from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import fitz  # PyMuPDF

from wiki.convert.pdf2md import detection
from wiki.convert.pdf2md.backends import docling_backend, pymupdf_backend

BackendName = Literal["auto", "fast", "ocr"]

_BACKENDS = {
    "fast": pymupdf_backend,
    "ocr": docling_backend,
}


@dataclass
class ConversionResult:
    markdown: str
    output_path: Path | None
    image_paths: list[Path]
    backend: str


def convert(
    input_path: str | Path,
    output_path: str | Path | None = None,
    images_dir: str | Path | None = None,
    backend: BackendName = "auto",
) -> ConversionResult:
    """Convert a PDF file to markdown.

    `backend="auto"` inspects the document and routes it to the fast
    native-text backend or the OCR/layout fallback backend. Pass "fast" or
    "ocr" to force a specific backend.
    """
    doc_path = Path(input_path)
    if not doc_path.is_file():
        raise FileNotFoundError(f"No such PDF file: {doc_path}")

    if backend == "auto":
        with fitz.open(doc_path) as doc:
            resolved_backend = "ocr" if detection.needs_ocr_backend(doc) else "fast"
    elif backend in _BACKENDS:
        resolved_backend = backend
    else:
        raise ValueError(f"Unknown backend {backend!r}; expected 'auto', 'fast', or 'ocr'")

    images_path = Path(images_dir) if images_dir is not None else None
    markdown, image_paths = _BACKENDS[resolved_backend].convert(doc_path, images_path)

    out_path = Path(output_path) if output_path is not None else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(markdown, encoding="utf-8")

    return ConversionResult(
        markdown=markdown,
        output_path=out_path,
        image_paths=image_paths,
        backend=resolved_backend,
    )
