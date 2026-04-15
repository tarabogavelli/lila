from unittest.mock import patch, MagicMock

from rag.query import query_literary_knowledge


class TestQueryLiteraryKnowledge:
    async def test_formats_response_with_sources(self, mock_query_response):
        response = mock_query_response(
            "Free indirect style blends narrator and character voice.",
            [
                {
                    "title": "How Fiction Works",
                    "chapter_number": 1,
                    "chapter_title": "Narrating",
                },
                {
                    "title": "How Fiction Works",
                    "chapter_number": 3,
                    "chapter_title": "Flaubert and Modern Narrative",
                },
            ],
        )
        mock_engine = MagicMock()
        mock_engine.query.return_value = response

        with patch("rag.query.get_query_engine", return_value=mock_engine):
            result = await query_literary_knowledge("What is free indirect style?")

        assert "Free indirect style" in result
        assert "[Sources:" in result
        assert "How Fiction Works, Chapter 1 ('Narrating')" in result
        assert (
            "How Fiction Works, Chapter 3 ('Flaubert and Modern Narrative')" in result
        )

    async def test_no_sources_fallback(self, mock_query_response):
        response = mock_query_response("Some answer.", [])
        mock_engine = MagicMock()
        mock_engine.query.return_value = response

        with patch("rag.query.get_query_engine", return_value=mock_engine):
            result = await query_literary_knowledge("question")

        assert "[Sources: my reading]" in result

    async def test_deduplicates_sources(self, mock_query_response):
        same_meta = {
            "title": "How Fiction Works",
            "chapter_number": 1,
            "chapter_title": "Narrating",
        }
        response = mock_query_response("Answer.", [same_meta, same_meta])
        mock_engine = MagicMock()
        mock_engine.query.return_value = response

        with patch("rag.query.get_query_engine", return_value=mock_engine):
            result = await query_literary_knowledge("question")

        sources_section = result.split("[Sources: ")[1].rstrip("]")
        assert sources_section.count("Chapter 1") == 1

    async def test_missing_chapter_title(self, mock_query_response):
        response = mock_query_response(
            "Answer.",
            [{"title": "Frantumaglia", "chapter_number": 5, "chapter_title": ""}],
        )
        mock_engine = MagicMock()
        mock_engine.query.return_value = response

        with patch("rag.query.get_query_engine", return_value=mock_engine):
            result = await query_literary_knowledge("question")

        assert "Frantumaglia, Chapter 5" in result
        assert "('" not in result.split("[Sources:")[1]

    async def test_missing_metadata_fields(self, mock_query_response):
        response = mock_query_response("Answer.", [{}])
        mock_engine = MagicMock()
        mock_engine.query.return_value = response

        with patch("rag.query.get_query_engine", return_value=mock_engine):
            result = await query_literary_knowledge("question")

        assert "Unknown, Chapter ?" in result
