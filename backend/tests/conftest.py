import sys
import os
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def sample_google_books_response():
    return {
        "kind": "books#volumes",
        "totalItems": 3,
        "items": [
            {
                "volumeInfo": {
                    "title": "Normal People",
                    "authors": ["Sally Rooney"],
                    "averageRating": 4.0,
                    "ratingsCount": 150,
                    "description": "A novel about two people.",
                    "imageLinks": {
                        "thumbnail": "http://books.google.com/books?id=abc&zoom=1&edge=curl"
                    },
                    "industryIdentifiers": [
                        {"type": "ISBN_10", "identifier": "1984822179"},
                        {"type": "ISBN_13", "identifier": "9781984822178"},
                    ],
                }
            },
            {
                "volumeInfo": {
                    "title": "Conversations with Friends",
                    "authors": ["Sally Rooney"],
                    "averageRating": 3.8,
                    "description": "Another novel.",
                }
            },
            {
                "volumeInfo": {
                    "title": "Beautiful World, Where Are You",
                    "authors": ["Sally Rooney"],
                }
            },
        ],
    }


@pytest.fixture
def sample_book_detail_response():
    return {
        "kind": "books#volumes",
        "totalItems": 1,
        "items": [
            {
                "volumeInfo": {
                    "title": "The Namesake",
                    "authors": ["Jhumpa Lahiri"],
                    "description": "A story of identity and belonging.",
                    "averageRating": 4.2,
                    "ratingsCount": 300,
                    "imageLinks": {
                        "thumbnail": "http://books.google.com/books?id=xyz&zoom=1&edge=curl"
                    },
                    "industryIdentifiers": [
                        {"type": "ISBN_10", "identifier": "0618485228"},
                        {"type": "ISBN_13", "identifier": "9780618485222"},
                    ],
                }
            }
        ],
    }


@pytest.fixture
def empty_google_books_response():
    return {"kind": "books#volumes", "totalItems": 0}


@pytest.fixture
def mock_fitz_doc():
    def _factory(pages):
        doc = MagicMock()
        doc.__len__ = MagicMock(return_value=len(pages))

        page_mocks = {}
        for page_num, text in pages:
            page_mock = MagicMock()
            page_mock.get_text.return_value = text
            page_mocks[page_num] = page_mock

        def getitem(idx):
            return page_mocks[idx]

        doc.__getitem__ = MagicMock(side_effect=getitem)
        doc.close = MagicMock()
        return doc

    return _factory


@pytest.fixture(autouse=True)
def reset_query_engine():
    yield
    import rag.query as qmod

    qmod._index = None
    qmod._course_index = None
    qmod._reranker = None
