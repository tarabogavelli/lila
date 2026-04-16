import os
import asyncio
import logging

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("lila")

BASE_URL = "https://goodreads-api-latest-updated.p.rapidapi.com"
RAPID_API_KEY = os.getenv("RAPID_API_KEY", "")

HEADERS = {
    "X-RapidAPI-Key": RAPID_API_KEY,
    "X-RapidAPI-Host": "goodreads-api-latest-updated.p.rapidapi.com",
}


async def search_goodreads(query: str) -> dict:
    if not RAPID_API_KEY:
        return {"error": "RAPID_API_KEY not configured"}

    async with httpx.AsyncClient(timeout=8) as client:
        resp = await client.get(
            f"{BASE_URL}/search",
            params={"q": query},
            headers=HEADERS,
        )
        if resp.status_code == 429:
            return {"error": "Rate limit exceeded"}
        resp.raise_for_status()
        results = resp.json()

    if not isinstance(results, list) or not results:
        return {"error": "No results found"}

    best = None
    for item in results:
        title = (item.get("title") or "").lower()
        if "analysis" in title or "summary" in title or "guide" in title:
            continue
        best = item
        break

    if not best:
        best = results[0]

    return {
        "id": best.get("id"),
        "title": best.get("title"),
        "author": best.get("author"),
        "rating": best.get("rating"),
        "ratings": best.get("ratings"),
        "imageUrl": best.get("smallImageURL", ""),
    }


async def fetch_goodreads_reviews(book_id: int, retries: int = 2) -> dict:
    if not RAPID_API_KEY:
        return {"error": "RAPID_API_KEY not configured"}

    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{BASE_URL}/books/{book_id}",
                    headers=HEADERS,
                )
                if resp.status_code == 429:
                    return {"error": "Rate limit exceeded"}
                if resp.status_code == 500:
                    if attempt < retries:
                        await asyncio.sleep(1.5)
                        continue
                    return {"error": "Goodreads temporarily unavailable"}
                resp.raise_for_status()
                data = resp.json()
                break
        except httpx.HTTPError:
            if attempt < retries:
                await asyncio.sleep(1.5)
                continue
            return {"error": "Failed to fetch from Goodreads"}

    reviews = data.get("popularReviews", [])
    top_reviews = []
    for r in reviews[:5]:
        body = r.get("body", "")
        if len(body) > 400:
            body = body[:400] + "..."
        top_reviews.append(
            {
                "user": r.get("user", {}).get("name", "Anonymous"),
                "rating": r.get("rating"),
                "likes": r.get("likes", 0),
                "text": body,
            }
        )

    return {
        "title": data.get("title"),
        "rating": data.get("rating"),
        "ratings": data.get("ratings"),
        "genres": data.get("genres", [])[:5],
        "description": data.get("description", ""),
        "reviews": top_reviews,
    }


async def search_and_get_reviews(title: str, author: str) -> dict:
    search_result = await search_goodreads(f"{title} {author}")
    if search_result.get("error"):
        return search_result

    book_id = search_result.get("id")
    if not book_id:
        return {"error": "Could not find book on Goodreads"}

    return await fetch_goodreads_reviews(book_id)
