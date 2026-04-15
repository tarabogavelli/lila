"""
Extract chapter-annotated text from PDFs using PyMuPDF.
Handles both 'How Fiction Works' and 'Frantumaglia' chapter structures.
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


def extract_chapters(pdf_path: str, source_name: str) -> list[Chapter]:
    """
    Extract chapters from a PDF. Returns list of Chapter objects.

    Strategy:
    1. Extract full text per page.
    2. Scan for chapter header patterns.
    3. Group consecutive pages between chapter headers.

    If no chapters detected, fall back to treating the whole document as one chapter.
    """
    doc = fitz.open(pdf_path)
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        pages.append((page_num, text))
    doc.close()

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
