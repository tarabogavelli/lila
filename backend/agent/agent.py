import asyncio
import json
import logging
import os
from pathlib import Path
import time
import yaml
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import (
    AgentServer,
    AgentSession,
    Agent,
    TurnHandlingOptions,
    room_io,
)
from livekit.agents.llm import function_tool, ChatContext, ChatMessage
from livekit.plugins import deepgram, elevenlabs, openai, silero, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from tools.books import search_books_api, fetch_reviews_api
from tools.goodreads import search_and_get_reviews
from tools.shelves import get_store, remove_store
from rag.query import (
    query_literary_knowledge,
    query_course_notes,
    retrieve_course_chunks,
)

load_dotenv()
logger = logging.getLogger("lila")

_config_path = Path(__file__).parent / "agent_config.yaml"
with open(_config_path) as f:
    _config = yaml.safe_load(f)

_tool_descriptions = {
    t["function"]["name"]: t["function"]["description"] for t in _config["tools"]
}

COURSE_KEYWORDS = {
    "bildungsroman",
    "bildung",
    "coming of age",
    "coming-of-age",
    "sharon marcus",
    "professor marcus",
    "the course",
    "our class",
    "lecture",
    "pere goriot",
    "balzac",
    "jane eyre",
    "bronte",
    "go tell it on the mountain",
    "james baldwin",
    "sula",
    "toni morrison",
    "never let me go",
    "kazuo ishiguro",
    "woman warrior",
    "maxine hong kingston",
    "maria or the wrongs of woman",
    "wollstonecraft",
    "metamorphosis",
    "kafka",
    "spiritual development",
}


class Lila(Agent):
    def __init__(self, room_name: str) -> None:
        super().__init__(instructions=_config["system_prompt"])
        self.room_name = room_name
        self._room = None

    async def _notify_tool_start(self, tool_name: str) -> None:
        if self._room:
            payload = json.dumps({"type": "tool_start", "name": tool_name})
            try:
                await self._room.local_participant.publish_data(
                    payload, topic="tool_status"
                )
            except Exception:
                logger.debug("Failed to publish tool_start for %s", tool_name)

    async def _notify_shelf_updated(self) -> None:
        if self._room:
            try:
                await self._room.local_participant.publish_data(
                    json.dumps({"event": "shelf_updated"}),
                    topic="shelf_updated",
                )
            except Exception:
                logger.debug("Failed to publish shelf_updated")

    def _looks_course_related(self, text: str) -> bool:
        lower = text.lower()
        return any(kw in lower for kw in COURSE_KEYWORDS)

    async def on_user_turn_completed(
        self, turn_ctx: ChatContext, new_message: ChatMessage
    ) -> None:
        user_text = (
            new_message.text_content if hasattr(new_message, "text_content") else ""
        )
        if not user_text:
            return

        try:
            if self._looks_course_related(user_text):
                chunks = await retrieve_course_chunks(user_text, top_k=3)
                if chunks:
                    context_str = "\n\n".join(chunks)
                    turn_ctx.add_message(
                        role="system",
                        content=(
                            "Relevant context from your Bildungsroman course notes:\n\n"
                            + context_str
                        ),
                    )
        except Exception:
            logger.warning(
                "Failed to retrieve RAG chunks in on_user_turn_completed", exc_info=True
            )

    @function_tool(description=_tool_descriptions["search_books"])
    async def search_books(self, query: str) -> str:
        await self._notify_tool_start("search_books")
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

    @function_tool(description=_tool_descriptions["add_to_shelf"])
    async def add_to_shelf(self, title: str, author: str, shelf_name: str) -> str:
        await self._notify_tool_start("add_to_shelf")
        book_data = await fetch_reviews_api(title, author)
        cover_url = book_data.get("coverUrl", "")
        isbn = book_data.get("isbn", "")

        get_store(self.room_name).add_book(shelf_name, title, author, isbn, cover_url)
        await self._notify_shelf_updated()
        return f"Added '{title}' by {author} to the '{shelf_name}' shelf."

    @function_tool(description=_tool_descriptions["get_shelf"])
    async def get_shelf(self, shelf_name: str) -> str:
        await self._notify_tool_start("get_shelf")
        books = get_store(self.room_name).get_shelf(shelf_name)
        if not books:
            return f"The '{shelf_name}' shelf is empty or doesn't exist."
        book_list = ", ".join([f"'{b['title']}' by {b['author']}" for b in books])
        return f"On '{shelf_name}': {book_list}"

    @function_tool(description=_tool_descriptions["list_shelves"])
    async def list_shelves(self) -> str:
        await self._notify_tool_start("list_shelves")
        shelves = get_store(self.room_name).get_all_shelves()
        if not shelves:
            return "No shelves yet"
        summary = []
        for name, books in shelves.items():
            count = len(books)
            summary.append(f"'{name}' ({count} book{'s' if count != 1 else ''})")
        return "Current shelves: " + ", ".join(summary)

    @function_tool(description=_tool_descriptions["query_literary_knowledge"])
    async def query_literary_knowledge_tool(self, question: str) -> str:
        await self._notify_tool_start("query_literary_knowledge")
        return await query_literary_knowledge(question)

    @function_tool(description=_tool_descriptions["query_course_notes"])
    async def query_course_notes_tool(self, question: str) -> str:
        await self._notify_tool_start("query_course_notes")
        return await query_course_notes(question)

    @function_tool(description=_tool_descriptions["fetch_goodreads_reviews"])
    async def fetch_goodreads_reviews(self, title: str, author: str) -> str:
        await self._notify_tool_start("fetch_goodreads_reviews")
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

    @function_tool(description=_tool_descriptions["rename_shelf"])
    async def rename_shelf(self, old_name: str, new_name: str) -> str:
        await self._notify_tool_start("rename_shelf")
        success = get_store(self.room_name).rename_shelf(old_name, new_name)
        if not success:
            return f"Couldn't rename — either '{old_name}' doesn't exist or '{new_name}' is already taken."
        await self._notify_shelf_updated()
        return f"Renamed shelf '{old_name}' to '{new_name}'."

    @function_tool(description=_tool_descriptions["remove_from_shelf"])
    async def remove_from_shelf(self, title: str, shelf_name: str) -> str:
        await self._notify_tool_start("remove_from_shelf")
        success = get_store(self.room_name).remove_book(shelf_name, title)
        if not success:
            return f"Couldn't find '{title}' on the '{shelf_name}' shelf."
        await self._notify_shelf_updated()
        return f"Removed '{title}' from the '{shelf_name}' shelf."


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: agents.JobContext):
    from rag.query import get_course_query_engine, get_query_engine

    get_query_engine()
    get_course_query_engine()

    await ctx.connect()

    session = AgentSession(
        stt=deepgram.STT(
            model="nova-3",
            language="en",
            keyterm=[
                "Elena Ferrante",
                "Ferrante",
                "Sally Rooney",
                "Rooney",
                "Jhumpa Lahiri",
                "Lahiri",
                "Bildungsroman",
                "BildungKazuo Ishiguro",
                "Ishiguro",
                "Balzac",
                "Neapolitan",
                "Patchett",
                "Elif Batuman",
                "Batuman",
                "Amor Towles",
                "Towles",
                "Sharon Marcus",
            ],
            smart_format=True,
        ),
        llm=openai.LLM(model="gpt-5.4-mini"),
        tts=elevenlabs.TTS(
            model="eleven_flash_v2_5",
            voice_id=os.getenv("ELEVENLABS_VOICE_ID", "l7kNoIfnJKPg7779LI2t"),
        ),
        vad=silero.VAD.load(),
        turn_handling=TurnHandlingOptions(
            turn_detection=MultilingualModel(), interruption={"mode": "adaptive"}
        ),
    )

    room_name = ctx.room.name
    lila = Lila(room_name)

    room_options = room_io.RoomOptions(
        audio_input=room_io.AudioInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await session.start(
        agent=lila,
        room=ctx.room,
        room_options=room_options,
        record=True,
    )

    lila._room = ctx.room

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
        payload = json.dumps(
            {
                "type": "tool_done",
                "tools": [c.name for c in ev.function_calls],
            }
        )
        asyncio.ensure_future(
            ctx.room.local_participant.publish_data(payload, topic="tool_status")
        )

    @session.on("user_input_transcribed")
    def on_user_transcribed(ev):
        if ev.is_final:
            logger.info("user_said | %s", ev.transcript)

    async def save_session_report():
        report = ctx.make_session_report(session)
        report_dict = report.to_dict()
        timestamp = time.time()

        sessions_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sessions")
        os.makedirs(sessions_dir, exist_ok=True)
        filepath = os.path.join(sessions_dir, f"{ctx.room.name}_{timestamp}.json")

        with open(filepath, "w") as f:
            json.dump(report_dict, f, indent=2, default=str)

        logger.info("session_report_saved | %s", filepath)

    async def cleanup_shelves():
        remove_store(room_name)

    ctx.add_shutdown_callback(save_session_report)
    ctx.add_shutdown_callback(cleanup_shelves)

    await session.say(
        text="Hi its Lila! What are you looking to read next?",
        allow_interruptions=True,
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
