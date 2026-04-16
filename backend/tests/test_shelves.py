import os
import shutil
from datetime import datetime

import pytest

from tools.shelves import DATA_DIR, ShelfStore, get_store, remove_store


@pytest.fixture(autouse=True)
def clean_shelf_files():
    yield
    if os.path.exists(DATA_DIR):
        shutil.rmtree(DATA_DIR)


class TestShelfStoreAddBook:
    def test_add_book_creates_shelf(self):
        store = ShelfStore("test-temp")
        store.add_book("favorites", "Normal People", "Sally Rooney")
        books = store.get_shelf("favorites")
        assert len(books) == 1
        assert books[0]["title"] == "Normal People"
        assert books[0]["author"] == "Sally Rooney"

    def test_add_book_appends_to_existing_shelf(self):
        store = ShelfStore("test-temp")
        store.add_book("favorites", "Normal People", "Sally Rooney")
        store.add_book("favorites", "The Namesake", "Jhumpa Lahiri")
        books = store.get_shelf("favorites")
        assert len(books) == 2

    def test_add_book_stores_all_metadata(self):
        store = ShelfStore("test-temp")
        store.add_book(
            "shelf", "Title", "Author", isbn="9781234567890", cover_url="http://img.jpg"
        )
        book = store.get_shelf("shelf")[0]
        assert book["title"] == "Title"
        assert book["author"] == "Author"
        assert book["isbn"] == "9781234567890"
        assert book["cover_url"] == "http://img.jpg"
        assert "added_at" in book

    def test_add_book_timestamp_is_valid_iso(self):
        store = ShelfStore("test-temp")
        store.add_book("shelf", "Title", "Author")
        ts = store.get_shelf("shelf")[0]["added_at"]
        parsed = datetime.fromisoformat(ts)
        assert parsed.year >= 2026


class TestShelfStoreRead:
    def test_get_shelf_nonexistent(self):
        store = ShelfStore("test-temp")
        assert store.get_shelf("nonexistent") == []

    def test_get_all_shelves_empty(self):
        store = ShelfStore("test-temp")
        assert store.get_all_shelves() == {}

    def test_get_all_shelves_multiple_shelves(self):
        store = ShelfStore("test-temp")
        store.add_book("a", "Book A", "Author A")
        store.add_book("b", "Book B", "Author B")
        store.add_book("c", "Book C", "Author C")
        shelves = store.get_all_shelves()
        assert len(shelves) == 3
        assert set(shelves.keys()) == {"a", "b", "c"}


class TestStoreRegistry:
    def test_get_store_creates_new(self):
        room = "test-registry-create"
        store = get_store(room)
        assert isinstance(store, ShelfStore)
        assert store.get_all_shelves() == {}
        remove_store(room)

    def test_get_store_returns_same_instance(self):
        room = "test-registry-same"
        store1 = get_store(room)
        store2 = get_store(room)
        assert store1 is store2
        remove_store(room)

    def test_different_rooms_are_isolated(self):
        room_a = "test-registry-a"
        room_b = "test-registry-b"
        store_a = get_store(room_a)
        store_b = get_store(room_b)
        store_a.add_book("shelf", "Book A", "Author A")
        assert store_b.get_all_shelves() == {}
        remove_store(room_a)
        remove_store(room_b)

    def test_remove_store_cleans_up(self):
        room = "test-registry-remove"
        store1 = get_store(room)
        store1.add_book("shelf", "Book", "Author")
        remove_store(room)
        store2 = get_store(room)
        assert store2.get_all_shelves() == {}
        remove_store(room)

    def test_remove_nonexistent_room_is_safe(self):
        remove_store("nonexistent-room")
