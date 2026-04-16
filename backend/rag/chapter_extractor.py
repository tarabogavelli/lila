"""
Extract chapter-annotated text from PDFs using PyMuPDF.
Supports book-specific extraction strategies dispatched by source_name.
"""

import fitz
import re
from dataclasses import dataclass


@dataclass
class Chapter:
    number: int
    title: str
    text: str
    start_page: int
    end_page: int


CHAPTER_PATTERNS = [
    re.compile(r"^(?:CHAPTER|Chapter)\s+(\w+)[\s.:—-]*(.*)$", re.MULTILINE),
    re.compile(r"^(\d+|[IVXLC]+)[.\s—:]+\s*([A-Z][^\n]*)$", re.MULTILINE),
    re.compile(r"^([A-Z][A-Z\s]{5,})$", re.MULTILINE),
]


_PAGE_MARKER = "\n\n<<PAGE:{}>>\n\n"


def _read_pages(pdf_path: str) -> list[tuple[int, str]]:
    doc = fitz.open(pdf_path)
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        pages.append((page_num, text))
    doc.close()
    return pages


def _build_chapters_from_boundaries(
    pages: list[tuple[int, str]],
    boundaries: list[tuple[int, int, str]],
    source_name: str,
) -> list[Chapter]:
    if not boundaries:
        full_text = "\n\n".join(text for _, text in pages)
        return [
            Chapter(
                number=1,
                title=source_name,
                text=full_text,
                start_page=0,
                end_page=len(pages) - 1,
            )
        ]

    chapters = []
    for i, (start_page, ch_num, ch_title) in enumerate(boundaries):
        end_page = (
            boundaries[i + 1][0] - 1 if i + 1 < len(boundaries) else len(pages) - 1
        )
        chapter_text = "\n\n".join(
            text for page_idx, text in pages if start_page <= page_idx <= end_page
        )
        chapters.append(
            Chapter(
                number=ch_num,
                title=ch_title,
                text=chapter_text,
                start_page=start_page,
                end_page=end_page,
            )
        )

    return chapters


def _extract_default(pages: list[tuple[int, str]], source_name: str) -> list[Chapter]:
    boundaries = []
    chapter_counter = 0

    for page_idx, text in pages:
        header_zone = text[:500]

        for pattern in CHAPTER_PATTERNS:
            match = pattern.search(header_zone)
            if match:
                chapter_counter += 1
                title = match.group(0).strip()
                boundaries.append((page_idx, chapter_counter, title))
                break

    return _build_chapters_from_boundaries(pages, boundaries, source_name)


_PART_RE = re.compile(r"^\s*PART\s", re.IGNORECASE)
_CWF_CHAPTER_RE = re.compile(r"^\s*(\d{1,2})\s*\n")


def _extract_conversations_with_friends(
    pages: list[tuple[int, str]], source_name: str
) -> list[Chapter]:
    boundaries = []

    for page_idx, text in pages:
        if page_idx < 8 or page_idx >= len(pages) - 1:
            continue

        stripped = text.strip()
        if len(stripped) < 20:
            continue
        if _PART_RE.match(stripped):
            continue

        match = _CWF_CHAPTER_RE.match(text)
        if match:
            ch_num = int(match.group(1))
            if 1 <= ch_num <= 31:
                boundaries.append((page_idx, ch_num, f"Chapter {ch_num}"))

    return _build_chapters_from_boundaries(pages, boundaries, source_name)


_ROMAN_RE = re.compile(r"^\s*(I{1,3}|IV|V|VI{0,3})\s*$")
_ROMAN_TO_INT = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}


def _extract_heart_the_lover(
    pages: list[tuple[int, str]], source_name: str
) -> list[Chapter]:
    boundaries = []

    for page_idx, text in pages:
        if page_idx < 5:
            continue

        stripped = text.strip()
        if len(stripped) > 50:
            continue

        match = _ROMAN_RE.match(stripped)
        if match:
            numeral = match.group(1)
            part_num = _ROMAN_TO_INT.get(numeral, 0)
            if part_num > 0:
                content_start = page_idx + 1
                boundaries.append((content_start, part_num, f"Part {numeral}"))

    if not boundaries:
        return _build_chapters_from_boundaries(pages, [], source_name)

    last_page_idx = pages[-1][0]
    last_text = pages[-1][1].strip() if pages else ""
    if len(last_text) < 50 and not _ROMAN_RE.match(last_text):
        back_matter_page = last_page_idx
    else:
        back_matter_page = None

    chapters = []
    for i, (start_page, ch_num, ch_title) in enumerate(boundaries):
        if i + 1 < len(boundaries):
            end_page = boundaries[i + 1][0] - 2
        else:
            end_page = (back_matter_page - 1) if back_matter_page else last_page_idx

        chapter_text = "\n\n".join(
            text for pg, text in pages if start_page <= pg <= end_page
        )
        chapters.append(
            Chapter(
                number=ch_num,
                title=ch_title,
                text=chapter_text,
                start_page=start_page,
                end_page=end_page,
            )
        )

    return chapters


_BOOK_HEADER_RE = re.compile(r"^Book\s+(\d+):\s+(.+)$", re.MULTILINE)
_SUBSECTION_RE = re.compile(r"^\[Book\s+(\d+)\]\s*(\d+\.\d+)\s+(.+)$", re.MULTILINE)


def _extract_bildungsroman_notes(
    pages: list[tuple[int, str]], source_name: str
) -> list[Chapter]:
    page_marker_re = re.compile(r"<<PAGE:(\d+)>>")

    full_text_parts = []
    for page_idx, text in pages:
        full_text_parts.append(_PAGE_MARKER.format(page_idx))
        full_text_parts.append(text)
    full_text = "".join(full_text_parts)

    book_titles = {}

    sections = []
    for match in _BOOK_HEADER_RE.finditer(full_text):
        book_num = int(match.group(1))
        book_title = match.group(2).strip()
        book_titles[book_num] = book_title
        sections.append((match.start(), book_num, None, book_title, match.group(0)))

    for match in _SUBSECTION_RE.finditer(full_text):
        book_num = int(match.group(1))
        sub_id = match.group(2)
        sub_title = match.group(3).strip()
        sections.append((match.start(), book_num, sub_id, sub_title, match.group(0)))

    sections.sort(key=lambda s: s[0])

    def _page_at_offset(offset):
        last_page = 0
        for m in page_marker_re.finditer(full_text[:offset]):
            last_page = int(m.group(1))
        return last_page

    chapters = []
    ch_counter = 0

    first_section_offset = sections[0][0] if sections else len(full_text)
    intro_text = full_text[:first_section_offset]
    intro_text = page_marker_re.sub("", intro_text).strip()
    if intro_text:
        ch_counter += 1
        chapters.append(
            Chapter(
                number=ch_counter,
                title="Introduction",
                text=intro_text,
                start_page=0,
                end_page=_page_at_offset(first_section_offset),
            )
        )

    for i, (offset, book_num, sub_id, title, raw_line) in enumerate(sections):
        if i + 1 < len(sections):
            next_offset = sections[i + 1][0]
        else:
            next_offset = len(full_text)

        section_text = full_text[offset:next_offset]
        section_text = page_marker_re.sub("", section_text).strip()

        if sub_id is None and i + 1 < len(sections) and sections[i + 1][1] == book_num:
            if len(section_text) < 200:
                continue

        ch_counter += 1
        book_title = book_titles.get(book_num, f"Book {book_num}")
        if sub_id:
            ch_title = f"{book_title} — {sub_id} {title}"
        else:
            ch_title = book_title

        start_page = _page_at_offset(offset)
        end_page = (
            _page_at_offset(next_offset - 1) if next_offset > offset else start_page
        )

        chapters.append(
            Chapter(
                number=ch_counter,
                title=ch_title,
                text=section_text,
                start_page=start_page,
                end_page=end_page,
            )
        )

    if not chapters:
        return _build_chapters_from_boundaries(pages, [], source_name)

    return chapters


_STRATEGIES = {
    "conversations_with_friends": _extract_conversations_with_friends,
    "heart_the_lover": _extract_heart_the_lover,
    "bildungsroman_notes": _extract_bildungsroman_notes,
}


def extract_chapters(pdf_path: str, source_name: str) -> list[Chapter]:
    """
    Extract chapters from a PDF. Returns list of Chapter objects.

    Uses source_name to dispatch to a book-specific extraction strategy.
    Falls back to generic pattern matching for unknown sources.
    """
    pages = _read_pages(pdf_path)
    strategy = _STRATEGIES.get(source_name, _extract_default)
    return strategy(pages, source_name)
