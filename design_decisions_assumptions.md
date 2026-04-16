# Design Decisions & Assumptions

## 1. RAG Pipeline

### Framework: LlamaIndex over LangChain

- LlamaIndex was chosen over LangChain because its retriever abstraction maps directly to the retrieval-only pattern used here. 
- The pipeline retrieves and reranks chunks, then hands them to the voice agent's LLM for synthesis — there is no separate LLM synthesis step within the RAG pipeline itself. 
- LangChain's chain-based orchestration adds indirection that is unnecessary for this pattern. LlamaIndex also has useful ChromaDB integration via `llama-index-vector-stores-chroma` with native metadata filtering support.

### Vector Store: ChromaDB over FAISS or Pinecone

- ChromaDB was chosen for its native metadata filtering. 
- The grading criteria specify chapter-specific questions, so being able to filter by `chapter_number` and `source` at the vector store level (not post-retrieval) is critical for precision. 
- FAISS has no metadata filtering — it would require a post-retrieval filter step that wastes retrieval slots on irrelevant chunks. 
- Pinecone would work but adds a hosted dependency, network latency, and cost for what is a small corpus. 
- ChromaDB's `PersistentClient` gives disk persistence with zero infrastructure beyond the filesystem.

### Two Separate Collections

The system uses two ChromaDB collections: `lila_library` for the two literary works and `bildungsroman_notes` for course lecture notes. These corpora have fundamentally different characteristics:

- **Literary text** (`lila_library`): Chunked at 768 tokens with 128-token overlap. Literary arguments span multiple paragraphs, so larger chunks preserve coherent narrative blocks. Overlap prevents losing context at chunk boundaries, which matters for questions like "what happens at the end of chapter 5?" Metadata schema: `{source, title, author, chapter_number, chapter_title}`.
- **Course notes** (`bildungsroman_notes`): Chunked at 4096 tokens with zero overlap (though in reality most chunks are <1000 tokens since it's already split by section). Lecture notes are structured as discrete sections with clear boundaries, so large chunks preserve complete arguments. Zero overlap avoids redundant retrieval. Metadata schema adds `book_title` for filtering by course reading.

Separate collections prevent literary retrieval from being polluted with lecture note chunks and vice versa.

### Chapter-Aware Extraction

The `chapter_extractor.py` module (`backend/rag/chapter_extractor.py`) dispatches to book-specific extraction functions keyed by `source_name`. Each ingested work has a different chapter structure:

- **Conversations with Friends**: 31 Arabic numeral chapters (1–31). Regex detects numeric markers at the start of page text.
- **Heart, the Lover**: 6 Roman numeral parts (I–VI). Extraction handles back matter detection to avoid false positives.
- **Bildungsroman course notes**: `Book N:` headers with `[Book N] X.Y` subsections. Complex extraction tracks page boundaries with markers.

A single generic regex approach failed because these patterns are too different. The strategy pattern (`_STRATEGIES` dict) is extensible — adding a new book means adding one extraction function and one dict entry. A `_extract_default` fallback handles unknown PDFs with generic chapter patterns, and if all detection fails, the entire document becomes one chapter.

**Trade-off**: Every new book requires manual inspection of its PDF structure and potentially a custom extraction function. Different editions or scans of the same book could break the regex patterns.

### Retrieval-Only Response Mode

The query functions in `backend/rag/query.py` return formatted chunks with source attribution directly, rather than using a generation-based response mode that synthesizes an answer from retrieved chunks. This was a deliberate architectural choice:

1. The voice agent's LLM already synthesizes the retrieved passages into a conversational response, so a second LLM synthesis step within the RAG pipeline seemed redundant.
2. Retrieval-only preserves exact quotes from the source text, which matters for literary questions where precise wording is important.
3. It eliminates a second OpenAI API call per RAG query, reducing cost.

### Cohere Reranking

- The pipeline retrieves the top 15 candidates via embedding similarity, then reranks to the top 5 using Cohere's `rerank-english-v3.0` cross-encoder model. Initial semantic similarity retrieval casts a wide net; the cross-encoder reranker then scores each candidate against the actual query with much higher precision. 
- This two-stage approach is especially important for literary questions where surface-level semantic similarity can be misleading — two chapters may both discuss "friendship" but only one discusses the specific scene asked about.

### Keyword-Based Metadata Filtering

- The `_build_filters()` function in `backend/rag/query.py` scans the question text for known book titles, author names, and chapter references, then constructs ChromaDB `MetadataFilters`. 
- For example, if the user asks "in chapter 5 of Conversations with Friends, what happens?", the filter constrains retrieval to `source=conversations_with_friends AND chapter_number=5`. 
- This dramatically improves precision for chapter-specific questions by eliminating irrelevant chunks before embedding similarity even runs.

**Trade-off**: The keyword lists (`LITERARY_BOOK_KEYWORDS`, `COURSE_BOOK_KEYWORDS`) are hardcoded and won't match creative phrasings like "in Rooney's first novel" or misspellings. A more robust approach would use NER or potentially the LLM itself to extract entities, but that would also add latency to every query.

### Embedding Model: text-embedding-3-small

Chosen over `text-embedding-3-large` for cost efficiency. The corpus is small, so the quality difference between the two models seemed marginal. The 1536-dimension embeddings from `text-embedding-3-small` provide sufficient semantic distinction between literary passages. 

### RAG Trade-offs Summary

- **No hybrid search**: Pure vector similarity with no BM25 keyword matching. Exact character name searches rely entirely on embedding similarity, which can miss unusual names.
- **No query expansion or HyDE**: Questions are embedded as-is. Hypothetical Document Embedding could improve recall for abstract questions but adds an LLM call per query.
- **Narrow corpus**: Two novels and one set of course notes. Out-of-corpus questions get the closest-matching but potentially irrelevant retrievals rather than a graceful "I don't have information on that."

---

## 2. LiveKit Agent Design

### SDK v1.5.x: AgentSession + Agent Subclass

The LiveKit Agents SDK v1.x uses `AgentSession` with `Agent` subclasses and `@function_tool` decorators that auto-discover tools via docstrings. This is the canonical pattern for all current LiveKit documentation.

### Voice Pipeline Components

The voice pipeline uses Deepgram Nova-3 for STT (with keyterm boosting for literary proper nouns like "Ferrante" and "Bildungsroman"), ElevenLabs for TTS (flash model variant for lower latency), gpt-5.4-mini as the LLM, Silero for VAD, and LiveKit's MultilingualModel for end-of-utterance turn detection with adaptive interruption mode. Background Voice Cancellation (BVC) is enabled on audio input to filter out environmental voices that would otherwise trigger false STT transcriptions.

### Config-Driven Tool Architecture

Tool definitions are loaded from `backend/agent/agent_config.yaml` at startup, with descriptions passed to `@function_tool(description=...)`. This separates tool documentation from implementation, making it straightforward to tune tool descriptions — which directly affect LLM tool-call routing — without modifying Python code. The agent exposes 9 tools:

| Category | Tools |
|---|---|
| Book discovery | `search_books`, `fetch_goodreads_reviews` |
| Shelf management | `add_to_shelf`, `remove_from_shelf`, `rename_shelf`, `get_shelf`, `list_shelves` |
| Knowledge retrieval | `query_literary_knowledge`, `query_course_notes` |

### Real-Time Frontend Sync via Data Channels

The agent publishes structured JSON on two LiveKit data channel topics:

- **`tool_status`**: Emits `tool_start` and `tool_done` events so the frontend can display animated tool-call chips (e.g., "Searching for books...") while tools execute.
- **`shelf_updated`**: Triggers an immediate REST fetch of `/shelves` in the frontend's `ShelfSync` component, providing near-instant shelf UI updates.

The frontend also polls `/shelves` every 3 seconds as a fallback in case data channel messages are missed during brief disconnections.

### Room-Scoped State and Cleanup

Each LiveKit room gets its own `ShelfStore` instance, persisted to `backend/data/shelves/{room}.json`. Room names are auto-generated as `lila-{uuid}` to prevent collisions between concurrent sessions. `ctx.add_shutdown_callback(cleanup_shelves)` removes the shelf file when the session ends, preventing disk accumulation on the EC2 instance.

**Trade-off**: Shelves do not persist between calls. This is intentional for the demo — each call is a fresh session. A production version would need user-scoped persistence with authentication.

---

## 3. Hosting Assumptions

### Split Architecture: EC2 Backend + Vercel Frontend

LiveKit agents are persistent Python processes that maintain a WebSocket connection to LiveKit Cloud as workers. 
They cannot run on serverless platforms (AWS Lambda, Vercel Functions, Google Cloud Functions) because those impose execution time limits and do not support persistent connections. 
EC2 is the simplest option that supports a long-running Python process.

The frontend is a static Vite build with no server-side logic, making Vercel's zero-config deployment ideal.

### Single EC2 t3.medium Instance

Both the FastAPI server (uvicorn on port 8000) and the LiveKit agent worker run as separate systemd services (`lila-api.service`, `lila-agent.service`) on a single t3.medium. This is sufficient for a small number of voice sessions because the agent worker is CPU-light — STT, TTS, and LLM are all external API calls. The EC2 instance only handles tool execution logic, RAG retrieval (ChromaDB queries), and shelf I/O.

**Assumption**: Expecting minimal concurrency and for the instance to only stay up for the duration of the demo period. To scale, would probably switch to ECS.

### HTTPS via Cloudflare Quick Tunnel

Vercel serves the frontend over HTTPS, and browsers block mixed content (HTTPS pages making HTTP API calls). Rather than configuring an SSL certificate on EC2 (which requires a domain, Elastic IP, and Let's Encrypt or ACM), a Cloudflare Quick Tunnel (`cloudflared tunnel --url http://localhost:8000`) creates an ephemeral HTTPS URL that proxies to the backend.

**Trade-off**: The tunnel URL changes every time the `cloudflared` process restarts, requiring a Vercel environment variable update and redeployment. In production, this would be replaced by a stable domain with an ALB and ACM certificate.

### CORS Configuration

CORS is set to `allow_origins=["*"]` because both the Cloudflare tunnel URL and Vercel preview URLs are unpredictable and vary across deployments. This is acceptable for a demo but would be tightened to the known frontend domain in production.

### No Load Balancer or CDN

The backend is a single process on a single instance. LiveKit Cloud handles all WebRTC media routing; the EC2 instance only runs agent logic and serves the REST API. An ALB would improve reliability but adds cost and complexity that seemed unnecessary for a demo.

---

## 4. Trade-offs and Limitations

### Single-Tenant, Single-Session
No authentication, no user accounts. Shelves are scoped per room and cleaned up on disconnect. There is no conversation memory between calls — each voice session starts fresh.

### Goodreads API Rate Limits
The Goodreads integration uses a RapidAPI wrapper limited to 35 requests/month on the BASIC plan. The implementation includes retry logic for transient 500 errors and graceful degradation when rate-limited (returns an error message; the agent falls back to Google Books data). Google Books serves as the primary book data source.

### Chapter Extraction Fragility
Each book requires a custom extraction strategy with regex patterns tuned to a specific PDF edition. A different scan, OCR quality, or edition formatting could break chapter detection. Mitigation: a `_extract_default` fallback uses generic chapter patterns, and if all detection fails, the entire document becomes one chapter (degraded but functional).

### No Hybrid Search
Pure vector similarity with no BM25 keyword component. Exact character name searches (e.g., "What does Bobbi say?") rely entirely on embedding similarity, which can miss unusual or short names. Adding a hybrid retriever (e.g., LlamaIndex's `QueryFusionRetriever`) would improve recall but adds pipeline complexity.

### No Conversation Memory
Each voice call starts with no memory of previous sessions. The LLM context is fresh each time. Shelves persist during a call but are cleaned up on disconnect. This is a deliberate simplification — persistent memory would require user accounts and a database.

### Ephemeral Tunnel URL
The Cloudflare Quick Tunnel URL changes on every restart. Updating it requires modifying the Vercel environment variable and redeploying the frontend. This is a known friction point for the demo workflow.

### Hardcoded Reading Profile
The user's reading history and preferences are hardcoded in the system prompt (`agent_config.yaml`). There is no mechanism for a new user to input their own preferences. This is by design for the demo's narrative — Lila knows "you" specifically — but limits generalizability.

### No Runtime PDF Upload
PDFs are pre-ingested at deployment time via `python -m rag.ingest`. There is no runtime upload endpoint. Adding on-the-fly ingestion would require background processing (10–30 seconds for embedding), query engine cache invalidation, and UI for upload progress. 

### Bookshelf Persistence Model
Bookshelves use a JSON file per room rather than a database. This is intentionally simple — no async drivers, no schema migrations, no connection pooling. The JSON file is written synchronously on every shelf mutation, which is acceptable for single-user, low-frequency writes. It would not scale to concurrent writes or large shelf collections.

---

## 5. Future Improvements

Given more time, the following areas would meaningfully improve Lila's functionality, reliability, and scalability.

### User Authentication and Personalized Profiles
Currently, the user's reading history and taste profile are hardcoded in the system prompt. With authentication (e.g., OAuth via Google or a simple email/password flow), each user would get a stored profile containing their reading history, favorite genres, mood preferences, and reread patterns. The system prompt would be dynamically assembled at session start by injecting the authenticated user's profile. This would transform Lila from a single-user demo into a multi-tenant product where every user gets a genuinely personalized librarian.

### Persistent Conversation Memory
Each voice call currently starts with a blank context. With a per-user conversation store (e.g., a summarized transcript saved to a database after each session), Lila could pick up where she left off — remembering what she recommended last time, what the user thought of a book they were reading, or which shelves they were building. Implementation would likely involve storing a compressed conversation summary (not raw transcripts) and prepending it to the system prompt at session start.

### RAG Pipeline Hardening

**Metadata filtering experimentation**: The current keyword-based metadata filtering (`_build_filters()`) uses hardcoded keyword lists. With more time, testing alternative approaches would be valuable — for example, using the LLM itself to extract book titles and chapter numbers from the question before retrieval, or using a lightweight NER model. This would handle creative phrasings ("Rooney's debut") and misspellings that the current approach misses.

**Cohere reranking latency profiling**: The Cohere reranker adds a network round-trip to every RAG query. Systematic latency testing — measuring P50/P95/P99 for the full retrieve-rerank pipeline across different `similarity_top_k` and `top_n` values — would determine whether the precision gains justify the latency cost in a voice context. It's possible that retrieving fewer candidates (e.g., top 8 instead of 15) with reranking to 3 would give nearly the same quality with lower latency.

**Expanded test query suite**: The current RAG testing is manual and ad-hoc. A structured evaluation set — covering chapter-specific factual questions, cross-book thematic queries, character name lookups, and adversarial out-of-corpus questions — would make it possible to measure retrieval quality systematically and catch regressions when changing chunking parameters or filtering logic.

**Hybrid search**: Adding BM25 keyword matching alongside vector similarity (e.g., via LlamaIndex's `QueryFusionRetriever`) would improve recall for exact name matches and short character names that embedding similarity struggles with.

### Real-World Book Tools
The current tool set covers discovery (Google Books, Goodreads) and personal organization (shelves). With more time, tools that bridge the gap between recommendation and action would make Lila significantly more useful:

- **Library availability**: Integration with the OverDrive/Libby API or WorldCat to check whether a recommended book is available at the user's local library, and place a hold directly from the conversation.
- **Bookstore purchase links**: Generate links to purchase from independent bookstores via Bookshop.org's affiliate API, or check availability at a preferred local bookstore.
- **Reading list export**: Export a shelf to Goodreads, StoryGraph, or a shareable link — so the user's curated shelves have value outside the voice session.
- **Reading progress tracking**: Let the user tell Lila "I'm on chapter 12 of Conversations with Friends" and have that persist, so Lila can ask about it next time and avoid spoilers beyond that point.

### Scalability and Infrastructure
- **Auto-scaling**: Replace the single EC2 instance with an ECS/Fargate service behind an ALB, allowing multiple concurrent voice sessions. LiveKit's agent dispatch would route jobs to available workers.
- **Stable HTTPS**: Replace the ephemeral Cloudflare tunnel with a registered domain, Elastic IP, and an ACM certificate on an ALB.
- **Database migration**: Move shelf persistence from JSON files to a lightweight database (e.g., DynamoDB or SQLite with WAL mode) to support concurrent writes and durable per-user storage.