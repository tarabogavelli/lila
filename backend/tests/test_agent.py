from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from agent.agent import Lila


@pytest.fixture
def lila():
    return Lila("test-room")


def _make_volume_info(title="Book", authors=None, rating=None):
    info = {"title": title}
    if authors is not None:
        info["authors"] = authors
    if rating is not None:
        info["averageRating"] = rating
    return {"volumeInfo": info}


class TestSearchBooks:
    async def test_found(self, lila):
        api_response = {
            "items": [
                _make_volume_info("Book A", ["Author A"], 4.5),
                _make_volume_info("Book B", ["Author B"], 3.0),
                _make_volume_info("Book C", ["Author C"]),
            ]
        }
        with patch(
            "agent.agent.search_books_api",
            new_callable=AsyncMock,
            return_value=api_response,
        ):
            result = await lila.search_books("query")

        assert result.startswith("Found: ")
        assert "Book A" in result
        assert "Book B" in result
        assert "Book C" in result

    async def test_empty_items(self, lila):
        with patch(
            "agent.agent.search_books_api",
            new_callable=AsyncMock,
            return_value={"items": []},
        ):
            result = await lila.search_books("query")

        assert "couldn't find anything" in result.lower()

    async def test_no_items_key(self, lila):
        with patch(
            "agent.agent.search_books_api", new_callable=AsyncMock, return_value={}
        ):
            result = await lila.search_books("query")

        assert "couldn't find anything" in result.lower()

    async def test_limits_to_3(self, lila):
        items = [_make_volume_info(f"Book {i}", [f"Author {i}"]) for i in range(5)]
        with patch(
            "agent.agent.search_books_api",
            new_callable=AsyncMock,
            return_value={"items": items},
        ):
            result = await lila.search_books("query")

        assert "Book 0" in result
        assert "Book 2" in result
        assert "Book 3" not in result

    async def test_missing_author_and_rating(self, lila):
        api_response = {"items": [{"volumeInfo": {"title": "Mystery"}}]}
        with patch(
            "agent.agent.search_books_api",
            new_callable=AsyncMock,
            return_value=api_response,
        ):
            result = await lila.search_books("query")

        assert "Unknown" in result
        assert "no rating" in result


class TestFetchBookReviews:
    async def test_formatted(self, lila):
        review_data = {
            "title": "The Namesake",
            "authors": ["Jhumpa Lahiri"],
            "description": "A story.",
            "averageRating": 4.2,
            "ratingsCount": 300,
        }
        with patch(
            "agent.agent.fetch_reviews_api",
            new_callable=AsyncMock,
            return_value=review_data,
        ):
            result = await lila.fetch_book_reviews("The Namesake", "Jhumpa Lahiri")

        assert "The Namesake" in result
        assert "4.2/5" in result
        assert "300 ratings" in result

    async def test_no_rating(self, lila):
        review_data = {
            "title": "Unknown Book",
            "authors": ["Author"],
            "description": "Desc.",
            "averageRating": None,
        }
        with patch(
            "agent.agent.fetch_reviews_api",
            new_callable=AsyncMock,
            return_value=review_data,
        ):
            result = await lila.fetch_book_reviews("Unknown Book", "Author")

        assert "no ratings yet" in result

    async def test_truncates_long_description(self, lila):
        review_data = {
            "title": "Long",
            "authors": ["Author"],
            "description": "A" * 500,
            "averageRating": None,
        }
        with patch(
            "agent.agent.fetch_reviews_api",
            new_callable=AsyncMock,
            return_value=review_data,
        ):
            result = await lila.fetch_book_reviews("Long", "Author")

        assert result.endswith("...")
        assert "A" * 301 not in result

    async def test_error_response(self, lila):
        with patch(
            "agent.agent.fetch_reviews_api",
            new_callable=AsyncMock,
            return_value={"error": "Book not found"},
        ):
            result = await lila.fetch_book_reviews("Missing", "Nobody")

        assert "Couldn't find details" in result


class TestAddToShelf:
    async def test_success(self, lila):
        review_data = {
            "coverUrl": "http://img.jpg",
            "isbn": "9781234567890",
        }
        mock_store = MagicMock()
        with patch(
            "agent.agent.fetch_reviews_api",
            new_callable=AsyncMock,
            return_value=review_data,
        ):
            with patch("agent.agent.get_store", return_value=mock_store):
                result = await lila.add_to_shelf("Title", "Author", "My Shelf")

        mock_store.add_book.assert_called_once_with(
            "My Shelf", "Title", "Author", "9781234567890", "http://img.jpg"
        )
        assert "Title" in result
        assert "My Shelf" in result

    async def test_missing_cover(self, lila):
        review_data = {"isbn": "123"}
        mock_store = MagicMock()
        with patch(
            "agent.agent.fetch_reviews_api",
            new_callable=AsyncMock,
            return_value=review_data,
        ):
            with patch("agent.agent.get_store", return_value=mock_store):
                await lila.add_to_shelf("Title", "Author", "Shelf")

        call_args = mock_store.add_book.call_args
        assert call_args[0][4] == ""


class TestGetShelf:
    async def test_with_books(self, lila):
        books = [
            {"title": "Book A", "author": "Author A"},
            {"title": "Book B", "author": "Author B"},
        ]
        mock_store = MagicMock()
        mock_store.get_shelf.return_value = books
        with patch("agent.agent.get_store", return_value=mock_store):
            result = await lila.get_shelf("favorites")

        assert "Book A" in result
        assert "Book B" in result

    async def test_empty(self, lila):
        mock_store = MagicMock()
        mock_store.get_shelf.return_value = []
        with patch("agent.agent.get_store", return_value=mock_store):
            result = await lila.get_shelf("empty")

        assert "empty or doesn't exist" in result


class TestListShelves:
    async def test_pluralization(self, lila):
        shelves_data = {
            "Single": [{"title": "A"}],
            "Multiple": [{"title": "B"}, {"title": "C"}],
        }
        mock_store = MagicMock()
        mock_store.get_all_shelves.return_value = shelves_data
        with patch("agent.agent.get_store", return_value=mock_store):
            result = await lila.list_shelves()

        assert "'Single' (1 book)" in result
        assert "'Multiple' (2 books)" in result

    async def test_empty(self, lila):
        mock_store = MagicMock()
        mock_store.get_all_shelves.return_value = {}
        with patch("agent.agent.get_store", return_value=mock_store):
            result = await lila.list_shelves()

        assert "No shelves yet" in result


class TestQueryLiteraryKnowledge:
    async def test_passthrough(self, lila):
        expected = "Free indirect style is a technique...\n\n[Sources: How Fiction Works, Chapter 1]"
        with patch(
            "agent.agent.query_literary_knowledge",
            new_callable=AsyncMock,
            return_value=expected,
        ):
            result = await lila.query_literary_knowledge_tool(
                "What is free indirect style?"
            )

        assert result == expected
