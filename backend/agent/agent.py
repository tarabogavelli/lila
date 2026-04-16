import asyncio
import json
import logging
import os
from pathlib import Path
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
from livekit.agents.llm import function_tool
from livekit.plugins import deepgram, elevenlabs, openai, silero, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

import tool_handlers as th
from tools.shelves import get_store, remove_store
from rag.query import (
    query_literary_knowledge,
    query_course_notes,
)

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

    @function_tool(description=_tool_descriptions["search_books"])
    async def search_books(self, query: str) -> str:
        await self._notify_tool_start("search_books")
        return await th.search_books(query)

    @function_tool(description=_tool_descriptions["add_to_shelf"])
    async def add_to_shelf(self, title: str, author: str, shelf_name: str) -> str:
        await self._notify_tool_start("add_to_shelf")
        result = await th.add_to_shelf(
            get_store(self.room_name), title, author, shelf_name
        )
        await self._notify_shelf_updated()
        return result

    @function_tool(description=_tool_descriptions["get_shelf"])
    async def get_shelf(self, shelf_name: str) -> str:
        await self._notify_tool_start("get_shelf")
        return await th.get_shelf(get_store(self.room_name), shelf_name)

    @function_tool(description=_tool_descriptions["list_shelves"])
    async def list_shelves(self) -> str:
        await self._notify_tool_start("list_shelves")
        return await th.list_shelves(get_store(self.room_name))

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
        return await th.fetch_goodreads_reviews(title, author)

    @function_tool(description=_tool_descriptions["rename_shelf"])
    async def rename_shelf(self, old_name: str, new_name: str) -> str:
        await self._notify_tool_start("rename_shelf")
        result = await th.rename_shelf(get_store(self.room_name), old_name, new_name)
        if result.startswith("Renamed"):
            await self._notify_shelf_updated()
        return result

    @function_tool(description=_tool_descriptions["remove_from_shelf"])
    async def remove_from_shelf(self, title: str, shelf_name: str) -> str:
        await self._notify_tool_start("remove_from_shelf")
        result = await th.remove_from_shelf(
            get_store(self.room_name), shelf_name, title
        )
        if result.startswith("Removed"):
            await self._notify_shelf_updated()
        return result


server = AgentServer()


@server.rtc_session()
async def entrypoint(ctx: agents.JobContext):
    from rag.query import _get_index, _get_course_index

    _get_index()
    _get_course_index()

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
                "Bildung",
                "Kazuo Ishiguro",
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

    async def cleanup_shelves():
        remove_store(room_name)

    ctx.add_shutdown_callback(cleanup_shelves)

    await session.say(
        text="Hi its Lila! What are you looking to read next?",
        allow_interruptions=True,
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
