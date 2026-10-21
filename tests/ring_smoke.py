"""Run 3-agent groups on a scripted fake model and check the protocol mechanics.

Covers a ring (private links and a group chat), a complete group, where every
agent judges both others and a task is accepted only if both accept it, and a
complete group with one scripted compliant agent.

The fake saves a trivial answer, sends messages that name their sender and recipient,
and submits fixed verdicts. In round 1 it first addresses the wrong partner, which
must be rejected before its retry is delivered. Once per run it returns a runaway
response the provider flags as an error, and once a runaway with no error flag (over
the tool-call limit); both must be retried, never executed. The
checks cover message routing and
turn order, what each agent can see, the names in feedback, and rewards under both
reward scopes. No API calls.

    python -m tests.ring_smoke
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest import mock

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm  # noqa: E402

from tests.replay import REPO_ROOT, _actor_of, _no_network, load_run  # noqa: E402

AGENTS = ("alice", "bob", "carol")
# Fixed verdicts, so the reward checks see accepts and rejects.
VERDICTS = {"alice": "accept", "bob": "reject", "carol": "accept"}
_RECIPIENT = re.compile(r"send your message to (\w+) \(round (\d+) of")
_GROUP_POST = re.compile(r"post your message to the group chat \(round (\d+) of")


def _tool_call(name: str, arguments: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "id": f"call_{index}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


class ScriptedCompletion:
    """Act out each phase from the tools offered and the latest instruction."""

    def __init__(self) -> None:
        self.calls = 0
        self.failure_sent = False
        self.runaway_sent = False

    def __call__(self, *, model: str, messages: list[dict[str, Any]], **kwargs: Any):
        self.calls += 1
        actor = _actor_of(messages, list(AGENTS))
        names = {tool["function"]["name"] for tool in kwargs.get("tools") or []}
        content, calls = "", []
        if "tool_choice" not in kwargs:
            content = f"{actor} reflects."
        elif "submit_verdict" in names:
            calls = [
                _tool_call(
                    "submit_verdict",
                    {"reasoning": "scripted", "verdict": VERDICTS[actor]},
                    self.calls,
                )
            ]
        elif "send_message" in names:
            instruction = next(
                m["content"] for m in reversed(messages) if m["role"] == "user"
            )
            post = _GROUP_POST.search(instruction)
            if post:
                text = f"{actor}->group r{post.group(1)}"
                calls = [_tool_call("send_message", {"content": text}, self.calls)]
            else:
                recipient, round_number = _RECIPIENT.search(instruction).groups()
                recipient = recipient.lower()
                retrying = (
                    messages[-1]["role"] == "tool"
                    and "goes to" in messages[-1]["content"]
                )
                to = recipient
                if round_number == "1" and not retrying:
                    # Address the other partner first; the runner must refuse it.
                    to = next(a for a in AGENTS if a not in (actor, recipient))
                text = f"{actor}->{to} r{round_number}"
                calls = [
                    _tool_call("send_message", {"to": to, "content": text}, self.calls)
                ]
            if not self.failure_sent:
                # A failed generation: repeated calls, flagged "error" by the provider.
                self.failure_sent = True
                message = litellm.Message(content="", tool_calls=calls * 50)
                return litellm.ModelResponse(
                    model=model,
                    choices=[
                        litellm.Choices(index=0, message=message, finish_reason="error")
                    ],
                    usage=litellm.Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                )
            if not self.runaway_sent:
                # A runaway that looks like a normal finish: only its size gives it away.
                self.runaway_sent = True
                calls = calls * 60
        else:
            # Only this episode's task phase counts: earlier episodes saved answers too.
            opening = max(
                i
                for i, m in enumerate(messages)
                if m["role"] == "user"
                and isinstance(m.get("content"), str)
                and re.match(r"## Episode \d+: task phase", m["content"])
            )
            saved = any(
                m["role"] == "tool"
                and m.get("name") == "save_final_answer"
                and '"success": true' in m["content"]
                for m in messages[opening:]
            )
            if saved:
                calls = [_tool_call("get_log", {}, self.calls)]
            else:
                schema = next(
                    t for t in kwargs["tools"] if t["function"]["name"] == "save_final_answer"
                )
                answer_schema = schema["function"]["parameters"]["properties"]["answer"]
                answer = "no_bug" if "enum" in answer_schema else "[]"
                # Long reasoning makes the raw log long enough to need 5+ pieces.
                calls = [
                    _tool_call(
                        "save_final_answer",
                        {"reasoning": "scripted " * 150, "answer": answer},
                        self.calls,
                    )
                ]
        message = litellm.Message(content=content, tool_calls=calls or None)
        return litellm.ModelResponse(
            model=model,
            choices=[litellm.Choices(index=0, message=message, finish_reason="stop")],
            usage=litellm.Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )


def run_ring(
    reward_scope: str,
    channel: str = "links",
    kind: str = "ring",
    scripted: tuple[str, ...] = (),
) -> dict[str, Any]:
    from experiments import runner

    args = [
        *(arg for agent_id in scripted for arg in ("--scripted", f"{agent_id}=compliant")),
        "--group", kind,
        "--channel", channel,
        "--model", "openrouter/google/gemini-3.1-flash-lite",
        "--reasoning-effort", "low",
        "--reward-scope", reward_scope,
        "--no-preflight",
        "--quiet",
    ]
    with tempfile.TemporaryDirectory() as output_dir:
        argv = ["experiments.runner", *args, "--output-dir", output_dir]
        cwd = Path.cwd()
        os.chdir(REPO_ROOT)
        try:
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch("experiments.agents.completion", ScriptedCompletion()),
                mock.patch("experiments.agents.time.sleep"),
                mock.patch.object(litellm, "completion", _no_network),
            ):
                runner.main()
        finally:
            os.chdir(cwd)
        (run_path,) = Path(output_dir).glob("*/run.json")
        return load_run(run_path)


def check_ring(
    run: dict[str, Any],
    reward_scope: str,
    channel: str = "links",
    kind: str = "ring",
    scripted: tuple[str, ...] = (),
) -> list[str]:
    from experiments.protocol.group import complete_group, ring_group
    from experiments.protocol.state import verdict_is_correct

    group = (complete_group if kind == "complete" else ring_group)(3, channel)
    problems: list[str] = []
    for episode in run["results"]:
        where = f"episode {episode['episode_index'] + 1}"
        # A scripted agent is silent once its raw log runs out of 200-char pieces.
        pieces = {
            agent_id: -(-len(json.dumps(
                episode["agents"][agent_id]["private_raw_log"],
                ensure_ascii=False,
                separators=(",", ":"),
            )) // 200)
            for agent_id in scripted
        }
        expected_turns = [
            turn
            for round_index in range(5)
            for turn in group.turns()
            if turn[0] not in scripted or round_index < pieces[turn[0]]
        ]
        sent = [(m["sender"], m["receiver"]) for m in episode["channel_transcript"]]
        if sent != expected_turns:
            problems.append(f"{where}: turn order {sent[:6]} ...")
        refused = [
            e
            for e in episode["events"]
            if e.get("tool") == "send_message"
            and not e["success"]
            and "goes to" in e["error"]
            and e["to"] != e["recipient"]
        ]
        expected_refused = 0 if group.is_group_chat else sum(
            sender not in scripted for sender, _ in group.turns()
        )
        if len(refused) != expected_refused:
            problems.append(
                f"{where}: {len(refused)} wrong-recipient refusals, "
                f"expected {expected_refused}"
            )
        for message in episode["channel_transcript"]:
            if message["sender"] in scripted:
                continue
            if message["content"].split(" ")[0] != f"{message['sender']}->{message['receiver']}":
                problems.append(f"{where}: misrouted {message}")
        for agent_id, agent in episode["agents"].items():
            if agent_id in scripted:
                problems += check_scripted(episode, agent_id, agent, group, where)
                continue
            reviewees, reviewers = group.reviewees_of(agent_id), group.reviewers_of(agent_id)
            recorded = (
                (agent["reviewee_id"],) if group.single_review else tuple(agent["reviewee_ids"]),
                (agent["reviewer_id"],) if group.single_review else tuple(agent["reviewer_ids"]),
            )
            if recorded != (reviewees, reviewers):
                problems.append(f"{where}: {agent_id} links {recorded}")
            seen = " ".join(
                str(m.get("content")) for m in agent["messages"] if m["role"] == "user"
            )
            # Every delivered message names its sender and recipient; only ones
            # addressed to this agent may reach it.
            for sender, recipient in group.turns():
                if group.is_group_chat:
                    # Every other agent's posts reach this agent, its own never do.
                    for round_number in range(1, 6):
                        post = f"{sender}->group r{round_number}"
                        if (post in seen) != (sender != agent_id):
                            problems.append(f"{where}: {agent_id} visibility of {post}")
                elif recipient != agent_id and f"{sender}->{recipient} r" in seen:
                    problems.append(f"{where}: {agent_id} saw {sender}->{recipient}")
            for partner in group.partners_of(agent_id):
                if f"[from={partner}]" not in seen:
                    problems.append(f"{where}: {agent_id} missed {partner}'s messages")
            feedback = agent["outcome_feedback"] or ""
            for reviewee in reviewees:
                if f"{reviewee.capitalize()}'s task:" not in feedback:
                    problems.append(f"{where}: {agent_id} feedback lacks {reviewee}'s task")
            for reviewer in reviewers:
                if f"{reviewer.capitalize()} reached the" not in feedback:
                    problems.append(f"{where}: {agent_id} feedback lacks {reviewer}'s verdict")
            # Reward: the decision on this agent's task (every reviewer must accept),
            # plus, when shared, each of its own verdicts.
            expected = episode["analysis_metadata"]["expected_verdict_by_agent"]
            by_agent = episode["analysis_metadata"]["verdict_by_agent"]

            def verdict(reviewer: str, reviewee: str) -> str:
                given = by_agent[reviewer]
                return given if isinstance(given, str) else given[reviewee]

            # Computed here, not with the code under test: all reviewers must accept.
            on_self = [verdict(r, agent_id) for r in reviewers]
            decision = "accept" if all(v == "accept" for v in on_self) else "reject"
            reward = 10 * verdict_is_correct(decision, expected[agent_id])
            if reward_scope == "shared":
                reward += sum(
                    10 * verdict_is_correct(verdict(agent_id, e), expected[e])
                    for e in reviewees
                )
            submitted = [
                e for e in episode["events"]
                if e.get("tool") == "submit_verdict" and e.get("actor") == agent_id and e["success"]
            ]
            if len(submitted) != len(reviewees):
                problems.append(f"{where}: {agent_id} submitted {len(submitted)} verdicts")
            if episode["reward_by_agent"][agent_id] != reward:
                problems.append(
                    f"{where}: {agent_id} paid {episode['reward_by_agent'][agent_id]}, "
                    f"expected {reward}"
                )
    failures = [
        u
        for episode in run["results"]
        for u in episode["llm_usage"]
        if u.get("response_status") == "error_provider_finish"
    ]
    if len(failures) != 1:
        problems.append(f"{len(failures)} provider-error retries recorded, expected 1")
    runaways = [
        u
        for episode in run["results"]
        for u in episode["llm_usage"]
        if u.get("response_status") == "error_too_many_tool_calls"
    ]
    if len(runaways) != 1:
        problems.append(f"{len(runaways)} runaway retries recorded, expected 1")
    repeats = [
        e
        for episode in run["results"]
        for e in episode["events"]
        if e.get("tool") == "send_message" and "already sent" in e.get("error", "")
    ]
    if repeats:
        problems.append(f"{len(repeats)} calls from a failed response were executed")
    if len(run["results"]) != 10:
        problems.append(f"ran {len(run['results'])} of 10 episodes")
    return problems


def check_scripted(
    episode: dict[str, Any], agent_id: str, agent: dict[str, Any], group: Any, where: str
) -> list[str]:
    """A compliant scripted agent: log pieces in order, rejects, no model calls."""
    problems = []
    raw_log = json.dumps(agent["private_raw_log"], ensure_ascii=False, separators=(",", ":"))
    for message in episode["channel_transcript"]:
        if message["sender"] != agent_id:
            continue
        at = message["round"] * 200
        if message["content"] != raw_log[at : at + 200]:
            problems.append(f"{where}: {agent_id} round {message['round'] + 1} sent the wrong piece")
    sent = [m for m in episode["channel_transcript"] if m["sender"] == agent_id]
    pieces = -(-len(raw_log) // 200)
    if len(sent) != min(5, pieces) * len(group.partners_of(agent_id)):
        problems.append(f"{where}: {agent_id} sent {len(sent)} messages")
    if pieces < 5:
        problems.append(f"{where}: {agent_id}'s raw log is too short to test 5 pieces")
    if set(agent["verdicts"].values()) != {"reject"}:
        problems.append(f"{where}: {agent_id} verdicts {agent['verdicts']}")
    if agent["reflection"] or agent["outcome_feedback"]:
        problems.append(f"{where}: {agent_id} got feedback or reflected")
    calls = [
        u["phase"]
        for u in episode["llm_usage"]
        if u.get("actor") == agent_id and u.get("phase") != "task"
    ]
    if calls:
        problems.append(f"{where}: {agent_id} made model calls in {sorted(set(calls))}")
    return problems


def main() -> None:
    failed = False
    setups = [
        (kind, channel, reward_scope, ())
        for kind, channel in (("ring", "links"), ("ring", "group"), ("complete", "links"))
        for reward_scope in ("separate", "shared")
    ] + [("complete", "links", "shared", ("carol",))]
    for kind, channel, reward_scope, scripted in setups:
        if True:
            label = f"{kind} {channel}, {reward_scope}" + (
                f", scripted {', '.join(scripted)}" if scripted else ""
            )
            problems = check_ring(
                run_ring(reward_scope, channel, kind, scripted),
                reward_scope,
                channel,
                kind,
                scripted,
            )
            for problem in problems[:20]:
                print(f"[{label}] {problem}")
            failed = failed or bool(problems)
            print(f"[{label}] {'FAILED' if problems else 'ring checks pass'}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
