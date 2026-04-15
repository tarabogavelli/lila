import httpx
import os

GOOGLE_BOOKS_BASE = "https://www.googleapis.com/books/v1/volumes"


async def search_books_api(query: str) -> dict:
    """Search Google Books. Returns raw API response."""
    async with httpx.AsyncClient() as client:
        params = {
            "q": query,
            "maxResults": 5,
            "key": os.getenv("GOOGLE_BOOKS_API_KEY"),
        }
        response = await client.get(GOOGLE_BOOKS_BASE, params=params)
        response.raise_for_status()
        return response.json()


async def fetch_reviews_api(title: str, author: str) -> dict:
    """Fetch detailed info including rating, description, cover URL, ISBN."""
    query = f"intitle:{title} inauthor:{author}"
    async with httpx.AsyncClient() as client:
        params = {
            "q": query,
            "maxResults": 1,
            "key": os.getenv("GOOGLE_BOOKS_API_KEY"),
        }
        response = await client.get(GOOGLE_BOOKS_BASE, params=params)
        response.raise_for_status()
        data = response.json()

        if not data.get("items"):
            return {"error": "Book not found"}

        vol = data["items"][0]["volumeInfo"]
        cover_url = vol.get("imageLinks", {}).get("thumbnail", "")
        if cover_url:
            cover_url = cover_url.replace("&edge=curl", "").replace("zoom=1", "zoom=0")

        return {
            "title": vol.get("title"),
            "authors": vol.get("authors", []),
            "description": vol.get("description", "No description available"),
            "averageRating": vol.get("averageRating"),
            "ratingsCount": vol.get("ratingsCount"),
            "coverUrl": cover_url,
            "isbn": next(
                (
                    id["identifier"]
                    for id in vol.get("industryIdentifiers", [])
                    if id["type"] == "ISBN_13"
                ),
                "",
            ),
        }
