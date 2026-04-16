"""
RAG testing tool — tests the retrieval-only pipeline with metadata filtering and reranking.

Usage:
    python test_rag.py              # run all queries, save full output to rag_test_results.md
    python test_rag.py interactive  # interactive REPL
"""

import asyncio
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

from rag.query import query_literary_knowledge, query_course_notes

load_dotenv()

CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "rag_test_results.md")

LITERARY_QUERIES = [
    "At the beginning of chapter 30 in Conversations with Friends, Bobbi and Frances are talking. What does Frances tell Bobbi that Melissa said about here?",
    "What happens to Frances in the church in Conversations with Friends?",
    "Which church does Frances go into in chapter 29 of Conversations with Friends?",
    "What is the protagonist's husband's name in Heart the Lover?",
]

COURSE_QUERIES = [
    "What is diasporic bildung and how does it relate to The Woman Warrior?",
    "How does Never Let Me Go use a bifocal narrative perspective?",
    "What does Professor Marcus say about Sula's hyper-individualism?",
    "What are the 2 types of chapters in Never Let Me Go according to sharon marcus?",
    "What do white tigers represent in The Woman Warrior?",
]


async def run_all():
    lines = []
    lines.append("# RAG Test Results\n")
    lines.append(f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}  RAG Pipeline Test — Literary Texts{RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")

    lines.append("\n## Literary Texts\n")

    for i, q in enumerate(LITERARY_QUERIES, 1):
        print(f"\n{YELLOW}{BOLD}[Literary {i}/{len(LITERARY_QUERIES)}]{RESET} {q}")
        result = await query_literary_knowledge(q)
        _print_result(result)

        lines.append(f"### Query {i}: {q}\n")
        lines.append(f"{result}\n")
        lines.append("\n---\n")

    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}  RAG Pipeline Test — Course Notes (Bildungsroman){RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")

    lines.append("\n## Course Notes\n")

    for i, q in enumerate(COURSE_QUERIES, 1):
        print(f"\n{GREEN}{BOLD}[Course {i}/{len(COURSE_QUERIES)}]{RESET} {q}")
        result = await query_course_notes(q)
        _print_result(result)

        lines.append(f"### Query {i}: {q}\n")
        lines.append(f"{result}\n")
        lines.append("\n---\n")

    with open(OUTPUT_FILE, "w") as f:
        f.write("\n".join(lines))

    total = len(LITERARY_QUERIES) + len(COURSE_QUERIES)
    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}  Done — {total} queries executed{RESET}")
    print(f"{BOLD}  Full output saved to: {OUTPUT_FILE}{RESET}\n")


async def interactive():
    print(f"\n{BOLD}RAG Interactive Tester{RESET}")
    print(
        f"{DIM}Prefix with 'c:' for course notes, otherwise queries literary texts{RESET}"
    )
    print(f"{DIM}Type 'quit' to exit{RESET}\n")

    while True:
        try:
            raw = input(f"{BOLD}Query: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not raw:
            continue
        if raw.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        if raw.lower().startswith("c:"):
            question = raw[2:].strip()
            print(f"{DIM}→ Querying course notes...{RESET}")
            result = await query_course_notes(question)
        else:
            question = raw
            print(f"{DIM}→ Querying literary texts...{RESET}")
            result = await query_literary_knowledge(question)

        _print_result(result)
        print()


def _print_result(result: str):
    chunks = result.split("\n\n---\n\n")
    print(f"{DIM}  Chunks returned: {len(chunks)}{RESET}")
    for i, chunk in enumerate(chunks, 1):
        lines = chunk.split("\n", 1)
        header = lines[0] if lines else ""
        body = lines[1] if len(lines) > 1 else ""
        preview = body[:200].replace("\n", " ").strip()
        print(f"\n  {CYAN}{BOLD}Chunk {i}:{RESET} {CYAN}{header}{RESET}")
        print(f"  {DIM}{preview}...{RESET}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        asyncio.run(interactive())
    else:
        asyncio.run(run_all())
