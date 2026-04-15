# Lila — Personal Librarian Voice Agent

## What it is
Lila is a RAG-enabled voice agent built on LiveKit — a personal librarian
with the personality of a well-read, opinionated English major friend from college.
She knows your reading history, makes emotionally-aware recommendations,
manages dynamic bookshelves, and can answer detailed literary questions by
drawing on James Wood's "How Fiction Works" and Elena Ferrante's "Frantumaglia."

## Live Demo
- Frontend: [Vercel link — TBD]
- Backend: Hosted on AWS EC2 (the frontend connects to it automatically)

## System Architecture
```
User's browser → LiveKit Cloud (WebRTC) → Agent (EC2)
                                         ├── STT (Deepgram)
                                         ├── LLM (OpenAI gpt-5.4-mini)
                                         ├── TTS (OpenAI)
                                         ├── Tools: Google Books API, Bookshelf Store
                                         └── RAG: LlamaIndex + ChromaDB

Frontend (Vercel) → FastAPI (EC2) → /token (JWT generation)
                                  → /shelves (bookshelf state for UI)
```

## How RAG Works
1. Two PDFs ingested: How Fiction Works and Frantumaglia
2. **Chapter boundaries extracted** from PDFs using PyMuPDF regex detection
3. Each chapter becomes a LlamaIndex Document with metadata:
   `{source, title, author, chapter_number, chapter_title}`
4. Chunked using SentenceSplitter (512 tokens, 50 overlap) — chunks inherit chapter metadata
5. Embedded with OpenAI text-embedding-3-small
6. Stored in ChromaDB with chapter metadata filterable
7. Retrieved via LlamaIndex QueryEngine (similarity_top_k=5)
8. `query_literary_knowledge` is a @function_tool the LLM calls when literary questions arise
9. Responses include chapter-level source attribution

## Tools
| Tool | Description |
|------|-------------|
| `search_books` | Google Books API volume search |
| `fetch_book_reviews` | Google Books detailed info (ratings, description, cover) |
| `add_to_shelf` | Add book to named shelf (fetches cover first, saves to JSON) |
| `get_shelf` / `list_shelves` | Read shelf contents |
| `query_literary_knowledge_tool` | LlamaIndex RAG over both PDFs |

## Tech Stack
- LiveKit Cloud (room server) + LiveKit Agents SDK v1.5.x (voice pipeline)
- OpenAI gpt-5.4-mini (LLM)
- Deepgram (STT)
- OpenAI (TTS)
- Silero (VAD) + LiveKit Turn Detector
- LlamaIndex (RAG framework)
- ChromaDB (vector store)
- PyMuPDF (PDF chapter extraction)
- FastAPI (token server + shelves API)
- React 18 + Vite (frontend)
- AWS EC2 t3.small (backend) + Vercel (frontend)

## Local Setup

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Fill in API keys

# One-time PDF ingestion (place PDFs in backend/data/ first)
python -m rag.ingest

# Terminal 1: Start API server
uvicorn server:app --host 0.0.0.0 --port 8000

# Terminal 2: Start LiveKit agent
python agent.py dev

# Or: Text-only CLI (for testing tools & RAG without voice)
python cli.py
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env  # Set VITE_API_BASE_URL and VITE_LIVEKIT_URL
npm run dev
```

## AI Tools Used
- Claude (Anthropic) — plan authoring and code generation
- LiveKit Agent Builder — initial agent testing
