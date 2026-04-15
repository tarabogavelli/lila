import json
import logging
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentServer, AgentSession, Agent
from livekit.agents.llm import function_tool
from livekit.plugins import deepgram, openai, silero

from tools.books import search_books_api, fetch_reviews_api
from tools.shelves import get_store, remove_store
from rag.query import query_literary_knowledge

load_dotenv()
logger = logging.getLogger("lila")

_config_path = Path(__file__).parent / "agent_config.yaml"
with open(_config_path) as f:
    _config = yaml.safe_load(f)

_tool_descriptions = {
    t["function"]["name"]: t["function"]["description"] for t in _config["tools"]
}


class Lila(Agent):
    def __init__(self, room_name: str) -> None:
        super().__init__(instructions=_config["system_prompt"])
        self.room_name = room_name

    @function_tool(description=_tool_descriptions["search_books"])
    async def search_books(self, query: str) -> str:
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

    @function_tool(description=_tool_descriptions["fetch_book_reviews"])
    async def fetch_book_reviews(self, title: str, author: str) -> str:
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

    @function_tool(description=_tool_descriptions["add_to_shelf"])
    async def add_to_shelf(self, title: str, author: str, shelf_name: str) -> str:
        book_data = await fetch_reviews_api(title, author)
        cover_url = book_data.get("coverUrl", "")
        isbn = book_data.get("isbn", "")

        get_store(self.room_name).add_book(shelf_name, title, author, isbn, cover_url)
        return f"Added '{title}' by {author} to the '{shelf_name}' shelf."

    @function_tool(description=_tool_descriptions["get_shelf"])
    async def get_shelf(self, shelf_name: str) -> str:
        books = get_store(self.room_name).get_shelf(shelf_name)
        if not books:
            return f"The '{shelf_name}' shelf is empty or doesn't exist."
        book_list = ", ".join([f"'{b['title']}' by {b['author']}" for b in books])
        return f"On '{shelf_name}': {book_list}"

    @function_tool(description=_tool_descriptions["list_shelves"])
    async def list_shelves(self) -> str:
        shelves = get_store(self.room_name).get_all_shelves()
        if not shelves:
            return "No shelves yet. Shall I start one?"
        summary = []
        for name, books in shelves.items():
            count = len(books)
            summary.append(f"'{name}' ({count} book{'s' if count != 1 else ''})")
        return "Current shelves: " + ", ".join(summary)

    @function_tool(description=_tool_descriptions["query_literary_knowledge"])
    async def query_literary_knowledge_tool(self, question: str) -> str:
        return await query_literary_knowledge(question)


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()

    session = AgentSession(
        stt=deepgram.STT(),
        llm=openai.LLM(model="gpt-5.4-mini"),
        tts=openai.TTS(),
        vad=silero.VAD.load(),
    )

    room_name = ctx.room.name

    await session.start(
        agent=Lila(room_name),
        room=ctx.room,
        record=True,
    )

    @session.on("conversation_item_added")
    def on_conversation_item(ev):
        logger.info(
            "conversation | %s: %s",
            ev.item.role,
            ev.item.text_content,
        )

    @session.on("function_tools_executed")
    def on_tools_executed(ev):
        for call_info in ev.function_calls:
            logger.info(
                "tool_call | %s(%s)",
                call_info.name,
                call_info.arguments,
            )

    @session.on("user_input_transcribed")
    def on_user_transcribed(ev):
        if ev.is_final:
            logger.info("user_said | %s", ev.transcript)

    async def save_session_report():
        report = ctx.make_session_report(session)
        report_dict = report.to_dict()

        sessions_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        filepath = os.path.join(sessions_dir, f"{ctx.room.name}.json")

        with open(filepath, "w") as f:
            json.dump(report_dict, f, indent=2, default=str)

        logger.info("session_report_saved | %s", filepath)

    async def cleanup_shelves():
        remove_store(room_name)

    ctx.add_shutdown_callback(save_session_report)
    ctx.add_shutdown_callback(cleanup_shelves)

    await session.generate_reply(
        instructions="Greet the user warmly as Lila. Say something like What are you looking to read next?"
        "Keep it to 1-2 sentences, natural and friendly.",
        allow_interruptions=True,
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
