import asyncio
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

RAPID_API_KEY = os.getenv("RAPID_API_KEY")
BASE_URL = "https://goodreads-api-latest-updated.p.rapidapi.com"
HEADERS = {
    "X-RapidAPI-Key": RAPID_API_KEY,
    "X-RapidAPI-Host": "goodreads-api-latest-updated.p.rapidapi.com",
}


async def test_search(query: str):
    print(f"\n=== SEARCH: '{query}' ===")
    start = time.time()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{BASE_URL}/search", params={"q": query}, headers=HEADERS
        )
    elapsed = time.time() - start
    print(f"Status: {resp.status_code} | Latency: {elapsed:.2f}s")

    if resp.status_code != 200:
        print(f"Error: {resp.text[:200]}")
        return None

    data = resp.json()
    if isinstance(data, list):
        print(f"Results: {len(data)} books")
        for book in data[:3]:
            print(
                f"  - [{book.get('id')}] {book.get('title')} "
                f"by {book.get('author')} "
                f"(rating: {book.get('rating')}, {book.get('ratings')} ratings)"
            )
        return data[0].get("id") if data else None
    else:
        print(f"Unexpected response type: {type(data)}")
        return None


async def test_book_details(book_id: int):
    print(f"\n=== BOOK DETAILS: id={book_id} ===")
    start = time.time()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{BASE_URL}/books/{book_id}", headers=HEADERS)
    elapsed = time.time() - start
    print(f"Status: {resp.status_code} | Latency: {elapsed:.2f}s")

    if resp.status_code != 200:
        print(f"Error: {resp.text[:200]}")
        return

    data = resp.json()
    print(f"Title: {data.get('title')}")
    print(f"Rating: {data.get('rating')} ({data.get('ratings')} ratings)")
    print(f"Pages: {data.get('pages')}")
    print(f"Genres: {data.get('genres', [])[:5]}")
    print(f"ISBN: {data.get('ISBN')}")

    reviews = data.get("popularReviews", [])
    print(f"\nReviews: {len(reviews)} total")
    for r in reviews[:3]:
        body = r.get("body", "")
        snippet = body[:150] + "..." if len(body) > 150 else body
        print(
            f"  - [{r.get('rating')}/5, {r.get('likes')} likes] "
            f"by {r.get('user', {}).get('name', '?')}: {snippet}"
        )


async def main():
    if not RAPID_API_KEY:
        print("ERROR: RAPID_API_KEY not set in .env")
        return

    book_id = await test_search("Normal People Sally Rooney")
    if book_id:
        await test_book_details(book_id)

    await test_search("How Fiction Works James Wood")


if __name__ == "__main__":
    asyncio.run(main())
