import json
import os
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
from dotenv import load_dotenv

from tools.shelves import get_store

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "data", "sessions")

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/token")
async def get_token(room: str = "", participant: str = "user"):
    """Generate a LiveKit room token."""
    if not room:
        room = f"lila-{uuid.uuid4().hex[:8]}"

    token = (
        api.AccessToken()
        .with_identity(participant)
        .with_name("User")
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .to_jwt()
    )

    return {"token": token, "url": os.getenv("LIVEKIT_URL"), "room": room}


@app.get("/shelves")
async def get_shelves(room: str = ""):
    """Return bookshelves for a specific room/conversation."""
    if not room:
        return {}
    return get_store(room).get_all_shelves()


@app.get("/sessions")
async def list_sessions():
    """List all saved session reports."""
    if not os.path.exists(SESSIONS_DIR):
        return []
    files = sorted(os.listdir(SESSIONS_DIR), reverse=True)
    return [f.replace(".json", "") for f in files if f.endswith(".json")]


@app.get("/sessions/{room_name}")
async def get_session(room_name: str):
    """Get a specific session report."""
    filepath = os.path.join(SESSIONS_DIR, f"{room_name}.json")
    if not os.path.exists(filepath):
        return {"error": "Session not found"}
    with open(filepath) as f:
        return json.load(f)
