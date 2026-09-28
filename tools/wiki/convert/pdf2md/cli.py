import argparse
import sys
from pathlib import Path

from wiki.convert.pdf2md.api import convert


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdf2md", description="Convert a PDF to Markdown.")
    parser.add_argument("input", type=Path, help="Path to the input PDF file")
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Path to write the markdown output (defaults to stdout)",
    )
    parser.add_argument(
        "--images-dir", type=Path, default=None,
        help="Directory to extract images into",
    )
    parser.add_argument(
        "--backend", choices=["auto", "fast", "ocr"], default="auto",
        help="Conversion backend to use (default: auto-detect)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = convert(
            args.input,
            output_path=args.output,
            images_dir=args.images_dir,
            backend=args.backend,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.output is None:
        print(result.markdown)
    else:
        print(
            f"Wrote {result.output_path} "
            f"({result.backend} backend, {len(result.image_paths)} image(s))"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
