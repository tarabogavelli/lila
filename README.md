# Lila — Voice Book Companion

Lila is a voice agent that feels like calling a well-read friend. She's 23, an opinionated English major who has read everything — and she knows *your* reading history, your moods, and what you're likely to love next.
She and the user took a class together in college: **BILDUNGSROMAN: The Coming-of-Age Novel**. Lila has a perfect memory of those lecture notes, so you can talk through the books, themes, and the professor's analysis — and use that lens to think about what to read next.

## System Architecture

```
Browser → LiveKit Cloud (WebRTC) → Agent (EC2)
                                  ├── STT (speech-to-text)
                                  ├── LLM (language model)
                                  ├── TTS (text-to-speech)
                                  ├── Tools: Google Books, Goodreads, Shelf Store
                                  └── RAG: LlamaIndex + ChromaDB

Frontend (Vercel) → FastAPI (EC2) → /token  (LiveKit room JWT)
                                  → /shelves (bookshelf state for UI)
```

The browser connects to LiveKit Cloud over WebRTC. LiveKit routes audio to the agent running on EC2, which runs a voice pipeline (STT → LLM → TTS). The agent publishes tool-call events back to the room so the frontend can update the bookshelf panel in real time.

## Agent Design

The agent is implemented using **LiveKit Agents SDK v1.x**. `Lila` subclasses `Agent` and each capability is a `@function_tool` method — the LLM decides autonomously when to call them based on the conversation.

Key design decisions:
- **Room-scoped shelf state**: each conversation gets its own JSON file (`data/shelves/{room}.json`), so shelf data is isolated per session and cleaned up on disconnect
- **Real-time UI sync**: when a shelf changes, the agent publishes a `shelf_updated` event to the LiveKit room data channel; the frontend listens and polls `/shelves` to refresh the bookshelf panel
- **RAG as a tool**: literary knowledge is surfaced via explicit tool calls (`query_literary_knowledge`, `query_course_notes`) rather than injected into every prompt — keeps context clean and lets the LLM decide when to consult sources
- **Text CLI**: `cli.py` runs the same tool/prompt stack without voice, useful for testing agent, RAG and tool behavior

## RAG Integration

Two ChromaDB collections:

| Collection | Contents |
|---|---|
| `lila_library` | *Conversations with Friends* (Sally Rooney) + *Heart the Lover* (Lily King) |
| `bildungsroman_notes` | Columbia Bildungsroman course lecture notes |

**Ingestion pipeline** (pre-built and included in the repo; only needed if adding new PDFs):
1. PDFs parsed with PyMuPDF
2. Chapter boundaries detected via regex (e.g. "Chapter N", ALL-CAPS titles)
3. Each chapter → LlamaIndex `Document` with metadata: `{source, title, author, chapter_number, chapter_title}`
4. Chunked with `SentenceSplitter` (768 tokens, 128 overlap for library, subsections are chunks for notes) — chunks inherit chapter metadata
5. Embedded and stored in ChromaDB


**Query-time**:
- Top 15 chunks retrieved by similarity search
- Reranked to top 5 via CohereRerank
- Responses include chapter-level source attribution (e.g. `[Conversations with Friends, Chapter 3 ('July')]`)
- Optional metadata filtering: questions mentioning "chapter X" filter by chapter number; each collection filtered by source

## Tools

| Tool | Description |
|------|-------------|
| `search_books` | Google Books API search by title/author |
| `fetch_goodreads_reviews` | Real reader reviews + ratings from Goodreads |
| `add_to_shelf` | Add book to a named shelf (auto-fetches cover art) |
| `get_shelf` / `list_shelves` | Read shelf contents |
| `rename_shelf` / `remove_from_shelf` | Shelf management |
| `query_literary_knowledge` | RAG over *Conversations with Friends* + *Heart the Lover* |
| `query_course_notes` | RAG over Bildungsroman course lecture notes |

## Tech Stack

- **LiveKit Cloud** + **LiveKit Agents SDK v1.5** — WebRTC room server + voice pipeline
- **STT / LLM / TTS** — configurable via `.env` (see `.env.example` for defaults)
- **LlamaIndex** — RAG framework (document ingestion, chunking, querying)
- **ChromaDB** — persistent vector store
- **PyMuPDF** — PDF parsing + chapter boundary extraction
- **CohereRerank** — retrieval reranking
- **FastAPI** — token server + shelves API
- **React 18 + Vite** — frontend
- **AWS EC2** (backend) + **Vercel** (frontend)

## Local Setup

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in API keys
```

Start the servers:

```bash
# Terminal 1: API server
uvicorn server:app --host 0.0.0.0 --port 8000

# Terminal 2: LiveKit agent
python -m agent.agent dev

# Optional: text-only CLI (no voice, good for testing)
python cli.py
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env          # set VITE_API_BASE_URL and VITE_LIVEKIT_URL
npm run dev
```

## Deployment

### Backend on AWS EC2

#### 1. Launch an EC2 instance

- AMI: Amazon Linux 2023
- Instance type: `t3.small` (or larger)
- Security group: allow SSH (port 22) from your IP
- Note the Public IPv4 address

#### 2. Run the setup script

```bash
ssh -i your-key.pem ec2-user@<EC2-PUBLIC-IP>

curl -O https://raw.githubusercontent.com/<your-user>/lila/main/deploy/ec2-setup.sh
bash ec2-setup.sh https://github.com/<your-user>/lila.git
```

This installs Python, clones the repo, creates a virtualenv, installs dependencies, and configures systemd services.

#### 3. Fill in API keys

```bash
nano /home/ec2-user/lila/backend/.env
```

#### 4. Start services

```bash
sudo systemctl start lila-api lila-agent
```

#### 5. Set up HTTPS via Cloudflare Tunnel

The frontend is served over HTTPS (Vercel), so the backend needs HTTPS too.
Cloudflare Quick Tunnel handles this for free — no domain or SSL certs needed.

```bash
bash /home/ec2-user/lila/deploy/setup-tunnel.sh
```

The script prints your HTTPS URL (e.g. `https://something-random.trycloudflare.com`).
Note: the URL changes if the tunnel restarts — update `VITE_API_BASE_URL` in Vercel if that happens.

#### Useful commands

```bash
journalctl -u lila-agent -f       # Agent logs
journalctl -u lila-api -f         # API logs
cat /tmp/cloudflared.log           # Tunnel logs

bash /home/ec2-user/lila/deploy/deploy.sh   # Restart after code changes
```

### Frontend on Vercel

1. Import the `lila` repo at [vercel.com](https://vercel.com)
2. Set **Root Directory** to `frontend`
3. Add environment variable: `VITE_API_BASE_URL` → your Cloudflare tunnel URL
4. Deploy — every push to `main` auto-deploys

## AI Tools Used

- Claude Code (Anthropic) — planning and code generation
