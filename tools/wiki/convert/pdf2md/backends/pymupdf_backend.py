from pathlib import Path

import pymupdf4llm

name = "fast"


def convert(doc_path: Path, images_dir: Path | None) -> tuple[str, list[Path]]:
    write_images = images_dir is not None
    if images_dir is not None:
        images_dir.mkdir(parents=True, exist_ok=True)

    markdown = pymupdf4llm.to_markdown(
        str(doc_path),
        write_images=write_images,
        image_path=str(images_dir) if images_dir is not None else "",
    )

    image_paths = (
        sorted(p for p in images_dir.iterdir() if p.is_file())
        if images_dir is not None
        else []
    )
    return markdown, image_paths
