"""Model calls, through the paper harness's LLM client (retries, providers, usage).

The episode only sees a responder: given an agent's messages and tools, it returns
the assistant message to append and the decoded tool calls. Tests swap in a
scripted responder.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from experiments.agents import (
    _complete_with_retries,
    _decoded_tool_arguments,
    _select_tools_and_choice,
)
from experiments.llm import get_litellm_completion_kwargs, reasoning_to_replay
from experiments.usage import make_llm_usage_recorder

from pr_review.config import Config


@dataclass
class Reply:
    # The assistant message, ready to append to the agent's history.
    message: dict[str, Any]
    # [{id, name, arguments}]; arguments is None when they didn't decode.
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    # {tools, tool_choice} as sent, after the model-specific fallback; None when the
    # responder made no API request (scripted responders in tests).
    request: dict[str, Any] | None = None
    # The reply hit the output limit without a tool call: a runaway, such as a model
    # repeating itself until the cap. The episode drops it from the history.
    cut_off: bool = False
    # Reasoning the provider returned but the message doesn't replay, such as
    # Anthropic's and OpenAI's summaries through OpenRouter. The episode keeps it in
    # the record only, so what the model is sent doesn't change.
    reasoning: str = ""


def returned_reasoning(choice_message: Any) -> str:
    """Readable reasoning on a response message: reasoning_content, or the text and
    summaries in reasoning_details. Encrypted reasoning (Gemini's) has none."""
    def get(source: Any, key: str) -> Any:
        return source.get(key) if isinstance(source, dict) else getattr(source, key, None)

    text = get(choice_message, "reasoning_content") or get(choice_message, "reasoning")
    if isinstance(text, str) and text.strip():
        return text
    details = get(choice_message, "reasoning_details") or get(
        get(choice_message, "provider_specific_fields") or {}, "reasoning_details"
    ) or []
    parts = [get(detail, "text") or get(detail, "summary") for detail in details]
    return "\n\n".join(part for part in parts if isinstance(part, str) and part.strip())


class Responder(Protocol):
    def __call__(
        self,
        *,
        agent_id: str,
        episode: int,
        phase: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str | dict[str, Any] | None,
    ) -> Reply: ...


def forced(tool_name: str) -> dict[str, Any]:
    return {"type": "function", "function": {"name": tool_name}}


class LLMResponder:
    def __init__(self, config: Config, journal_path: Path, invocation_id: str) -> None:
        self.config = config
        self.journal_path = journal_path
        self.invocation_id = invocation_id
        self.usage_records: list[dict[str, Any]] = []

    def __call__(
        self,
        *,
        agent_id: str,
        episode: int,
        phase: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: str | dict[str, Any] | None,
    ) -> Reply:
        model = self.config.model
        # "none": tools are sent, since the history holds tool calls, but none may be
        # called. Without it some models (GPT-6 Luna) call one anyway and reply empty;
        # with it some (DeepSeek) still do. A call is then accepted, so the retries
        # don't run out, and dropped: the reply is its text, possibly none.
        calls_tools = tool_choice not in (None, "none")
        extra = get_litellm_completion_kwargs(
            model,
            self.config.reasoning_effort,
            passthrough_params=("tool_choice",) if tool_choice else (),
        )
        completion_kwargs: dict[str, Any] = {"tools": tools, **extra}
        if tool_choice is not None:
            tools, tool_choice = _select_tools_and_choice(
                tools=tools,
                tool_choice=tool_choice,
                model=model,
                reasoning_effort=self.config.reasoning_effort,
            )
            completion_kwargs.update(tools=tools, tool_choice=tool_choice)
        recorder = make_llm_usage_recorder(
            records=self.usage_records,
            journal_path=self.journal_path,
            invocation_id=self.invocation_id,
            episode_id=f"episode_{episode}",
            episode_index=episode - 1,
            actor=agent_id,
            phase=phase,
            round_idx=None,
            attempt_idx=None,
        )
        response, choice_message, content, tool_calls = _complete_with_retries(
            model=model,
            messages=messages,
            completion_kwargs=completion_kwargs,
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_output_tokens,
            accept_tool_calls=tool_choice is not None,
            usage_recorder=recorder,
        )
        choices = getattr(response, "choices", None) or []
        finish_reason = getattr(choices[0], "finish_reason", None) if choices else None
        message: dict[str, Any] = {"role": "assistant", "content": content}
        if calls_tools and tool_calls:
            message["tool_calls"] = tool_calls
        # DeepSeek's reasoning is replayed in the message, so transcripts keep it.
        message.update(reasoning_to_replay(model, choice_message))
        recorded = "" if message.get("reasoning_content") else returned_reasoning(choice_message)
        return Reply(
            message=message,
            tool_calls=[
                {
                    "id": call["id"],
                    "name": call["function"]["name"],
                    "arguments": _decoded_tool_arguments(call["function"]["arguments"]),
                }
                for call in message.get("tool_calls", [])
            ],
            request={
                "tools": completion_kwargs["tools"],
                "tool_choice": completion_kwargs.get("tool_choice"),
            },
            cut_off=finish_reason == "length" and not message.get("tool_calls"),
            reasoning=recorded,
        )
