import fitz  # PyMuPDF

MIN_WORDS_PER_PAGE = 10


def _sample_page_indices(page_count: int, sample_pages: int) -> list[int]:
    if page_count <= sample_pages:
        return list(range(page_count))
    step = page_count / sample_pages
    return sorted({int(i * step) for i in range(sample_pages)})


def _is_textful(page: fitz.Page, min_words: int = MIN_WORDS_PER_PAGE) -> bool:
    word_count = len(page.get_text("text").split())
    return word_count >= min_words


def _has_undetected_table(page: fitz.Page) -> bool:
    """True if the page has a table that the fast backend's default
    table-detection strategy ("lines_strict") would miss and rasterize as an
    image instead of extracting as text — e.g. tables laid out with tab-stops
    rather than ruled lines. Checked via the more lenient "lines" strategy.
    """
    if page.find_tables(strategy="lines_strict").tables:
        return False  # fast backend already detects and extracts this fine
    return bool(page.find_tables(strategy="lines").tables)


def needs_ocr_backend(
    doc: fitz.Document,
    sample_pages: int = 10,
    text_ratio_threshold: float = 0.5,
    min_undetected_tables: int = 1,
) -> bool:
    """Classify a whole document as needing the OCR/layout fallback backend.

    Samples up to `sample_pages` pages spread evenly across the document and
    checks two things:

    - How many sampled pages have a meaningful native text layer. If the
      fraction of textful pages falls below `text_ratio_threshold`, the
      document is treated as scanned/complex and routed to the OCR backend.
    - How many textful pages have a table the fast backend's table-detection
      would miss (see `_has_undetected_table`). If at least
      `min_undetected_tables` such pages are found, the document is routed to
      the OCR backend, whose table-structure model extracts these reliably
      instead of silently dropping the data into a rasterized image.
    """
    page_count = doc.page_count
    if page_count == 0:
        return False

    indices = _sample_page_indices(page_count, sample_pages)
    pages = [doc[i] for i in indices]

    textful_pages = [p for p in pages if _is_textful(p)]
    text_ratio = len(textful_pages) / len(indices)
    if text_ratio < text_ratio_threshold:
        return True

    undetected_tables = sum(1 for p in textful_pages if _has_undetected_table(p))
    return undetected_tables >= min_undetected_tables
