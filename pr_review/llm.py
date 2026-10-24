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
        _, choice_message, content, tool_calls = _complete_with_retries(
            model=model,
            messages=messages,
            completion_kwargs=completion_kwargs,
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_output_tokens,
            accept_tool_calls=tool_choice is not None,
            usage_recorder=recorder,
        )
        message: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_choice is not None and tool_calls:
            message["tool_calls"] = tool_calls
        # DeepSeek's reasoning is replayed in the message, so transcripts keep it.
        message.update(reasoning_to_replay(model, choice_message))
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
        )
