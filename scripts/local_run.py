"""Local invocation for development — no Foundry required.

Runs the agent's tools and system prompt against an OpenAI-compatible model
endpoint so you can iterate on prompts and tools without deploying.

Usage:
  python scripts/local_run.py "Is NorthStar Networks meeting their SLA commitments?"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.agent import AGENT_TOOLS, build_agent_definition  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="The user query to send to the agent")
    parser.add_argument(
        "--prompt-version",
        choices=["v1", "v2"],
        default="v1",
        help="Which system prompt to use",
    )
    args = parser.parse_args()

    # Swap the prompt by setting the env var the agent module reads.
    prompt_path = (
        Path(__file__).parent.parent / "agent" / "prompts" / f"system_prompt_{args.prompt_version}.md"
    )
    os.environ["SYSTEM_PROMPT_PATH"] = str(prompt_path)

    definition = build_agent_definition()
    print(f"[local] Using prompt: {prompt_path.name}")
    print(f"[local] Model: {definition['model']}")
    print(f"[local] Query: {args.query}")
    print()

    # Minimal local loop using openai-python. The Foundry hosted runtime
    # handles this loop server-side in production.
    try:
        from openai import AzureOpenAI
    except ImportError:
        raise SystemExit("Install 'openai': pip install openai")

    client = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version="2024-08-01-preview",
    )

    tool_lookup = {fn.__name__: fn for fn in AGENT_TOOLS}
    messages = [
        {"role": "system", "content": definition["instructions"]},
        {"role": "user", "content": args.query},
    ]

    for _ in range(6):
        completion = client.chat.completions.create(
            model=definition["model"],
            messages=messages,
            tools=definition["tools"],
        )
        msg = completion.choices[0].message
        if not msg.tool_calls:
            print("[local] Agent response:")
            print(msg.content)
            return

        messages.append(msg.model_dump())
        for tc in msg.tool_calls:
            args_obj = json.loads(tc.function.arguments or "{}")
            print(f"[local] tool: {tc.function.name}({args_obj})")
            result = tool_lookup[tc.function.name](**args_obj)
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": str(result)}
            )

    print("[local] Iteration cap reached without a final answer.")


if __name__ == "__main__":
    main()
