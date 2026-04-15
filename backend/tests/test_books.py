from unittest.mock import patch, AsyncMock, MagicMock

import httpx
import pytest

from tools.books import search_books_api, fetch_reviews_api


def _mock_httpx_response(json_data, status_code=200):
    response = MagicMock()
    response.json.return_value = json_data
    response.status_code = status_code
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=response
        )
    else:
        response.raise_for_status.return_value = None
    return response


def _make_client_mock(response):
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestSearchBooksApi:
    async def test_success(self, sample_google_books_response):
        response = _mock_httpx_response(sample_google_books_response)
        client = _make_client_mock(response)
        with patch("tools.books.httpx.AsyncClient", return_value=client):
            result = await search_books_api("Sally Rooney")

        assert result["totalItems"] == 3
        assert len(result["items"]) == 3

    async def test_passes_query_and_key(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_BOOKS_API_KEY", "test-key-123")
        response = _mock_httpx_response({"items": []})
        client = _make_client_mock(response)
        with patch("tools.books.httpx.AsyncClient", return_value=client):
            await search_books_api("test query")

        call_kwargs = client.get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert params["q"] == "test query"
        assert params["key"] == "test-key-123"
        assert params["maxResults"] == 5

    async def test_http_error_propagates(self):
        response = _mock_httpx_response({}, status_code=500)
        client = _make_client_mock(response)
        with patch("tools.books.httpx.AsyncClient", return_value=client):
            with pytest.raises(httpx.HTTPStatusError):
                await search_books_api("query")


class TestFetchReviewsApi:
    async def test_success(self, sample_book_detail_response):
        response = _mock_httpx_response(sample_book_detail_response)
        client = _make_client_mock(response)
        with patch("tools.books.httpx.AsyncClient", return_value=client):
            result = await fetch_reviews_api("The Namesake", "Jhumpa Lahiri")

        assert result["title"] == "The Namesake"
        assert result["authors"] == ["Jhumpa Lahiri"]
        assert result["averageRating"] == 4.2
        assert result["ratingsCount"] == 300
        assert result["isbn"] == "9780618485222"
        assert "edge=curl" not in result["coverUrl"]

    async def test_cover_url_cleanup(self):
        data = {
            "items": [
                {
                    "volumeInfo": {
                        "title": "Test",
                        "imageLinks": {
                            "thumbnail": "http://example.com?zoom=1&edge=curl"
                        },
                    }
                }
            ]
        }
        response = _mock_httpx_response(data)
        client = _make_client_mock(response)
        with patch("tools.books.httpx.AsyncClient", return_value=client):
            result = await fetch_reviews_api("Test", "Author")

        assert "edge=curl" not in result["coverUrl"]
        assert "zoom=0" in result["coverUrl"]
        assert "zoom=1" not in result["coverUrl"]

    async def test_no_items(self, empty_google_books_response):
        response = _mock_httpx_response(empty_google_books_response)
        client = _make_client_mock(response)
        with patch("tools.books.httpx.AsyncClient", return_value=client):
            result = await fetch_reviews_api("Nonexistent", "Nobody")

        assert result == {"error": "Book not found"}

    async def test_missing_optional_fields(self):
        data = {"items": [{"volumeInfo": {"title": "Bare"}}]}
        response = _mock_httpx_response(data)
        client = _make_client_mock(response)
        with patch("tools.books.httpx.AsyncClient", return_value=client):
            result = await fetch_reviews_api("Bare", "Author")

        assert result["coverUrl"] == ""
        assert result["isbn"] == ""
        assert result["averageRating"] is None
        assert result["authors"] == []
        assert result["description"] == "No description available"

    async def test_isbn_13_preferred(self):
        data = {
            "items": [
                {
                    "volumeInfo": {
                        "title": "Test",
                        "industryIdentifiers": [
                            {"type": "ISBN_10", "identifier": "1234567890"},
                            {"type": "ISBN_13", "identifier": "9781234567890"},
                        ],
                    }
                }
            ]
        }
        response = _mock_httpx_response(data)
        client = _make_client_mock(response)
        with patch("tools.books.httpx.AsyncClient", return_value=client):
            result = await fetch_reviews_api("Test", "Author")

        assert result["isbn"] == "9781234567890"

    async def test_no_isbn_13(self):
        data = {
            "items": [
                {
                    "volumeInfo": {
                        "title": "Test",
                        "industryIdentifiers": [
                            {"type": "ISBN_10", "identifier": "1234567890"},
                        ],
                    }
                }
            ]
        }
        response = _mock_httpx_response(data)
        client = _make_client_mock(response)
        with patch("tools.books.httpx.AsyncClient", return_value=client):
            result = await fetch_reviews_api("Test", "Author")

        assert result["isbn"] == ""
