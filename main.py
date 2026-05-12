"""Vendor Performance Analyst — Foundry hosted agent entry point.

Implements the Foundry Responses protocol via ``azure-ai-agentserver-responses``.
Wraps the existing ``agent.agent`` system prompt and tool registry in the
Responses server host so the same agent can run locally and on Foundry hosted
compute.

Required environment variables (injected by Foundry at runtime):
    FOUNDRY_PROJECT_ENDPOINT
    AZURE_AI_MODEL_DEPLOYMENT_NAME
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os

from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponseEventStream,
    ResponsesAgentServerHost,
    ResponsesServerOptions,
)
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from agent.agent import AGENT_TOOLS, load_system_prompt

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── Configuration ───────────────────────────────────────────────────────────

FOUNDRY_PROJECT_ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT") or os.environ.get(
    "AZURE_AI_PROJECT_ENDPOINT"
)
if not FOUNDRY_PROJECT_ENDPOINT:
    raise EnvironmentError(
        "FOUNDRY_PROJECT_ENDPOINT is not set. The Foundry runtime injects it "
        "automatically; for local runs set it in .env."
    )

AZURE_AI_MODEL_DEPLOYMENT_NAME = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME") or os.environ.get(
    "MODEL_DEPLOYMENT_NAME"
)
if not AZURE_AI_MODEL_DEPLOYMENT_NAME:
    raise EnvironmentError(
        "AZURE_AI_MODEL_DEPLOYMENT_NAME is not set. Declare it in "
        "agent.manifest.yaml or .env."
    )

_credential = DefaultAzureCredential()
_project_client = AIProjectClient(endpoint=FOUNDRY_PROJECT_ENDPOINT, credential=_credential)
_openai_client = _project_client.get_openai_client()

SYSTEM_PROMPT = load_system_prompt()


# ── Tool registry ───────────────────────────────────────────────────────────

_TOOL_LOOKUP = {fn.__name__: fn for fn in AGENT_TOOLS}


def _build_responses_tools() -> list[dict]:
    """Build Responses API tool schemas from the AGENT_TOOLS callables."""
    schemas: list[dict] = []
    for fn in AGENT_TOOLS:
        sig = inspect.signature(fn)
        properties: dict[str, dict] = {}
        required: list[str] = []
        for name, param in sig.parameters.items():
            properties[name] = {"type": "string", "description": f"Argument {name}"}
            if param.default is inspect.Parameter.empty:
                required.append(name)
        schemas.append(
            {
                "type": "function",
                "name": fn.__name__,
                "description": (fn.__doc__ or "").strip().split("\n")[0],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            }
        )
    return schemas


TOOLS = _build_responses_tools()


def _execute_tool_call(function_name: str, arguments: str) -> str:
    """Dispatch a function call from the model to the registered Python tool."""
    fn = _TOOL_LOOKUP.get(function_name)
    if fn is None:
        return json.dumps({"error": f"Unknown function: {function_name}"})
    try:
        args = json.loads(arguments or "{}")
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid tool arguments: {e}"})
    try:
        result = fn(**args)
    except Exception as e:  # noqa: BLE001 — surface to model for self-correction
        return json.dumps({"error": f"Tool '{function_name}' failed: {e}"})
    return result if isinstance(result, str) else json.dumps(result)


# ── Responses protocol handler ──────────────────────────────────────────────

MAX_TOOL_ITERATIONS = 6

app = ResponsesAgentServerHost(
    options=ResponsesServerOptions(default_fetch_history_count=20),
)


def _build_input(current_input: str, history: list) -> list[dict]:
    """Combine prior turns and the current user message into Responses input."""
    items: list[dict] = []
    for item in history or []:
        items.append(item)
    items.append({"role": "user", "content": current_input})
    return items


@app.response_handler
async def handle_create(
    request: CreateResponse,
    context: ResponseContext,
    cancellation_signal: asyncio.Event,
):
    """Drive the model + tool loop and stream the final answer."""
    stream = ResponseEventStream(response_id=context.response_id, request=request)

    yield stream.emit_created()
    yield stream.emit_in_progress()

    user_input = await context.get_input_text() or ""
    history = await context.get_history()

    message_item = stream.add_output_item_message()
    yield message_item.emit_added()

    text_content = message_item.add_text_content()
    yield text_content.emit_added()

    full_text = ""
    loop = asyncio.get_event_loop()
    model_input: list[dict] = _build_input(user_input, history)

    try:
        for _ in range(MAX_TOOL_ITERATIONS):
            if cancellation_signal.is_set():
                yield stream.emit_incomplete("cancelled")
                return

            response = await loop.run_in_executor(
                None,
                lambda: _openai_client.responses.create(
                    model=AZURE_AI_MODEL_DEPLOYMENT_NAME,
                    instructions=SYSTEM_PROMPT,
                    input=model_input,
                    tools=TOOLS,
                ),
            )

            function_calls = [item for item in response.output if item.type == "function_call"]

            if not function_calls:
                # Final answer — extract text and stream it out.
                for item in response.output:
                    if item.type == "message":
                        for part in item.content:
                            if part.type == "output_text":
                                full_text += part.text
                if full_text:
                    yield text_content.emit_delta(full_text)
                break

            # Append the function_call items plus their outputs to the input
            # and loop. The Responses API requires both halves of the pair.
            for fc in function_calls:
                model_input.append(fc)
                result = _execute_tool_call(fc.name, fc.arguments)
                logger.info("tool=%s args=%s", fc.name, fc.arguments)
                model_input.append(
                    {
                        "type": "function_call_output",
                        "call_id": fc.call_id,
                        "output": result,
                    }
                )
        else:
            # Iteration cap reached without a final answer.
            fallback = (
                "I reached the tool-call iteration cap without producing a verdict. "
                "Please rephrase or narrow the question."
            )
            yield text_content.emit_delta(fallback)
            full_text = fallback

    except Exception as e:  # noqa: BLE001
        err = f"Error calling Foundry model: {e}"
        logger.exception(err)
        if not full_text:
            yield text_content.emit_delta(err)

    yield text_content.emit_text_done()
    yield text_content.emit_done()
    yield message_item.emit_done()
    yield stream.emit_completed()


if __name__ == "__main__":
    app.run()
