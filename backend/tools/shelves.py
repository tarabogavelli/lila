import json
import os
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "shelves")


class ShelfStore:
    """Bookshelf store scoped to a single conversation, persisted to JSON."""

    def __init__(self, room: str):
        self.room = room
        self._path = os.path.join(DATA_DIR, f"{room}.json")
        self.shelves: dict[str, list[dict]] = {}
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            with open(self._path) as f:
                self.shelves = json.load(f)

    def _save(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self.shelves, f, indent=2)

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
        self._save()

    def get_shelf(self, shelf_name: str) -> list[dict]:
        self._load()
        return self.shelves.get(shelf_name, [])

    def remove_book(self, shelf_name: str, title: str) -> bool:
        if shelf_name not in self.shelves:
            return False
        before = len(self.shelves[shelf_name])
        self.shelves[shelf_name] = [
            b for b in self.shelves[shelf_name] if b["title"].lower() != title.lower()
        ]
        if len(self.shelves[shelf_name]) == before:
            return False
        if not self.shelves[shelf_name]:
            del self.shelves[shelf_name]
        self._save()
        return True

    def rename_shelf(self, old_name: str, new_name: str) -> bool:
        if old_name not in self.shelves:
            return False
        if new_name in self.shelves:
            return False
        self.shelves[new_name] = self.shelves.pop(old_name)
        self._save()
        return True

    def get_all_shelves(self) -> dict[str, list[dict]]:
        self._load()
        return self.shelves


_stores: dict[str, ShelfStore] = {}


def get_store(room: str) -> ShelfStore:
    if room not in _stores:
        _stores[room] = ShelfStore(room)
    return _stores[room]


def remove_store(room: str):
    store = _stores.pop(room, None)
    if store and os.path.exists(store._path):
        os.remove(store._path)
