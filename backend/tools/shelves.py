from datetime import datetime, timezone


class ShelfStore:
    """In-memory bookshelf store scoped to a single conversation."""

    def __init__(self):
        self.shelves: dict[str, list[dict]] = {}

    def add_book(
        self,
        shelf_name: str,
        title: str,
        author: str,
        isbn: str = "",
        cover_url: str = "",
    ):
        if shelf_name not in self.shelves:
            self.shelves[shelf_name] = []

        book = {
            "title": title,
            "author": author,
            "isbn": isbn,
            "cover_url": cover_url,
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        self.shelves[shelf_name].append(book)

    def get_shelf(self, shelf_name: str) -> list[dict]:
        return self.shelves.get(shelf_name, [])

    def get_all_shelves(self) -> dict[str, list[dict]]:
        return self.shelves


_stores: dict[str, ShelfStore] = {}


def get_store(room: str) -> ShelfStore:
    if room not in _stores:
        _stores[room] = ShelfStore()
    return _stores[room]


def remove_store(room: str):
    _stores.pop(room, None)
