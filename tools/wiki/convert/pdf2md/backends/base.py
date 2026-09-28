from pathlib import Path
from typing import Protocol


class Backend(Protocol):
    """Converts a PDF file to markdown, optionally extracting images."""

    name: str

    def convert(self, doc_path: Path, images_dir: Path | None) -> tuple[str, list[Path]]:
        """Return (markdown_text, extracted_image_paths)."""
        ...
