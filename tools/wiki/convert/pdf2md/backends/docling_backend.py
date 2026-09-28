import tempfile
from pathlib import Path
from typing import Any

name = "ocr"

_converters: dict[bool, Any] = {}


def _get_converter(extract_images: bool) -> Any:
    converter = _converters.get(extract_images)
    if converter is None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        pipeline_options = PdfPipelineOptions(generate_picture_images=extract_images)
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }
        )
        _converters[extract_images] = converter
    return converter


def convert(doc_path: Path, images_dir: Path | None) -> tuple[str, list[Path]]:
    from docling_core.types.doc import ImageRefMode

    result = _get_converter(extract_images=images_dir is not None).convert(str(doc_path))
    document = result.document

    if images_dir is not None:
        images_dir = images_dir.resolve()
        images_dir.mkdir(parents=True, exist_ok=True)
        # export_to_markdown() has no artifacts_dir param; save_as_markdown()
        # is the current API for writing referenced images alongside the text.
        # artifacts_dir is resolved relative to the (temp) markdown file's own
        # directory, not the caller's cwd, so it must be made absolute first
        # or images silently land next to the temp file instead of here.
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            document.save_as_markdown(
                tmp_path,
                image_mode=ImageRefMode.REFERENCED,
                artifacts_dir=images_dir,
            )
            markdown = tmp_path.read_text(encoding="utf-8")
        finally:
            tmp_path.unlink(missing_ok=True)
        image_paths = sorted(p for p in images_dir.iterdir() if p.is_file())
    else:
        markdown = document.export_to_markdown(image_mode=ImageRefMode.PLACEHOLDER)
        image_paths = []

    return markdown, image_paths
