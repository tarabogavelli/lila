from unittest.mock import patch

from rag.chapter_extractor import extract_chapters, Chapter


class TestChapterDataclass:
    def test_fields(self):
        ch = Chapter(number=1, title="Test", text="body", start_page=0, end_page=5)
        assert ch.number == 1
        assert ch.title == "Test"
        assert ch.text == "body"
        assert ch.start_page == 0
        assert ch.end_page == 5


class TestExtractChaptersPatterns:
    def test_pattern_chapter_word(self, mock_fitz_doc):
        pages = [
            (0, "Chapter One: Narrating\nSome text about narrating fiction."),
            (1, "More text continuing the discussion."),
            (2, "Chapter Two: Detail\nText about the role of detail."),
            (3, "Continuation of detail discussion."),
        ]
        doc = mock_fitz_doc(pages)
        with patch("rag.chapter_extractor.fitz.open", return_value=doc):
            chapters = extract_chapters("/fake.pdf", "test")

        assert len(chapters) == 2
        assert chapters[0].number == 1
        assert "Narrating" in chapters[0].title
        assert chapters[0].start_page == 0
        assert chapters[0].end_page == 1
        assert chapters[1].number == 2
        assert "Detail" in chapters[1].title
        assert chapters[1].start_page == 2
        assert chapters[1].end_page == 3

    def test_pattern_roman_numeral(self, mock_fitz_doc):
        pages = [
            (0, "IV. THE LETTER\nContent about letters and correspondence."),
        ]
        doc = mock_fitz_doc(pages)
        with patch("rag.chapter_extractor.fitz.open", return_value=doc):
            chapters = extract_chapters("/fake.pdf", "test")

        assert len(chapters) == 1
        assert chapters[0].number == 1

    def test_pattern_all_caps_title(self, mock_fitz_doc):
        pages = [
            (0, "FRANTUMAGLIA\nThis is the opening section about her concept."),
        ]
        doc = mock_fitz_doc(pages)
        with patch("rag.chapter_extractor.fitz.open", return_value=doc):
            chapters = extract_chapters("/fake.pdf", "test")

        assert len(chapters) == 1
        assert "FRANTUMAGLIA" in chapters[0].title

    def test_fallback_no_patterns_match(self, mock_fitz_doc):
        pages = [
            (0, "Just some regular body text here."),
            (1, "More regular text with no chapter headers."),
        ]
        doc = mock_fitz_doc(pages)
        with patch("rag.chapter_extractor.fitz.open", return_value=doc):
            chapters = extract_chapters("/fake.pdf", "my_source")

        assert len(chapters) == 1
        assert chapters[0].number == 1
        assert chapters[0].title == "my_source"
        assert chapters[0].start_page == 0
        assert chapters[0].end_page == 1


class TestExtractChaptersPageGrouping:
    def test_text_concatenation_across_pages(self, mock_fitz_doc):
        pages = [
            (0, "Chapter One: Intro\nPage zero text."),
            (1, "Page one continuation."),
            (2, "Chapter Two: Next\nPage two text."),
        ]
        doc = mock_fitz_doc(pages)
        with patch("rag.chapter_extractor.fitz.open", return_value=doc):
            chapters = extract_chapters("/fake.pdf", "test")

        assert "Page zero text." in chapters[0].text
        assert "Page one continuation." in chapters[0].text
        assert "Page two text." in chapters[1].text
        assert "Page one continuation." not in chapters[1].text

    def test_single_page_pdf(self, mock_fitz_doc):
        pages = [(0, "Chapter 1: Only Chapter\nAll the content.")]
        doc = mock_fitz_doc(pages)
        with patch("rag.chapter_extractor.fitz.open", return_value=doc):
            chapters = extract_chapters("/fake.pdf", "test")

        assert len(chapters) == 1
        assert chapters[0].start_page == 0
        assert chapters[0].end_page == 0

    def test_multiple_chapters(self, mock_fitz_doc):
        pages = [
            (0, "Chapter 1: First\nText."),
            (1, "Chapter 2: Second\nText."),
            (2, "Chapter 3: Third\nText."),
        ]
        doc = mock_fitz_doc(pages)
        with patch("rag.chapter_extractor.fitz.open", return_value=doc):
            chapters = extract_chapters("/fake.pdf", "test")

        assert len(chapters) == 3
        assert chapters[0].start_page == 0
        assert chapters[0].end_page == 0
        assert chapters[1].start_page == 1
        assert chapters[2].end_page == 2


class TestExtractChaptersEdgeCases:
    def test_header_zone_500_char_limit(self, mock_fitz_doc):
        padding = "x" * 600
        pages = [(0, padding + "\nChapter 1: Hidden\nText.")]
        doc = mock_fitz_doc(pages)
        with patch("rag.chapter_extractor.fitz.open", return_value=doc):
            chapters = extract_chapters("/fake.pdf", "fallback_source")

        assert len(chapters) == 1
        assert chapters[0].title == "fallback_source"

    def test_header_within_zone(self, mock_fitz_doc):
        padding = "x" * 400
        pages = [(0, padding + "\nChapter 1: Visible\nText.")]
        doc = mock_fitz_doc(pages)
        with patch("rag.chapter_extractor.fitz.open", return_value=doc):
            chapters = extract_chapters("/fake.pdf", "test")

        assert len(chapters) == 1
        assert "Visible" in chapters[0].title

    def test_first_pattern_wins(self, mock_fitz_doc):
        pages = [(0, "Chapter One: NARRATING STORIES\nBody text.")]
        doc = mock_fitz_doc(pages)
        with patch("rag.chapter_extractor.fitz.open", return_value=doc):
            chapters = extract_chapters("/fake.pdf", "test")

        assert len(chapters) == 1
        assert "Chapter One" in chapters[0].title

    def test_empty_page_text(self, mock_fitz_doc):
        pages = [(0, ""), (1, "")]
        doc = mock_fitz_doc(pages)
        with patch("rag.chapter_extractor.fitz.open", return_value=doc):
            chapters = extract_chapters("/fake.pdf", "empty")

        assert len(chapters) == 1
        assert chapters[0].title == "empty"
