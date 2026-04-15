"""
RAG testing tool — interactive queries and automated batch runs.

Usage:
    python test_rag.py                  # interactive REPL
    python test_rag.py batch            # run all queries from rag_queries.json
    python test_rag.py batch --verbose  # batch with full chunk details
"""

import json
import os
import sys

from dotenv import load_dotenv

from rag.query import get_query_engine

load_dotenv()

CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
RED = "\033[91m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

QUERIES_FILE = os.path.join(os.path.dirname(__file__), "rag_queries.json")


def run_query(engine, question: str) -> dict:
    response = engine.query(question)

    chunks = []
    for node in response.source_nodes:
        meta = node.metadata
        chunks.append(
            {
                "score": round(node.score, 4) if node.score else None,
                "source": meta.get("title", "Unknown"),
                "chapter_number": meta.get("chapter_number", "?"),
                "chapter_title": meta.get("chapter_title", ""),
                "pages": f"{meta.get('start_page', '?')}-{meta.get('end_page', '?')}",
                "text_preview": node.text[:300] if node.text else "",
            }
        )

    sources = []
    for ch in chunks:
        s = f"{ch['source']}, Chapter {ch['chapter_number']}"
        if ch["chapter_title"]:
            s += f" ('{ch['chapter_title'][:50]}')"
        if s not in sources:
            sources.append(s)

    return {
        "answer": str(response.response),
        "sources": sources,
        "chunks": chunks,
    }


def print_result(result: dict, verbose: bool = False):
    print(f"\n{CYAN}{BOLD}Answer:{RESET}")
    print(f"{CYAN}{result['answer']}{RESET}")

    print(f"\n{GREEN}{BOLD}Sources:{RESET}")
    for s in result["sources"]:
        print(f"  {GREEN}- {s}{RESET}")

    if verbose:
        print(f"\n{YELLOW}{BOLD}Retrieved Chunks ({len(result['chunks'])}):{RESET}")
        for i, ch in enumerate(result["chunks"], 1):
            print(f"\n  {YELLOW}--- Chunk {i} ---{RESET}")
            print(f"  {DIM}Score:   {ch['score']}{RESET}")
            print(
                f"  {DIM}Source:  {ch['source']}, Chapter {ch['chapter_number']}{RESET}"
            )
            print(f"  {DIM}Pages:   {ch['pages']}{RESET}")
            preview = ch["text_preview"].replace("\n", " ")
            print(f"  {DIM}Preview: {preview}...{RESET}")


def interactive(engine):
    print(f"\n{BOLD}RAG Query Tester{RESET} — type a question, see full results")
    print(f"{DIM}Commands: 'verbose' toggles chunk details, 'quit' exits{RESET}\n")

    verbose = True

    while True:
        try:
            question = input(f"{BOLD}Query: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break
        if question.lower() == "verbose":
            verbose = not verbose
            print(f"Verbose mode: {'ON' if verbose else 'OFF'}")
            continue

        result = run_query(engine, question)
        print_result(result, verbose=verbose)
        print()


def batch(engine, verbose: bool = False):
    if not os.path.exists(QUERIES_FILE):
        print(f"{RED}No queries file found at {QUERIES_FILE}{RESET}")
        print("Creating template with example queries...\n")
        create_default_queries()

    with open(QUERIES_FILE) as f:
        queries = json.load(f)

    print(f"\n{BOLD}Running {len(queries)} queries from rag_queries.json{RESET}\n")
    print("=" * 70)

    results = []
    for i, entry in enumerate(queries, 1):
        question = entry["question"]
        tag = entry.get("tag", f"query_{i}")

        print(f"\n{BOLD}[{i}/{len(queries)}] {tag}{RESET}")
        print(f"{DIM}{question}{RESET}")

        result = run_query(engine, question)
        result["tag"] = tag
        result["question"] = question
        results.append(result)

        print_result(result, verbose=verbose)
        print("\n" + "-" * 70)

    print(f"\n{BOLD}Summary{RESET}")
    print(f"  Queries run: {len(results)}")
    for r in results:
        src_count = len(r["sources"])
        chunk_count = len(r["chunks"])
        print(f"  {DIM}[{r['tag']}] {src_count} sources, {chunk_count} chunks{RESET}")

    output_path = os.path.join(os.path.dirname(__file__), "rag_test_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to {output_path}")


def create_default_queries():
    default = [
        {
            "tag": "free_indirect_style",
            "question": "What is free indirect style according to James Wood?",
        },
        {
            "tag": "flaubert_detail",
            "question": "What does James Wood say about Flaubert's use of detail?",
        },
        {
            "tag": "character_creation",
            "question": "How does James Wood describe the creation of fictional character?",
        },
        {
            "tag": "narrator_reliability",
            "question": "What does Wood say about the reliability of narrators?",
        },
    ]
    with open(QUERIES_FILE, "w") as f:
        json.dump(default, f, indent=2)
    print(f"Created {QUERIES_FILE} with {len(default)} default queries.")
    print("Edit this file to add your own queries.\n")


if __name__ == "__main__":
    engine = get_query_engine()

    if len(sys.argv) > 1 and sys.argv[1] == "batch":
        verbose = "--verbose" in sys.argv
        batch(engine, verbose=verbose)
    else:
        interactive(engine)
