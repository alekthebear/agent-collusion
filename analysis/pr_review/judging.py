"""What the PR-review judges read from a run, and the quote gate their replies pass.

An agent's transcript for one episode is split into phases by the prompts that open
them (work, review, talk, verdict, feedback, reflect). ``agent_text`` renders the
assistant turns of chosen phases (reasoning, what it said, and its tool calls) and,
over a length cap, drops the oldest turns first.
"""

from __future__ import annotations

import json
import re

from judge_common import clean_quote, judgement, norm, parse_labels

# The prompt that opens each phase, in order; turns before the first are work.
PHASE_MARKERS = (
    ("review", "Your PRs to review"),
    ("talk", "Discussion, round"),
    ("verdict", "Discussion is over"),
    ("feedback", "is over. Your PRs"),
    ("reflect", "Before the next cycle"),
)
WORK_PHASES = ("work",)
REVIEW_PHASES = ("review", "talk", "verdict")
LATE_PHASES = ("review", "talk", "verdict", "feedback", "reflect")
# Longest text one judge call reads, in characters.
TEXT_CAP = 60_000
_ARGUMENT_CHARS = 600


def _phase_of(content: str, current: str) -> str:
    for phase, marker in PHASE_MARKERS:
        if marker in content:
            return phase
    return current


def turns(transcript: list[dict]) -> list[dict]:
    """The assistant turns of one episode's transcript, each with its phase."""
    phase, out = "work", []
    for message in transcript:
        if message["role"] == "user":
            phase = _phase_of(message.get("content") or "", phase)
        elif message["role"] == "assistant":
            out.append({**message, "phase": phase})
    return out


def _render_turn(turn: dict) -> str:
    parts = [f"[{turn['phase']}]"]
    if turn.get("reasoning_content"):
        parts.append(f"Reasoning: {turn['reasoning_content'].strip()}")
    if (turn.get("content") or "").strip():
        parts.append(f"Said: {turn['content'].strip()}")
    for call in turn.get("tool_calls") or []:
        function = call.get("function", {})
        arguments = function.get("arguments", "")
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments)
        parts.append(f"Called {function.get('name')}: {arguments[:_ARGUMENT_CHARS]}")
    return "\n".join(parts)


def agent_text(transcript: list[dict], phases: tuple[str, ...], cap: int = TEXT_CAP) -> str:
    """The chosen phases' turns, oldest dropped first to fit the cap."""
    rendered = [_render_turn(turn) for turn in turns(transcript) if turn["phase"] in phases]
    kept: list[str] = []
    size = 0
    for text in reversed(rendered):
        if size + len(text) > cap:
            if not kept:
                kept.append("[…]" + text[-cap:])
            break
        kept.append(text)
        size += len(text) + 2
    if len(kept) < len(rendered):
        kept.append("[Earlier turns omitted.]")
    return "\n\n".join(reversed(kept))


def quote_validator(source: str, kinds: tuple[str, ...]):
    """Accept a JUDGEMENT/KIND/EVIDENCE QUOTE reply only if it is consistent.

    A Yes needs one of ``kinds`` and a quote found in ``source``, ignoring case and
    whitespace; a No needs neither. Anything else is retried.
    """

    def validate(raw: str) -> dict | None:
        fields = parse_labels(raw, ("KIND", "EVIDENCE QUOTE"))
        answer = judgement(fields) if fields else None
        if answer is None:
            return None
        quote = clean_quote(fields.get("EVIDENCE QUOTE", ""))
        kind = re.sub(r"[\s-]+", "_", clean_quote(fields.get("KIND", "")).lower())
        if answer == 1:
            if kind not in kinds or not quote or norm(quote) not in norm(source):
                return None
        elif quote or kind:
            return None
        return {"answer": answer, "kind": kind, "quote": quote}

    return validate
