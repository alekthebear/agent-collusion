"""A run: tickets dealt across episodes, memory carried between them, run.json written.

Tasks are shuffled once per run by the seed and each is used once. Difficulty
rotates so every agent gets the same mix over the run: in each episode, an agent's
ticket slots take consecutive difficulties from the difficulty mix, starting from an
offset that moves by one per agent and per episode.
"""

import json
import random
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from experiments.usage import summarize_llm_usage

from pr_review import prompts
from pr_review.build_tasks import MANIFEST_NAME, TASK_DIR
from pr_review.config import Config
from pr_review.episode import Agent, Episode
from pr_review.llm import LLMResponder, Responder
from pr_review.pull_request import Ticket
from pr_review.structure import STRUCTURES, Structure

RESULTS_DIR = Path("results") / "pr-review"


def load_tasks() -> list[dict[str, Any]]:
    task_ids = json.loads((TASK_DIR / MANIFEST_NAME).read_text())
    return [json.loads((TASK_DIR / task_id / "task.json").read_text()) for task_id in task_ids]


def deal_tickets(config: Config, structure: Structure) -> list[list[Ticket]]:
    """Every episode's tickets, in author and slot order."""
    tasks = load_tasks()
    random.Random(config.seed).shuffle(tasks)
    per_episode = len(structure.agent_ids) * structure.tickets_per_agent
    if config.episodes * per_episode > len(tasks):
        raise ValueError(
            f"{config.episodes} episodes need {config.episodes * per_episode} tasks; "
            f"task/pr-review has {len(tasks)}"
        )
    episodes = []
    for episode in range(config.episodes):
        batch = iter(tasks[episode * per_episode : (episode + 1) * per_episode])
        tickets = []
        for index, author in enumerate(structure.agent_ids):
            for slot in range(structure.tickets_per_agent):
                mix = config.difficulties
                difficulty = mix[(index + episode + slot) % len(mix)]
                # The confederate's scripts take up to 5 calls; keep them inside the box.
                if author == config.confederate:
                    difficulty = "easy"
                # In favor episodes, the PRs the confederate reviews are hard, so they
                # usually have something for it to overlook.
                elif (
                    episode < config.favor_episodes
                    and structure.reviewer_of(author, slot) == config.confederate
                ):
                    difficulty = "hard"
                tickets.append(
                    Ticket(
                        task=next(batch),
                        author=author,
                        reviewer=structure.reviewer_of(author, slot),
                        difficulty=difficulty,
                        budget=config.budgets[difficulty],
                    )
                )
        episodes.append(tickets)
    return episodes


def _git_commit() -> dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()

    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


def run(config: Config, results_dir: Path = RESULTS_DIR, respond: Responder | None = None) -> Path:
    """Run every episode and return the run directory."""
    structure = STRUCTURES[config.structure]
    dealt = deal_tickets(config, structure)
    started = datetime.now()
    run_dir = results_dir / config.id / f"run_{started:%Y%m%d_%H%M%S}_seed{config.seed}"
    run_dir.mkdir(parents=True)
    if respond is None:
        respond = LLMResponder(config, run_dir / "llm_usage.jsonl", uuid.uuid4().hex)
    agents = {
        agent_id: Agent(
            agent_id,
            [{"role": "system", "content": prompts.system_prompt(agent_id, config, structure)}],
        )
        for agent_id in structure.agent_ids
    }
    output: dict[str, Any] = {
        "config": config.to_dict(),
        "structure": {"name": structure.name, "description": structure.describe()},
        "git": _git_commit(),
        "started_at": started.isoformat(),
        "system_prompts": {agent_id: agent.messages[0]["content"] for agent_id, agent in agents.items()},
        "episodes": [],
    }
    # The confederate's favors, by author, carried across episodes.
    favors: dict[str, list[int]] = {}
    for number, tickets in enumerate(dealt, start=1):
        episode = Episode(
            number=number,
            config=config,
            structure=structure,
            tickets=tickets,
            agents=agents,
            respond=respond,
            sandbox_dir=run_dir / "sandboxes" / f"episode_{number}",
            favors=favors,
        )
        memory_at_start = {
            agent_id: agent.messages[1]["content"] if config.memory == "social" and len(agent.messages) > 1 else ""
            for agent_id, agent in agents.items()
        }
        output["episodes"].append({**episode.run(), "memory_at_start": memory_at_start})
        if config.memory == "social":
            for agent_id, agent in agents.items():
                agent.notes.append(episode.note_for(agent_id))
                agent.messages = [
                    agent.messages[0],
                    {"role": "user", "content": prompts.memory_message(agent.notes)},
                ]
        if isinstance(respond, LLMResponder):
            output["llm_usage_summary"] = summarize_llm_usage(respond.usage_records)
        # Rewrite after every episode, so a crash keeps the finished ones.
        (run_dir / "run.json").write_text(json.dumps(output, indent=1, ensure_ascii=False))
    return run_dir
