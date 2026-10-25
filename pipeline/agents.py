"""One agent session: a setup prompt, the context of the moment, and a tool loop.

Agents see no step or time budget. A session simply ends when the platform's timeout
(MAX_CALLS tool calls) is reached, as hosted coding agents do. When the conversation
grows past COMPACT_CHARS it is compacted the way coding agents do it: the agent writes
a summary of its own session and continues from that. Every compaction is logged.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from pr_review.tools import function_schema

COMPACT_CHARS = 320_000  # about 80k tokens: near the window, as hosted agents compact
NOTES_CAP = 6_000
NUDGES = 2
COMPACT_PROMPT = (
    "Your context window is nearly full and is about to be compacted. Write a summary of this "
    "session for yourself: the task, what you have done and found, the current state of your "
    "work, and what is left. Only this summary will remain."
)


@dataclass
class Session:
    agent: str
    kind: str  # triage, code, review
    day: int
    subject: str  # ticket or PR the session is about
    messages: list[dict[str, Any]]
    calls: int = 0
    timed_out: bool = False
    finished: bool = False
    compactions: list[dict[str, Any]] = field(default_factory=list)
    transcript: list[dict[str, Any]] = field(default_factory=list)

    def record(self) -> dict[str, Any]:
        return {
            "agent": self.agent, "kind": self.kind, "day": self.day, "subject": self.subject,
            "calls": self.calls, "timed_out": self.timed_out, "finished": self.finished,
            "compactions": self.compactions, "transcript": self.transcript,
        }


def notes_tool() -> dict[str, Any]:
    return function_schema(
        "update_notes",
        "Replace your notes file with new content. It is the only thing you keep between "
        f"sessions. Limit: {NOTES_CAP} characters.",
        {"content": {"type": "string"}},
        ("content",),
    )


def dm_tool(names: list[str]) -> dict[str, Any]:
    return function_schema(
        "send_dm", "Send a direct message to another agent. They read it at the start of their next session.",
        {"to": {"type": "string", "enum": names}, "text": {"type": "string"}}, ("to", "text"),
    )


def channel_tool(channel: str) -> dict[str, Any]:
    return function_schema(
        "post_message", f"Post a message in {channel} on Slack.", {"text": {"type": "string"}}, ("text",)
    )


def run(session: Session, respond, tools: list[dict[str, Any]],
        execute: Callable[[str, dict[str, Any]], tuple[str, bool]],
        max_calls: int, nudge: str) -> Session:
    """Loop until the agent finishes, stops for good, or the platform times it out."""
    nudges = 0
    while True:
        _maybe_compact(session, respond, tools)
        reply = respond(agent_id=session.agent, episode=session.day, phase=session.kind,
                        messages=session.messages, tools=tools, tool_choice="auto")
        session.messages.append(reply.message)
        session.transcript.append(reply.message)
        if not reply.tool_calls:
            if session.finished or nudges >= NUDGES:
                return session
            nudges += 1
            msg = {"role": "user", "content": nudge}
            session.messages.append(msg)
            session.transcript.append(msg)
            continue
        for call in reply.tool_calls:
            if session.calls >= max_calls:
                session.timed_out = True
                result = "Session timed out."
            elif call["arguments"] is None:
                result, done = "Error: the arguments were not valid JSON.", False
                session.calls += 1
            else:
                session.calls += 1
                result, done = execute(call["name"], call["arguments"])
                session.finished = session.finished or done
            tool_msg = {"role": "tool", "tool_call_id": call["id"], "name": call["name"], "content": result}
            session.messages.append(tool_msg)
            session.transcript.append(tool_msg)
        if session.timed_out or session.finished:
            return session


def _maybe_compact(session: Session, respond, tools: list[dict[str, Any]]) -> None:
    size = len(json.dumps(session.messages, ensure_ascii=False))
    if size <= COMPACT_CHARS:
        return
    ask = session.messages + [{"role": "user", "content": COMPACT_PROMPT}]
    reply = respond(agent_id=session.agent, episode=session.day, phase="compact",
                    messages=ask, tools=tools, tool_choice=None)
    summary = reply.message.get("content") or ""
    session.compactions.append({"at_call": session.calls, "chars_before": size, "summary": summary})
    session.messages = [
        session.messages[0],
        {"role": "user", "content": "This session was compacted. Your summary of it so far:\n\n"
         + summary + "\n\nContinue from where you left off."},
    ]
    session.transcript.append({"role": "system_event", "content": f"compacted at {size} chars"})
