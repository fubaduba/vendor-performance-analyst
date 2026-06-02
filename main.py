"""Vendor Performance Analyst — Foundry hosted agent entry point.

Implements the Foundry Responses protocol via ``azure-ai-agentserver-responses``.
Wraps the existing ``agent.agent`` system prompt and tool registry in the
Responses server host so the same agent can run locally and on Foundry hosted
compute.

Required environment variables (injected by Foundry at runtime):
    FOUNDRY_PROJECT_ENDPOINT   (or AZURE_AI_PROJECT_ENDPOINT)
    AZURE_AI_MODEL_DEPLOYMENT_NAME  (or MODEL_DEPLOYMENT_NAME)
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import time

from opentelemetry import context as context_api, trace

from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponseEventStream,
    ResponsesAgentServerHost,
    ResponsesServerOptions,
)
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from azure.ai.agentserver.optimization import load_config

from agent.agent import AGENT_TOOLS, load_system_prompt


# ── Structured JSON logging ──────────────────────────────────────────────────

class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("tool_name", "arguments", "latency_ms", "response_id", "error"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_handler = logging.StreamHandler()
_handler.setFormatter(_JsonFormatter())
logging.root.setLevel(logging.INFO)
logging.root.addHandler(_handler)

logger = logging.getLogger(__name__)


# ── Configuration ─────────────────────────────────────────────────────────────

FOUNDRY_PROJECT_ENDPOINT: str | None = os.environ.get(
    "FOUNDRY_PROJECT_ENDPOINT"
) or os.environ.get("AZURE_AI_PROJECT_ENDPOINT")

AZURE_AI_MODEL_DEPLOYMENT_NAME: str | None = os.environ.get(
    "AZURE_AI_MODEL_DEPLOYMENT_NAME"
) or os.environ.get("MODEL_DEPLOYMENT_NAME")

_telemetry_configured = False


def _configure_telemetry() -> None:
    """No-op — the new azure-ai-agentserver-core (2.0.0b5+) auto-configures
    tracing via microsoft-opentelemetry distro in the AgentServerHost __init__.

    It reads APPLICATIONINSIGHTS_CONNECTION_STRING from the environment and
    enables the opentelemetry-instrumentation-openai-v2 instrumentor with
    sensitive data recording (message content) based on
    OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT (defaults to true).

    This function is kept as a placeholder so existing call sites don't break.
    """
    global _telemetry_configured
    if _telemetry_configured:
        return
    _telemetry_configured = True
    logger.info("Telemetry is auto-configured by azure-ai-agentserver-core distro.")


def _require_env() -> None:
    """Raise EnvironmentError if required env vars are absent.

    Called at the top of handle_create so the container can start even when
    Foundry hasn't injected env vars yet (e.g. during the build health-check).
    """
    if not FOUNDRY_PROJECT_ENDPOINT:
        raise EnvironmentError(
            "FOUNDRY_PROJECT_ENDPOINT is not set. The Foundry runtime injects it "
            "automatically; for local runs set it in .env."
        )
    if not AZURE_AI_MODEL_DEPLOYMENT_NAME:
        raise EnvironmentError(
            "AZURE_AI_MODEL_DEPLOYMENT_NAME is not set. Declare it in "
            "agent.manifest.yaml or .env."
        )


# ── Lazy credential / client init ─────────────────────────────────────────────

_credential: DefaultAzureCredential | None = None
_project_client: AIProjectClient | None = None
_openai_client = None


def _get_credential() -> DefaultAzureCredential:
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential


def _get_project_client() -> AIProjectClient:
    global _project_client
    if _project_client is None:
        _configure_telemetry()
        assert FOUNDRY_PROJECT_ENDPOINT  # validated by _require_env before first use
        _project_client = AIProjectClient(
            endpoint=FOUNDRY_PROJECT_ENDPOINT, credential=_get_credential()
        )
    return _project_client


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        _openai_client = _get_project_client().get_openai_client()
    return _openai_client


# Load optimization config — uses optimized instructions when running under
# the optimizer, otherwise falls back to the baseline system prompt.
_opt_config = load_config()
SYSTEM_PROMPT = _opt_config.instructions or load_system_prompt()


# ── Tool registry ─────────────────────────────────────────────────────────────

_TOOL_LOOKUP = {fn.__name__: fn for fn in AGENT_TOOLS}


def _param_json_schema(name: str, param: inspect.Parameter) -> dict:
    """Derive a JSON Schema snippet for one tool parameter."""
    annotation = param.annotation
    # Real integer annotation
    if annotation is int:
        return {"type": "integer", "description": f"Argument {name}"}
    # `days` parameters are semantically integers even when annotated as str
    if name == "days":
        return {"type": "integer", "description": "Lookback window in days"}
    return {"type": "string", "description": f"Argument {name}"}


def _build_responses_tools() -> list[dict]:
    """Build Responses API tool schemas from the AGENT_TOOLS callables."""
    schemas: list[dict] = []
    for fn in AGENT_TOOLS:
        sig = inspect.signature(fn)
        properties: dict[str, dict] = {}
        required: list[str] = []
        for name, param in sig.parameters.items():
            properties[name] = _param_json_schema(name, param)
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


# ── Responses protocol handler ────────────────────────────────────────────────

MAX_TOOL_ITERATIONS = 6
_MAX_LOG_ARG_LENGTH = 200  # truncation limit for argument strings in structured logs

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
    _require_env()

    tracer = trace.get_tracer(__name__)

    stream = ResponseEventStream(response_id=context.response_id, request=request)

    yield stream.emit_created()
    yield stream.emit_in_progress()

    user_input = await context.get_input_text() or ""
    history = await context.get_history()

    # Create an explicit span so traces are recorded even without incoming traceparent.
    # The span wraps the entire model+tool loop and carries input/output for evals.
    span = tracer.start_span(
        "invoke_agent",
        attributes={
            "gen_ai.system": "azure.ai.agentserver",
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": "vendorjobdetails",
            "gen_ai.response.id": context.response_id,
        },
    )
    ctx = trace.set_span_in_context(span)
    token = context_api.attach(ctx)

    # Record input on the span for trace-based evals
    span.set_attribute("input.value", user_input)

    message_item = stream.add_output_item_message()
    yield message_item.emit_added()

    text_content = message_item.add_text_content()
    yield text_content.emit_added()

    final_text = ""
    loop = asyncio.get_event_loop()
    model_input: list[dict] = _build_input(user_input, history)

    try:
        for _ in range(MAX_TOOL_ITERATIONS):
            if cancellation_signal.is_set():
                span.end()
                context_api.detach(token)
                yield stream.emit_incomplete("cancelled")
                return

            response = await loop.run_in_executor(
                None,
                lambda: _get_openai_client().responses.create(
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
                                final_text += part.text
                if final_text:
                    yield text_content.emit_delta(final_text)
                break

            # Append function_call items (as plain dicts — Responses API requires
            # a homogeneous input array) and their outputs, then loop.
            for fc in function_calls:
                model_input.append(
                    {
                        "type": "function_call",
                        "call_id": fc.call_id,
                        "name": fc.name,
                        "arguments": fc.arguments,
                    }
                )
                t0 = time.monotonic()
                result = await loop.run_in_executor(None, _execute_tool_call, fc.name, fc.arguments)
                latency_ms = int((time.monotonic() - t0) * 1000)
                logger.info(
                    "tool call completed",
                    extra={
                        "tool_name": fc.name,
                        "arguments": (
                            fc.arguments[:_MAX_LOG_ARG_LENGTH]
                            if len(fc.arguments) > _MAX_LOG_ARG_LENGTH
                            else fc.arguments
                        ),
                        "latency_ms": latency_ms,
                        "response_id": context.response_id,
                    },
                )
                model_input.append(
                    {
                        "type": "function_call_output",
                        "call_id": fc.call_id,
                        "output": result,
                    }
                )
        else:
            # Iteration cap reached without a final answer.
            final_text = (
                "I reached the tool-call iteration cap without producing a verdict. "
                "Please rephrase or narrow the question."
            )
            yield text_content.emit_delta(final_text)

    except Exception as e:  # noqa: BLE001
        logger.exception(
            "Error calling Foundry model",
            extra={"error": str(e), "response_id": context.response_id},
        )
        span.set_status(trace.StatusCode.ERROR, str(e))
        span.record_exception(e)
        span.end()
        context_api.detach(token)
        yield stream.emit_incomplete(str(e))
        return

    # Record output on the current span for trace-based evals
    span.set_attribute("output.value", final_text)
    span.end()
    context_api.detach(token)

    yield text_content.emit_text_done()
    yield text_content.emit_done()
    yield message_item.emit_done()
    yield stream.emit_completed()


if __name__ == "__main__":
    app.run()
