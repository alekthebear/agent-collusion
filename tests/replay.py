"""Replay a recorded run through the current code and compare everything it produces.

Each agent's recorded assistant turns are served back, in order, in place of the LLM.
The run is deterministic given those turns, so the replayed run.json must match the
recorded one, and every request (history, tools, tool choice) must match the golden
request log. Only temp-directory hashes, the repo path, and pytest timings are
normalized.

    python -m tests.replay            # compare against the fixture and golden log
    python -m tests.replay --record   # rewrite the golden request log
"""

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest import mock

# Keep LiteLLM from fetching its remote model-cost map at import.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures"
POC_RUN = FIXTURES / "poc_run.json.gz"
POC_REQUESTS = FIXTURES / "poc_requests.jsonl"

# The command that produced the PoC fixture, minus its output directory.
POC_ARGS = [
    "--cross-episode-memory-scope", "full-history",
    "--verdict-policy", "raw-only",
    "--char-limit", "200",
    "--max-rounds", "5",
    "--manifest", str(REPO_ROOT / "task/task_sequences_50x10/rep001_sampled_manifest.json"),
    "--run-label", "default_cross-episode_raw-only_r5_rep1_memory-full-history_shared-verdict-accuracy_reward_verdict-review_reflection",
    "--alice-model", "openrouter/google/gemini-3.1-flash-lite",
    "--alice-reasoning-effort", "low",
    "--alice-temperature", "1.0",
    "--alice-max-output-tokens", "64000",
    "--alice-cross-episode-memory-length", "-1",
    "--bob-model", "openrouter/google/gemini-3.1-flash-lite",
    "--bob-reasoning-effort", "low",
    "--bob-temperature", "1.0",
    "--bob-max-output-tokens", "64000",
    "--bob-cross-episode-memory-length", "-1",
    "--reward-scope", "shared",
    "--reward-type", "verdict-accuracy",
    "--reflection",
    "--reward",
    "--verdict-review",
    "--no-preflight",
]

# Fields that depend on the provider response rather than the protocol.
IGNORED_KEYS = frozenset({"llm_usage", "llm_usage_summary", "llm_reasoning_traces"})

# Record fields added after the fixture was recorded. They may appear only in the
# replay; everything the recording has must still match.
ADDED_KEYS = frozenset(
    {"agent_group", "reviewee_id", "reviewer_id", "message_side_channel"}
)

_NORMALIZERS = (
    # Temp test directories carry a per-run hash.
    (re.compile(r"(_ep\d{3})_[0-9a-f]{16}"), r"\1_<hash>"),
    # Pytest reports wall-clock durations.
    (re.compile(r"\bin \d+\.\d+s\b"), "in <t>s"),
)

# The logged pytest launcher depends on whether pytest is on PATH. Applied only to
# event "command" fields, which never reach the agents.
_PYTEST_LAUNCHER = re.compile(r"^.*? (?=<repo>/results/tmp_tests/)")


def normalize_text(text: str) -> str:
    text = text.replace(str(REPO_ROOT), "<repo>")
    for pattern, replacement in _NORMALIZERS:
        text = pattern.sub(replacement, text)
    return text


def normalize(value: Any) -> Any:
    """Normalize strings recursively and drop provider-dependent fields."""
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, dict):
        return {
            key: (
                _PYTEST_LAUNCHER.sub("<pytest> ", normalize_text(item))
                if key == "command" and isinstance(item, str)
                else normalize(item)
            )
            for key, item in value.items()
            if key not in IGNORED_KEYS
        }
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def _digest(value: Any) -> str:
    canonical = json.dumps(normalize(value), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_run(path: Path) -> dict[str, Any]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def recorded_turns(run: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Each agent's assistant turns in call order, from its final, complete history."""
    final = run["results"][-1]["agents"]
    return {
        agent_id: [m for m in agent["messages"] if m["role"] == "assistant"]
        for agent_id, agent in final.items()
    }


def _actor_of(messages: list[dict[str, Any]], agent_ids: list[str]) -> str:
    """Identify the caller from the system prompt's "You are <Name>." line."""
    system = json.dumps(messages[0].get("content", ""), ensure_ascii=False)
    matches = [a for a in agent_ids if f"You are {a.capitalize()}." in system]
    if len(matches) != 1:
        raise AssertionError(f"Cannot identify the calling agent: {matches}")
    return matches[0]


class FakeCompletion:
    """Serve recorded assistant turns and log a digest of every request."""

    def __init__(self, turns: dict[str, list[dict[str, Any]]]):
        self.turns = {agent_id: list(queue) for agent_id, queue in turns.items()}
        self.requests: list[dict[str, Any]] = []

    def __call__(self, *, model: str, messages: list[dict[str, Any]], **kwargs: Any):
        actor = _actor_of(messages, list(self.turns))
        queue = self.turns[actor]
        if not queue:
            raise AssertionError(f"{actor} made more calls than were recorded")
        turn = queue.pop(0)
        self.requests.append(
            {
                "index": len(self.requests),
                "actor": actor,
                "messages": _digest(messages),
                "tools": _digest(kwargs.get("tools")),
                "tool_choice": kwargs.get("tool_choice"),
            }
        )
        message = litellm.Message(
            content=turn.get("content") or "",
            tool_calls=turn.get("tool_calls") or None,
        )
        return litellm.ModelResponse(
            model=model,
            choices=[litellm.Choices(index=0, message=message, finish_reason="stop")],
            usage=litellm.Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        )

    def unconsumed(self) -> dict[str, int]:
        return {agent_id: len(queue) for agent_id, queue in self.turns.items() if queue}


def replay(recorded: dict[str, Any], args: list[str]) -> tuple[dict[str, Any], FakeCompletion]:
    """Run the current code on the recorded turns; return its run.json and the fake."""
    from experiments import runner

    fake = FakeCompletion(recorded_turns(recorded))
    with tempfile.TemporaryDirectory() as output_dir:
        argv = ["experiments.runner", *args, "--output-dir", output_dir]
        cwd = Path.cwd()
        os.chdir(REPO_ROOT)
        try:
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch("experiments.agents.completion", fake),
                # Fail loudly if any other path reaches a real provider.
                mock.patch.object(litellm, "completion", _no_network),
            ):
                runner.main()
        finally:
            os.chdir(cwd)
        (run_path,) = Path(output_dir).glob("*/run.json")
        return load_run(run_path), fake


def _no_network(*args: Any, **kwargs: Any):
    raise AssertionError("Unexpected direct litellm.completion call during replay")


def differences(expected: Any, actual: Any, path: str = "", limit: int = 20) -> list[str]:
    """List up to ``limit`` paths where two normalized JSON values differ."""
    found: list[str] = []

    def walk(a: Any, b: Any, where: str) -> None:
        if len(found) >= limit:
            return
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(set(a) | set(b)):
                if key not in a and key in ADDED_KEYS:
                    continue
                if key not in a or key not in b:
                    found.append(f"{where}.{key}: present only in {'actual' if key in b else 'expected'}")
                else:
                    walk(a[key], b[key], f"{where}.{key}")
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                found.append(f"{where}: length {len(a)} != {len(b)}")
            for index, (x, y) in enumerate(zip(a, b)):
                walk(x, y, f"{where}[{index}]")
        elif a != b:
            found.append(f"{where}: {str(a)[:120]!r} != {str(b)[:120]!r}")

    walk(normalize(expected), normalize(actual), path)
    return found


def read_requests(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def check_poc(*, record: bool = False) -> list[str]:
    """Replay the PoC; return a list of problems, empty when the replay matches."""
    recorded = load_run(POC_RUN)
    produced, fake = replay(recorded, POC_ARGS)
    problems: list[str] = []
    if fake.unconsumed():
        problems.append(f"recorded turns never requested: {fake.unconsumed()}")
    problems += [
        f"results{d}" for d in differences(recorded["results"], produced["results"])
    ]
    problems += [
        f"run_config{d}"
        for d in differences(recorded["run_config"], produced["run_config"])
    ]
    if record:
        POC_REQUESTS.write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in fake.requests),
            encoding="utf-8",
        )
    else:
        golden = read_requests(POC_REQUESTS)
        if len(golden) != len(fake.requests):
            problems.append(f"requests: {len(golden)} golden != {len(fake.requests)} replayed")
        for want, got in zip(golden, fake.requests):
            if want != got:
                fields = [k for k in want if want[k] != got.get(k)]
                problems.append(
                    f"request {want['index']} ({want['actor']}): differs in {fields}"
                )
                break
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--record", action="store_true", help="Rewrite the golden request log."
    )
    args = parser.parse_args()
    problems = check_poc(record=args.record)
    for problem in problems:
        print(problem)
    if problems:
        sys.exit(1)
    print("Replay matches." + (" Golden request log written." if args.record else ""))


if __name__ == "__main__":
    main()
