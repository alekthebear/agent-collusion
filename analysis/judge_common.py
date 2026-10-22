"""Shared plumbing for the LLM judges.

Covers prompt files, reply parsing, the cached judge client, run selection, and the
review structure of pair, ring, and complete-group runs. Both judges default to
DeepSeek V4.1 Flash through OpenRouter; ``--base-url`` and ``--model`` point them at
a local OpenAI-compatible server instead, such as the paper's Qwen 3.8 27B.
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
import re
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
DEFAULT_API_KEY_ENV = "OPENROUTER_API_KEY"


# ---------------------------------------------------------------- prompts


def load_prompts(path: Path) -> dict[str, dict[str, str]]:
    """Read fenced prompt blocks as ``{section: {subsection: text}}``.

    Headings inside a code fence belong to the prompt, not the document structure.
    """
    prompts: dict[str, dict[str, str]] = {}
    section, sub, fence, buf = None, "", False, []
    for line in path.read_text().split("\n"):
        if line.startswith("```"):
            if fence and section is not None:
                prompts.setdefault(section, {})[sub] = "\n".join(buf).rstrip("\n")
            fence, buf = not fence, []
            continue
        if fence:
            buf.append(line)
        elif line.startswith("### "):
            sub = line[4:].strip()
        elif line.startswith("## "):
            section, sub = line[3:].strip(), ""
    return prompts


def render(template: str, **values: str) -> str:
    """Substitute placeholders literally, preserving JSON braces in prompt text.

    One pass, so a placeholder inside a substituted value (a message, a reflection) stays.
    """
    return re.sub(r"\{(\w+)\}",
                  lambda match: values.get(match.group(1), match.group(0)), template)


def check_prompt(prompts: dict[str, dict[str, str]], rung: str, path: Path,
                 placeholders: tuple[str, ...], labels: tuple[str, ...]) -> None:
    """Fail before API work if the prompt is malformed."""

    def die(message: str) -> None:
        raise SystemExit(f"{path.name}: {message}")

    if list(prompts) != [rung]:
        die(f"expected exactly one section named '{rung}'")
    blocks = prompts[rung]
    for part in ("system", "user"):
        if part not in blocks:
            die(f"'{rung}' has no '### {part}' fenced block")
    for name in placeholders:
        if blocks["user"].count("{" + name + "}") != 1:
            die(f"the user block must contain {{{name}}} exactly once")
    joined = blocks["system"] + blocks["user"]
    for label in ("JUDGEMENT",) + labels:
        if f"{label}:" not in joined:
            die(f"the prompt no longer asks for '{label}:'")


# ---------------------------------------------------------------- reply parsing


def strip_thinking(text: str) -> str:
    """Drop a reasoning block a Qwen3 route emits inline ahead of its answer."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S | re.I)
    # Keep an unterminated reasoning block so a truncated reply can still be parsed.
    return re.sub(r"^.*?<think>", "", text, flags=re.S | re.I).strip()


def parse_labels(text: str, labels: tuple[str, ...]) -> dict[str, str] | None:
    """Parse ``LABEL: value`` fields, allowing multiline values, or None without a JUDGEMENT."""
    keys = ("JUDGEMENT", "EXPLANATION") + labels
    found: dict[str, list[str]] = {}
    current = None
    for line in strip_thinking(text).split("\n"):
        # Accept markdown bold around the label, before or after the colon.
        match = re.match(r"^\s*\**([A-Z][A-Z -]*[A-Z])\**:\**\s*(.*)$", line)
        if match and match.group(1) in keys:
            current = match.group(1)
            found[current] = [match.group(2)]
        elif current is not None:
            found[current].append(line)
    if "JUDGEMENT" not in found:
        return None
    return {key: "\n".join(lines).strip() for key, lines in found.items()}


def judgement(fields: dict[str, str]) -> int | None:
    """Return 1 for Yes, 0 for No, and None for anything else."""
    verdict = fields.get("JUDGEMENT", "").strip().strip("[].*` ").lower()
    return {"yes": 1, "no": 0}.get(verdict)


def clean_quote(value: str) -> str:
    value = (value or "").strip().strip("[]`").strip()
    return "" if value.lower() in ("", "none", "n/a") else value


def norm(text: str) -> str:
    """Whitespace- and case-insensitive form, for checking a quote against its source."""
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def cache_key(rung: str, gate: int, model: str, prompt: str) -> str:
    digest = hashlib.sha1(f"{rung}\x00{gate}\x00{model}\x00{prompt}".encode()).hexdigest()
    return f"{rung}:{digest}"


# ---------------------------------------------------------------- judging


def reasoning_switch(base_url: str, think: bool, effort: str = "") -> dict:
    """Set thinking explicitly so server or provider defaults cannot override --think.

    A local server only switches thinking on or off; OpenRouter also takes an effort.
    """
    if "openrouter.ai" in base_url:
        reasoning = {"effort": effort} if effort else {"enabled": think}
        return {"reasoning": reasoning, "usage": {"include": True}}
    return {"chat_template_kwargs": {"enable_thinking": think or bool(effort)}}


def judge_identity(args: argparse.Namespace) -> str:
    """The model plus any reasoning setting, so cached replies never cross settings."""
    effort = getattr(args, "reasoning_effort", "")
    if effort:
        return f"{args.model}|reasoning={effort}"
    return f"{args.model}|think" if args.think else args.model


class Judge:
    def __init__(self, args: argparse.Namespace, cache_path: Path, client=None):
        if client is None:
            from openai import OpenAI

            api_key = os.environ.get(args.api_key_env) or "EMPTY"
            client = OpenAI(base_url=args.base_url, api_key=api_key, timeout=args.timeout)
        self.client = client
        self.model = args.model
        self.max_tokens = args.max_tokens
        self.identity = judge_identity(args)
        self.extra = reasoning_switch(args.base_url, bool(args.think),
                                      getattr(args, "reasoning_effort", ""))
        self.cache_path = cache_path
        self.cache: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.calls = 0
        self.tokens = [0, 0]
        self.cost = 0.0
        if cache_path.exists():
            with cache_path.open() as handle:
                for line in handle:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self.cache[row["key"]] = row["parsed"]

    def _remember(self, key: str, parsed: dict, raw: str, reasoning: str) -> None:
        """Append the verdict, raw reply, and complete provider reasoning trace to the cache."""
        with self.lock:
            self.cache[key] = parsed
            with self.cache_path.open("a") as handle:
                handle.write(json.dumps({"key": key, "parsed": parsed, "raw": raw[:4000],
                                         "reasoning": reasoning},
                                        ensure_ascii=False) + "\n")

    def _count(self, response) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        with self.lock:
            self.tokens[0] += getattr(usage, "prompt_tokens", 0) or 0
            self.tokens[1] += getattr(usage, "completion_tokens", 0) or 0
            self.cost += float(getattr(usage, "cost", 0) or 0)

    def ask(self, rung: str, gate: int, system: str, user: str,
            validate: Callable[[str], dict | None]) -> dict:
        """Return ``validate``'s result for the reply, retrying replies it rejects.

        Successful parses are reused from the cache; unresolved ones are retried on the
        next sweep and come back with ``answer=None`` and ``parse_ok=0``.
        """
        key = cache_key(rung, gate, self.identity, system + "\x00" + user)
        with self.lock:
            hit = self.cache.get(key)
        if hit is not None and hit.get("parse_ok"):
            return hit

        raw = reasoning = error = ""
        value = None
        request_count = 0
        for attempt in range(3):
            try:
                request_count += 1
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": user}],
                    temperature=0.0,
                    # Increase the token budget on retries in case reasoning used it up.
                    max_tokens=self.max_tokens * (1, 2, 4)[attempt],
                    extra_body=self.extra,
                )
                self._count(response)
                message = response.choices[0].message
                raw = message.content or ""
                # Provider routes expose the reasoning trace under either field name.
                reasoning = (getattr(message, "reasoning", None)
                             or getattr(message, "reasoning_content", None) or "")
                value = validate(raw)
                if value is not None:
                    error = ""
                    break
                error = "empty completion" if not raw else "invalid completion"
            except Exception as exc:  # a judge sweep should survive one bad call
                error = f"{type(exc).__name__}: {exc}"
        with self.lock:
            self.calls += request_count

        if value is not None:
            parsed = dict(value, parse_ok=1, error="")
        else:
            parsed = {"answer": None, "parse_ok": 0, "error": error}
        parsed["reasoning_chars"] = len(reasoning)
        self._remember(key, parsed, raw, reasoning)
        return parsed

    def report(self) -> str:
        cost = f", ${self.cost:.4f}" if self.cost else ""
        return (f"api calls: {self.calls}, tokens in/out: "
                f"{self.tokens[0]:,}/{self.tokens[1]:,}{cost}")


def judge_all(units: list, work: Callable[[int], dict], record: Callable[[int, dict], None],
              workers: int, judge: Judge) -> None:
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(work, index): index for index in range(len(units))}
        for future in as_completed(futures):
            record(futures[future], future.result())
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(units)}  ({judge.report()})", flush=True)


# ---------------------------------------------------------------- CLI and run selection


def add_common_args(parser: argparse.ArgumentParser, default_cache: str,
                    reasoning_effort: str = "", max_tokens: int = 400) -> None:
    parser.add_argument("--runs", nargs="+", required=True,
                        help="glob(s) matching run.json files, relative to the repo root")
    parser.add_argument("--out", required=True, help="CSV to write")
    parser.add_argument("--cache", default=default_cache)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV,
                        help="environment variable holding the API key (read from .env too)")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-tokens", type=int, default=max_tokens)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--think", action="store_true",
                        help="leave the judge model's reasoning on")
    parser.add_argument("--reasoning-effort", default=reasoning_effort,
                        choices=("", "minimal", "low", "medium", "high", "xhigh"),
                        help="reasoning effort for OpenRouter judges, or '' for none; implies --think. "
                             "Raise --max-tokens with it, since reasoning counts toward it")
    parser.add_argument("--limit", type=int, default=0,
                        help="stop after N runs -- useful for a smoke test")
    parser.add_argument("--runs-per-condition", type=int, default=0,
                        help="after deduplicating repetitions, keep the first N reps per condition")
    parser.add_argument("--verdict-policy", default="",
                        help="only judge episodes with this verdict policy; empty means all")
    parser.add_argument("--dry-run", action="store_true",
                        help="build the prompts and report their count and size, without API calls")


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")


def run_rep(path: Path) -> int | None:
    """Return the repetition number encoded in a run directory name."""
    match = re.search(r"_rep(\d+)(?:_|$)", path.parent.name)
    return int(match.group(1)) if match else None


def select_paths(paths: list[Path], runs_per_condition: int = 0) -> list[Path]:
    """Keep the latest artifact per repetition, then optionally cap each condition."""
    latest: dict[tuple[Path, int | str], Path] = {}
    for path in paths:
        rep = run_rep(path)
        key = (path.parent.parent, rep if rep is not None else path.parent.name)
        current = latest.get(key)
        if current is None or path.parent.name > current.parent.name:
            latest[key] = path
    grouped: dict[Path, list[Path]] = defaultdict(list)
    for path in latest.values():
        grouped[path.parent.parent].append(path)
    selected = []
    for condition in sorted(grouped, key=str):
        condition_paths = sorted(
            grouped[condition],
            key=lambda path: (
                run_rep(path) is None,
                run_rep(path) if run_rep(path) is not None else path.parent.name,
            ),
        )
        if runs_per_condition:
            condition_paths = condition_paths[:runs_per_condition]
        selected.extend(condition_paths)
    return selected


def load_runs(args: argparse.Namespace) -> list[tuple[Path, dict]]:
    paths: list[Path] = []
    for pattern in args.runs:
        paths += [Path(p) for p in sorted(glob.glob(str(ROOT / pattern)))]
    paths = select_paths(paths, args.runs_per_condition)
    if args.limit:
        paths = paths[:args.limit]
    runs = []
    for path in paths:
        try:
            with path.open() as handle:
                runs.append((path.resolve(), json.load(handle)))
        except (json.JSONDecodeError, OSError):
            continue
    return runs


def run_columns(path: Path, run: dict) -> dict:
    """Columns that identify a run in every judge's output."""
    config = run.get("run_config") or {}
    manifest = config.get("manifest") or ""
    match = re.search(r"rep(\d+)", manifest) if isinstance(manifest, str) else None
    family = path.parent.parent.parent
    try:
        run_path = str(path.relative_to(ROOT))
    except ValueError:
        run_path = str(path)
    return {
        "run_path": run_path,
        "cond_dir": path.parent.parent.name,
        "family": "" if family == ROOT else family.name,
        "structure": group_kind(run),
        "channel": channel_kind(run),
        "rep": match.group(1) if match else "",
    }


def write_csv(rows: list[dict], out: str) -> Path:
    out_path = ROOT / out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [key for key in rows[0] if not key.startswith("_")]
    with out_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return out_path


def dry_run(prompts: list[tuple[str, str]]) -> int:
    """Report how many calls a sweep would make and how large its prompts are."""
    chars = sum(len(system) + len(user) for system, user in prompts)
    print(f"dry run: {len(prompts)} judge calls, {chars:,} prompt characters "
          f"(about {chars // 4:,} tokens before caching)")
    if prompts:
        print("\n--- first user prompt ---\n" + prompts[0][1])
    return 0


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


# ---------------------------------------------------------------- review structure


def group_kind(run: dict) -> str:
    group = (run.get("run_config") or {}).get("agent_group") or {}
    return group.get("kind") or "pair"


def channel_kind(run: dict) -> str:
    group = (run.get("run_config") or {}).get("agent_group") or {}
    return group.get("channel") or "links"


def scripted_agents(run: dict) -> set[str]:
    return set((run.get("run_config") or {}).get("scripted_agents") or {})


def agent_model(run: dict, agent: str) -> str:
    models = (run.get("run_config") or {}).get("models") or {}
    return models.get(agent, "") if isinstance(models, dict) else str(models)


def reviewees(record: dict) -> list[str]:
    """The agents this agent judges, from a pair, ring, or complete-group record."""
    targets = record.get("reviewee_ids") or [record.get("reviewee_id") or record.get("peer_id")]
    return [target for target in targets if target]


def episode_links(episode: dict) -> list[tuple[str, str]]:
    """(reviewer, reviewee) pairs for every verdict in the episode."""
    agents = episode.get("agents")
    if not isinstance(agents, dict):
        return []
    return [(agent, target) for agent, record in agents.items()
            if isinstance(record, dict) for target in reviewees(record)]


def verdict_on(record: dict, reviewee: str) -> str:
    verdicts = record.get("verdicts")
    if isinstance(verdicts, dict):
        return verdicts.get(reviewee) or ""
    return record.get("verdict") or ""


def verdict_correct_on(record: dict, reviewee: str):
    correct = record.get("verdicts_correct")
    if isinstance(correct, dict):
        return correct.get(reviewee)
    return record.get("verdict_correct")


def display(agent: str) -> str:
    return agent.capitalize()


def names(agents: list[str]) -> str:
    shown = [display(agent) for agent in agents]
    return shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " and " + shown[-1]


def describe_structure(run: dict, episode: dict) -> str:
    """Who judges whom and where messages go, as told to the judge."""
    lines = [f"- {display(reviewer)} submits a verdict on {display(reviewee)}."
             for reviewer, reviewee in episode_links(episode)]
    if channel_kind(run) == "group":
        lines.append("- Every message is posted to a group chat that all participants "
                     "read; its recipient is shown as Group.")
    else:
        lines.append("- Each message goes privately from its sender to the recipient "
                     "shown, along a review link.")
    return "\n".join(lines)


def transcript_messages(episode: dict) -> list[dict]:
    """Messages in delivery order, with the text the recipient saw."""
    messages = sorted(
        episode.get("channel_transcript") or [],
        key=lambda m: (m.get("round", 0), m.get("event_id", 0)),
    )
    out = []
    for message in messages:
        text = message.get("content") or ""
        # The receiver also sees the optional label, which agents have used to carry content.
        label = message.get("message_type")
        if label and label != "other":
            text += f" [label: {label}]"
        out.append({"round": message.get("round"), "sender": message.get("sender") or "",
                    "receiver": message.get("receiver") or "", "text": text})
    return out


def render_transcript(messages: list[dict]) -> str:
    return "\n".join(
        f"[round {m['round']}] {display(m['sender'])} -> {display(m['receiver'])}: {m['text']}"
        for m in messages
    )
