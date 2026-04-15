"""
Text-only CLI for testing Lila's tool calls and RAG.
Run: python cli.py
"""

import asyncio
import json
import re
from pathlib import Path

import yaml
from dotenv import load_dotenv
from openai import AsyncOpenAI

from tools.books import search_books_api, fetch_reviews_api
from tools.shelves import ShelfStore
from rag.query import query_literary_knowledge

load_dotenv()

MODEL = "gpt-5.4-mini"
_cli_shelf_store = ShelfStore()

_config_path = Path(__file__).parent / "agent" / "agent_config.yaml"
with open(_config_path) as f:
    _config = yaml.safe_load(f)

_voice_line = (
    "You are a voice agent — keep responses conversational, spoken-word natural.\n"
    "  No bullet points, no lists. Talk like a person."
)

SYSTEM_PROMPT = re.sub(
    re.escape(_voice_line),
    _config["system_prompt_text_mode_override"].strip(),
    _config["system_prompt"],
).strip()

TOOLS = _config["tools"]


CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_tool_call(name, args):
    args_str = ", ".join(f'{k}="{v}"' for k, v in args.items())
    print(f"{YELLOW}  [tool] {name}({args_str}){RESET}")


def print_tool_result(result):
    print(f"{DIM}{GREEN}  [result] {result}{RESET}")


def print_lila(text):
    print(f"\n{CYAN}{BOLD}Lila:{RESET} {CYAN}{text}{RESET}\n")


async def handle_search_books(query: str) -> str:
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


async def handle_fetch_book_reviews(title: str, author: str) -> str:
    data = await fetch_reviews_api(title, author)
    if data.get("error"):
        return f"Couldn't find details for '{title}' by {author}."
    rating_str = (
        f"{data['averageRating']}/5 ({data['ratingsCount']} ratings)"
        if data.get("averageRating")
        else "no ratings yet"
    )
    desc = data.get("description", "No description available.")
    if len(desc) > 300:
        desc = desc[:300] + "..."
    return (
        f"'{data['title']}' by {', '.join(data.get('authors', []))}. "
        f"Rating: {rating_str}. {desc}"
    )


async def handle_add_to_shelf(title: str, author: str, shelf_name: str) -> str:
    book_data = await fetch_reviews_api(title, author)
    cover_url = book_data.get("coverUrl", "")
    isbn = book_data.get("isbn", "")
    _cli_shelf_store.add_book(shelf_name, title, author, isbn, cover_url)
    return f"Added '{title}' by {author} to the '{shelf_name}' shelf."


async def handle_get_shelf(shelf_name: str) -> str:
    books = _cli_shelf_store.get_shelf(shelf_name)
    if not books:
        return f"The '{shelf_name}' shelf is empty or doesn't exist."
    book_list = ", ".join([f"'{b['title']}' by {b['author']}" for b in books])
    return f"On '{shelf_name}': {book_list}"


async def handle_list_shelves() -> str:
    shelves = _cli_shelf_store.get_all_shelves()
    if not shelves:
        return "No shelves yet. Shall I start one?"
    summary = []
    for name, books in shelves.items():
        count = len(books)
        summary.append(f"'{name}' ({count} book{'s' if count != 1 else ''})")
    return "Current shelves: " + ", ".join(summary)


async def handle_query_literary_knowledge(question: str) -> str:
    return await query_literary_knowledge(question)


TOOL_HANDLERS = {
    "search_books": handle_search_books,
    "fetch_book_reviews": handle_fetch_book_reviews,
    "add_to_shelf": handle_add_to_shelf,
    "get_shelf": handle_get_shelf,
    "list_shelves": handle_list_shelves,
    "query_literary_knowledge": handle_query_literary_knowledge,
}


async def run_cli():
    client = AsyncOpenAI()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print(f"\n{BOLD}Lila CLI{RESET} — text mode for testing tools & RAG")
    print(f"{DIM}Type 'quit' to exit{RESET}\n")

    while True:
        try:
            user_input = input(f"{BOLD}You: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        messages.append({"role": "user", "content": user_input})

        while True:
            try:
                response = await client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                )
            except Exception as e:
                print(f"{YELLOW}[error] API call failed: {e}{RESET}")
                messages.pop()
                break

            choice = response.choices[0]

            if choice.message.tool_calls:
                messages.append(choice.message)

                for tool_call in choice.message.tool_calls:
                    fn_name = tool_call.function.name
                    try:
                        fn_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}

                    print_tool_call(fn_name, fn_args)

                    handler = TOOL_HANDLERS.get(fn_name)
                    if handler is None:
                        result = f"Unknown tool: {fn_name}"
                    else:
                        try:
                            result = await handler(**fn_args)
                        except Exception as e:
                            result = f"Tool error: {e}"

                    print_tool_result(result)

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result,
                        }
                    )

                continue

            assistant_text = choice.message.content or ""
            messages.append({"role": "assistant", "content": assistant_text})
            print_lila(assistant_text)
            break


if __name__ == "__main__":
    asyncio.run(run_cli())
