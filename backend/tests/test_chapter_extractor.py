from unittest.mock import patch

from rag.chapter_extractor import (
    extract_chapters,
    Chapter,
    _clean_text,
    _extract_conversations_with_friends,
    _extract_heart_the_lover,
    _extract_bildungsroman_notes,
    _STRATEGIES,
)


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


class TestStrategyDispatch:
    def test_conversations_dispatched(self):
        assert (
            _STRATEGIES["conversations_with_friends"]
            is _extract_conversations_with_friends
        )

    def test_heart_the_lover_dispatched(self):
        assert _STRATEGIES["heart_the_lover"] is _extract_heart_the_lover

    def test_bildungsroman_dispatched(self):
        assert _STRATEGIES["bildungsroman_notes"] is _extract_bildungsroman_notes

    def test_unknown_source_uses_default(self, mock_fitz_doc):
        pages = [(0, "Chapter 1: Intro\nBody text.")]
        doc = mock_fitz_doc(pages)
        with patch("rag.chapter_extractor.fitz.open", return_value=doc):
            chapters = extract_chapters("/fake.pdf", "some_unknown_book")
        assert len(chapters) == 1
        assert "Intro" in chapters[0].title


class TestConversationsStrategy:
    def test_skips_front_matter(self):
        pages = [
            (0, ""),
            (1, ""),
            (2, ""),
            (3, ""),
            (4, "SALLY ROONEY\nConversations with Friends"),
            (5, "In times of crisis..."),
            (6, "Contents\nTitle Page\n1\n2\n3"),
            (7, "20\n21\nAcknowledgements"),
            (8, "PART ONE"),
            (9, "1\nBobbi and I first met Melissa at a poetry night."),
            (10, "More chapter 1 text continuing."),
            (11, "2\nIt rained all day before we went for dinner."),
        ]
        chapters = _extract_conversations_with_friends(
            pages, "conversations_with_friends"
        )
        assert chapters[0].number == 1
        assert chapters[0].title == "Chapter 1"
        assert chapters[0].start_page == 9

    def test_skips_part_dividers(self):
        pages = [(i, "") for i in range(8)]
        pages += [
            (8, "PART ONE"),
            (9, "1\nChapter one text here."),
            (10, "PART TWO"),
            (11, "2\nChapter two text here."),
            (12, "Copyright 2017."),
        ]
        chapters = _extract_conversations_with_friends(
            pages, "conversations_with_friends"
        )
        assert len(chapters) == 2
        assert chapters[0].number == 1
        assert chapters[1].number == 2

    def test_skips_copyright_last_page(self):
        pages = [(i, "") for i in range(8)]
        pages += [
            (8, "PART ONE"),
            (9, "1\nFirst chapter text."),
            (10, "Copyright 2017 by Faber.\nAll rights reserved."),
        ]
        chapters = _extract_conversations_with_friends(
            pages, "conversations_with_friends"
        )
        assert len(chapters) == 1
        assert chapters[0].number == 1

    def test_correct_chapter_count(self):
        pages = [(i, "") for i in range(9)]
        for ch in range(1, 32):
            pages.append((8 + ch, f"{ch}\nText for chapter {ch}."))
        pages.append((40, "Copyright page."))
        chapters = _extract_conversations_with_friends(
            pages, "conversations_with_friends"
        )
        assert len(chapters) == 31
        assert chapters[0].number == 1
        assert chapters[-1].number == 31


class TestHeartTheLoverStrategy:
    def test_detects_three_parts(self):
        pages = [(i, "") for i in range(10)]
        pages[5] = (5, "Title page text with lots of content " * 5)
        pages += [
            (10, "I"),
            (11, "Content of part one. " * 20),
            (12, "More part one. " * 20),
            (97, "End of part one. " * 20),
            (98, "II"),
            (99, "Content of part two. " * 20),
            (117, "End of part two. " * 20),
            (118, "III"),
            (119, "Content of part three. " * 20),
            (180, "End of part three. " * 20),
            (181, "OceanofPDF.com"),
        ]
        chapters = _extract_heart_the_lover(pages, "heart_the_lover")
        assert len(chapters) == 3
        assert chapters[0].title == "Part I"
        assert chapters[0].start_page == 11
        assert chapters[1].title == "Part II"
        assert chapters[1].start_page == 99
        assert chapters[2].title == "Part III"
        assert chapters[2].start_page == 119
        assert chapters[2].end_page == 180

    def test_skips_front_matter(self):
        pages = [
            (0, ""),
            (1, ""),
            (2, "Heart\nthe\nLover"),
            (3, ""),
            (10, "I"),
            (11, "Content starts here. " * 20),
        ]
        chapters = _extract_heart_the_lover(pages, "heart_the_lover")
        assert len(chapters) == 1
        assert chapters[0].start_page == 11

    def test_fallback_when_no_numerals(self):
        pages = [
            (0, "Some regular text that is long enough. " * 5),
            (1, "More regular text. " * 5),
        ]
        chapters = _extract_heart_the_lover(pages, "heart_the_lover")
        assert len(chapters) == 1
        assert chapters[0].title == "heart_the_lover"


class TestBildungsromanStrategy:
    def test_intro_section_created(self):
        pages = [
            (0, "Bildungsroman Lecture Notes\nGeneral intro text."),
            (1, "More intro material."),
            (2, "Book 7: The Woman Warrior\nSome text."),
        ]
        chapters = _extract_bildungsroman_notes(pages, "bildungsroman_notes")
        assert chapters[0].title == "Introduction"
        assert "General intro text" in chapters[0].text

    def test_subsections_split_on_same_page(self):
        pages = [
            (
                0,
                "Book 5: Sula\n[Book 5] 5.1 Toni Morrison\nBio text.\n[Book 5] 5.2 Why Sula?\nReason text.",
            ),
        ]
        chapters = _extract_bildungsroman_notes(pages, "bildungsroman_notes")
        titles = [ch.title for ch in chapters]
        assert any("5.1 Toni Morrison" in t for t in titles)
        assert any("5.2 Why Sula?" in t for t in titles)
        toni_ch = [ch for ch in chapters if "5.1" in ch.title][0]
        assert "Bio text" in toni_ch.text
        assert "Reason text" not in toni_ch.text

    def test_book_title_in_metadata(self):
        pages = [
            (
                0,
                "Book 3: The Metamorphosis\nIntro.\n[Book 3] 3.1 Overview\nOverview text.",
            ),
        ]
        chapters = _extract_bildungsroman_notes(pages, "bildungsroman_notes")
        sub = [ch for ch in chapters if "3.1" in ch.title][0]
        assert "The Metamorphosis" in sub.title

    def test_book_without_subsections(self):
        pages = [
            (0, "Book 1: Père Goriot\nBalzac sees capitalism as zero sum game."),
        ]
        chapters = _extract_bildungsroman_notes(pages, "bildungsroman_notes")
        assert any("Père Goriot" in ch.title for ch in chapters)

    def test_fallback_when_no_tags(self):
        pages = [
            (0, "Just regular notes without any tags."),
            (1, "More untagged content."),
        ]
        chapters = _extract_bildungsroman_notes(pages, "bildungsroman_notes")
        assert len(chapters) == 1
        assert chapters[0].title == "Introduction"


class TestCleanText:
    def test_joins_mid_paragraph_line_break(self):
        text = "the quick brown\nfox jumped over"
        assert _clean_text(text) == "the quick brown fox jumped over"

    def test_preserves_paragraph_boundary_after_period(self):
        text = "end of sentence.\nNew paragraph starts here."
        assert _clean_text(text) == "end of sentence.\n\nNew paragraph starts here."

    def test_preserves_paragraph_boundary_after_question_mark(self):
        text = "really?\nYes indeed."
        assert _clean_text(text) == "really?\n\nYes indeed."

    def test_preserves_existing_double_newline(self):
        text = "paragraph one.\n\nParagraph two."
        assert _clean_text(text) == text

    def test_preserves_colon_boundary(self):
        text = "the following:\nfirst item"
        assert _clean_text(text) == "the following:\n\nfirst item"

    def test_joins_multiple_consecutive_wraps(self):
        text = "this is a very long\nsentence that wraps\nacross three lines."
        assert (
            _clean_text(text)
            == "this is a very long sentence that wraps across three lines."
        )

    def test_preserves_dialogue(self):
        text = "she said.\nI know, he replied."
        assert _clean_text(text) == "she said.\n\nI know, he replied."

    def test_handles_empty_string(self):
        assert _clean_text("") == ""

    def test_handles_single_line(self):
        assert _clean_text("just one line") == "just one line"

    def test_joins_across_page_boundary(self):
        text = "like I did with many other\n\n\npeople, that while I was talking"
        assert (
            _clean_text(text)
            == "like I did with many other people, that while I was talking"
        )

    def test_preserves_real_paragraph_across_page_boundary(self):
        text = "end of chapter.\n\n\nNew chapter begins here."
        assert _clean_text(text) == "end of chapter.\n\nNew chapter begins here."
