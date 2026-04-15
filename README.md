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
python -m agent.agent dev

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

## Deployment

### Backend on AWS EC2

All deployment scripts are in `deploy/`.

#### 1. Launch an EC2 instance

- Go to AWS Console > EC2 > Launch Instance
- **AMI**: Amazon Linux 2023
- **Instance type**: `t3.medium` (2 vCPU, 4GB RAM)
- **Key pair**: Create or select one (you'll need this to SSH in)
- **Security group**: Create a new one with these inbound rules:
  - SSH (port 22) from your IP
  - Custom TCP (port 8000) from anywhere (0.0.0.0/0) — this is the API port
- Launch the instance and note the **Public IPv4 address**

#### 2. SSH in and run the setup script

```bash
ssh -i your-key.pem ec2-user@<EC2-PUBLIC-IP>

# Download and run the setup script (replace with your repo URL)
curl -O https://raw.githubusercontent.com/<your-user>/lila/main/deploy/ec2-setup.sh
bash ec2-setup.sh https://github.com/<your-user>/lila.git
```

This installs Python, clones the repo, creates a virtualenv, installs dependencies,
and configures systemd services.

#### 3. Fill in API keys

```bash
nano /home/ec2-user/lila/backend/.env
```

Fill in all the keys from `.env.example` (LiveKit, OpenAI, Deepgram, Google Books).

#### 4. Copy PDFs and run RAG ingestion

```bash
# From your local machine, copy PDFs to EC2:
scp -i your-key.pem backend/data/*.pdf ec2-user@<EC2-PUBLIC-IP>:/home/ec2-user/lila/backend/data/

# On EC2, run ingestion:
cd /home/ec2-user/lila/backend
source .venv/bin/activate
python -m rag.ingest
```

#### 5. Start the services

```bash
sudo systemctl start lila-api lila-agent
```

#### 6. Verify

```bash
# Check both services are running
sudo systemctl status lila-api lila-agent

# Test the API
curl http://localhost:8000/token
```

You should see JSON with a token. From your local machine, also test:
```bash
curl http://<EC2-PUBLIC-IP>:8000/token
```

#### Useful commands

```bash
# View live logs
journalctl -u lila-agent -f    # Agent logs
journalctl -u lila-api -f      # API server logs

# Restart after code changes
bash /home/ec2-user/lila/deploy/deploy.sh

# Stop services
sudo systemctl stop lila-api lila-agent
```

### Frontend on Vercel

#### 1. Connect your repo

- Go to [vercel.com](https://vercel.com) and sign in with GitHub
- Click "Add New Project" and import your `lila` repository

#### 2. Configure the project

- **Root Directory**: Set to `frontend`
- **Framework Preset**: Vite (auto-detected)
- **Build Command**: `npm run build` (auto-detected)

#### 3. Set the environment variable

In Vercel project settings > Environment Variables, add:

| Name | Value |
|------|-------|
| `VITE_API_BASE_URL` | `http://<EC2-PUBLIC-IP>:8000` |

Replace `<EC2-PUBLIC-IP>` with your EC2 instance's public IP address.

#### 4. Deploy

Click "Deploy". Vercel builds and hosts the frontend. Every push to `main`
auto-deploys.

#### 5. Verify end-to-end

Open the Vercel URL in your browser, click "Call Lila", and confirm:
- Lila greets you (audio works)
- You can speak and she responds (STT + LLM + TTS works)
- Ask her to add a book to a shelf (tool calls work, bookshelf panel updates)
- Ask a question about How Fiction Works (RAG works)

## AI Tools Used
- Claude (Anthropic) — plan authoring and code generation
- LiveKit Agent Builder — initial agent testing
