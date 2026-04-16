from unittest.mock import patch, MagicMock, AsyncMock


from rag.query import (
    query_literary_knowledge,
    query_course_notes,
    _build_filters,
    _format_chunks,
)


def _make_node(text, metadata=None):
    node = MagicMock()
    node.text = text
    node.metadata = metadata or {}
    return node


class TestBuildFilters:
    def test_literary_book_match(self):
        filters = _build_filters(
            "What happens in Conversations with Friends?", "lila_library"
        )
        assert filters is not None
        assert len(filters.filters) == 1
        assert filters.filters[0].key == "source"
        assert filters.filters[0].value == "conversations_with_friends"

    def test_literary_author_match(self):
        filters = _build_filters(
            "Tell me about Lily King's writing style", "lila_library"
        )
        assert filters is not None
        assert filters.filters[0].value == "heart_the_lover"

    def test_course_book_match(self):
        filters = _build_filters("What did we learn about Sula?", "bildungsroman_notes")
        assert filters is not None
        assert filters.filters[0].key == "book_title"
        assert filters.filters[0].value == "Sula"

    def test_chapter_number_match(self):
        filters = _build_filters(
            "What happens in chapter 5 of Conversations with Friends?", "lila_library"
        )
        assert filters is not None
        assert len(filters.filters) == 2
        source_filter = [f for f in filters.filters if f.key == "source"][0]
        ch_filter = [f for f in filters.filters if f.key == "chapter_number"][0]
        assert source_filter.value == "conversations_with_friends"
        assert ch_filter.value == 5

    def test_no_match_returns_none(self):
        filters = _build_filters("What is the meaning of life?", "lila_library")
        assert filters is None

    def test_unknown_collection_returns_none(self):
        filters = _build_filters("anything", "unknown_collection")
        assert filters is None


class TestFormatChunks:
    def test_formats_with_metadata(self):
        nodes = [
            _make_node(
                "Some literary text.",
                {
                    "title": "Conversations with Friends",
                    "chapter_number": 3,
                    "chapter_title": "Chapter 3",
                },
            )
        ]
        result = _format_chunks(nodes)
        assert "[Conversations with Friends, Chapter 3 ('Chapter 3')]" in result
        assert "Some literary text." in result

    def test_multiple_chunks_separated(self):
        nodes = [
            _make_node("First chunk.", {"title": "Book A", "chapter_number": 1}),
            _make_node("Second chunk.", {"title": "Book B", "chapter_number": 2}),
        ]
        result = _format_chunks(nodes)
        assert "---" in result
        assert "First chunk." in result
        assert "Second chunk." in result

    def test_empty_nodes(self):
        result = _format_chunks([])
        assert result == "No relevant passages found."

    def test_missing_metadata(self):
        nodes = [_make_node("Text.", {})]
        result = _format_chunks(nodes)
        assert "Unknown, Chapter ?" in result


class TestQueryLiteraryKnowledge:
    async def test_returns_formatted_chunks(self):
        nodes = [
            _make_node(
                "Bobbi and I first met Melissa.",
                {
                    "title": "Conversations with Friends",
                    "chapter_number": 1,
                    "chapter_title": "Chapter 1",
                },
            )
        ]
        mock_retriever = MagicMock()
        mock_retriever.aretrieve = AsyncMock(return_value=nodes)

        mock_reranker = MagicMock()
        mock_reranker.postprocess_nodes.return_value = nodes

        mock_index = MagicMock()
        mock_index.as_retriever.return_value = mock_retriever

        with (
            patch("rag.query._get_index", return_value=mock_index),
            patch("rag.query._get_reranker", return_value=mock_reranker),
        ):
            result = await query_literary_knowledge("Who is Melissa?")

        assert "Conversations with Friends" in result
        assert "Bobbi and I first met Melissa" in result
        mock_reranker.postprocess_nodes.assert_called_once()

    async def test_no_results(self):
        mock_retriever = MagicMock()
        mock_retriever.aretrieve = AsyncMock(return_value=[])

        mock_reranker = MagicMock()
        mock_reranker.postprocess_nodes.return_value = []

        mock_index = MagicMock()
        mock_index.as_retriever.return_value = mock_retriever

        with (
            patch("rag.query._get_index", return_value=mock_index),
            patch("rag.query._get_reranker", return_value=mock_reranker),
        ):
            result = await query_literary_knowledge("Something obscure?")

        assert result == "No relevant passages found."


class TestQueryCourseNotes:
    async def test_returns_formatted_chunks(self):
        nodes = [
            _make_node(
                "Sula represents nihilist bildung.",
                {
                    "title": "Bildungsroman Course Notes",
                    "chapter_number": 23,
                    "chapter_title": "Sula — 5.1 Toni Morrison",
                },
            )
        ]
        mock_retriever = MagicMock()
        mock_retriever.aretrieve = AsyncMock(return_value=nodes)

        mock_reranker = MagicMock()
        mock_reranker.postprocess_nodes.return_value = nodes

        mock_index = MagicMock()
        mock_index.as_retriever.return_value = mock_retriever

        with (
            patch("rag.query._get_course_index", return_value=mock_index),
            patch("rag.query._get_reranker", return_value=mock_reranker),
        ):
            result = await query_course_notes("What did we discuss about Sula?")

        assert "Sula represents nihilist bildung" in result
        assert "Bildungsroman Course Notes" in result
