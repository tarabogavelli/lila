"""
Text-only CLI for testing Lila's tool calls and RAG.
Run: python cli.py
"""

import asyncio
import json
import re
from pathlib import Path

import yaml
from dotenv import load_dotenv
from openai import AsyncOpenAI

import tool_handlers as th
from tools.shelves import ShelfStore
from rag.query import query_literary_knowledge, query_course_notes

load_dotenv()

MODEL = "gpt-5.4-mini"
_cli_shelf_store = ShelfStore("cli-session")

_config_path = Path(__file__).parent / "agent" / "agent_config.yaml"
with open(_config_path) as f:
    _config = yaml.safe_load(f)

_voice_line = (
    "You are a voice agent — keep responses conversational, spoken-word natural.\n"
    "  No bullet points, no lists. Talk like a person."
)

SYSTEM_PROMPT = re.sub(
    re.escape(_voice_line),
    _config["system_prompt_text_mode_override"].strip(),
    _config["system_prompt"],
).strip()

TOOLS = _config["tools"]


CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_tool_call(name, args):
    args_str = ", ".join(f'{k}="{v}"' for k, v in args.items())
    print(f"{YELLOW}  [tool] {name}({args_str}){RESET}")


def print_tool_result(result):
    print(f"{DIM}{GREEN}  [result] {result}{RESET}")


def print_lila(text):
    print(f"\n{CYAN}{BOLD}Lila:{RESET} {CYAN}{text}{RESET}\n")


TOOL_HANDLERS = {
    "search_books": lambda **kw: th.search_books(**kw),
    "add_to_shelf": lambda **kw: th.add_to_shelf(_cli_shelf_store, **kw),
    "get_shelf": lambda **kw: th.get_shelf(_cli_shelf_store, **kw),
    "list_shelves": lambda **kw: th.list_shelves(_cli_shelf_store),
    "query_literary_knowledge": lambda **kw: query_literary_knowledge(**kw),
    "query_course_notes": lambda **kw: query_course_notes(**kw),
    "fetch_goodreads_reviews": lambda **kw: th.fetch_goodreads_reviews(**kw),
    "rename_shelf": lambda **kw: th.rename_shelf(_cli_shelf_store, **kw),
    "remove_from_shelf": lambda **kw: th.remove_from_shelf(_cli_shelf_store, **kw),
}


async def run_cli():
    client = AsyncOpenAI()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print(f"\n{BOLD}Lila CLI{RESET} — text mode for testing tools & RAG")
    print(f"{DIM}Type 'quit' to exit{RESET}\n")

    while True:
        try:
            user_input = input(f"{BOLD}You: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Bye!")
            break

        messages.append({"role": "user", "content": user_input})

        while True:
            try:
                response = await client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                )
            except Exception as e:
                print(f"{YELLOW}[error] API call failed: {e}{RESET}")
                messages.pop()
                break

            choice = response.choices[0]

            if choice.message.tool_calls:
                messages.append(choice.message)

                for tool_call in choice.message.tool_calls:
                    fn_name = tool_call.function.name
                    try:
                        fn_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}

                    print_tool_call(fn_name, fn_args)

                    handler = TOOL_HANDLERS.get(fn_name)
                    if handler is None:
                        result = f"Unknown tool: {fn_name}"
                    else:
                        try:
                            result = await handler(**fn_args)
                        except Exception as e:
                            result = f"Tool error: {e}"

                    print_tool_result(result)

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result,
                        }
                    )

                continue

            assistant_text = choice.message.content or ""
            messages.append({"role": "assistant", "content": assistant_text})
            print_lila(assistant_text)
            break


if __name__ == "__main__":
    asyncio.run(run_cli())
