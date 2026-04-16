from tools.books import fetch_reviews_api, search_books_api
from tools.goodreads import search_and_get_reviews


async def search_books(query: str) -> str:
    results = await search_books_api(query)
    if not results.get("items"):
        return "I couldn't find anything matching that. Could you be more specific?"
    books = []
    for item in results["items"][:3]:
        info = item.get("volumeInfo", {})
        title = info.get("title", "Unknown")
        authors = ", ".join(info.get("authors", ["Unknown"]))
        rating = info.get("averageRating", "no rating")
        books.append(f"'{title}' by {authors} (rating: {rating})")
    return "Found: " + "; ".join(books)


async def add_to_shelf(store, title: str, author: str, shelf_name: str) -> str:
    book_data = await fetch_reviews_api(title, author)
    cover_url = book_data.get("coverUrl", "")
    isbn = book_data.get("isbn", "")
    store.add_book(shelf_name, title, author, isbn, cover_url)
    return f"Added '{title}' by {author} to the '{shelf_name}' shelf."


async def get_shelf(store, shelf_name: str) -> str:
    books = store.get_shelf(shelf_name)
    if not books:
        return f"The '{shelf_name}' shelf is empty or doesn't exist."
    book_list = ", ".join([f"'{b['title']}' by {b['author']}" for b in books])
    return f"On '{shelf_name}': {book_list}"


async def list_shelves(store) -> str:
    shelves = store.get_all_shelves()
    if not shelves:
        return "No shelves yet. Shall I start one?"
    summary = []
    for name, books in shelves.items():
        count = len(books)
        summary.append(f"'{name}' ({count} book{'s' if count != 1 else ''})")
    return "Current shelves: " + ", ".join(summary)


async def fetch_goodreads_reviews(title: str, author: str) -> str:
    data = await search_and_get_reviews(title, author)
    if data.get("error"):
        return f"Couldn't get Goodreads reviews: {data['error']}"
    result = f"Goodreads: '{data.get('title')}' — {data.get('rating')}/5 ({data.get('ratings')} ratings)"
    genres = data.get("genres", [])
    if genres:
        result += f". Genres: {', '.join(genres[:3])}"
    reviews = data.get("reviews", [])
    if reviews:
        result += ". Top reviews: "
        snippets = []
        for r in reviews[:3]:
            snippets.append(f"{r['user']} ({r['rating']}/5): {r['text']}")
        result += " | ".join(snippets)
    return result


async def rename_shelf(store, old_name: str, new_name: str) -> str:
    success = store.rename_shelf(old_name, new_name)
    if not success:
        return f"Couldn't rename — either '{old_name}' doesn't exist or '{new_name}' is already taken."
    return f"Renamed shelf '{old_name}' to '{new_name}'."


async def remove_from_shelf(store, shelf_name: str, title: str) -> str:
    success = store.remove_book(shelf_name, title)
    if not success:
        return f"Couldn't find '{title}' on the '{shelf_name}' shelf."
    return f"Removed '{title}' from the '{shelf_name}' shelf."
