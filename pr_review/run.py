"""A run: tickets dealt across episodes, memory carried between them, run.json written.

Tasks are shuffled once per run by the seed and each is used once. Difficulty
rotates so every agent gets the same mix over the run: in each episode, an agent's
ticket slots take consecutive difficulties starting from an offset that moves by
one per agent and per episode.
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
from pr_review.config import DIFFICULTIES, Config
from pr_review.episode import Agent, Episode
from pr_review.llm import LLMResponder, Responder
from pr_review.pull_request import Ticket
from pr_review.golden import APPROVE
from pr_review.structure import STRUCTURES, Structure, with_slots

RESULTS_DIR = Path("results") / "pr-review"


def load_tasks() -> list[dict[str, Any]]:
    task_ids = json.loads((TASK_DIR / MANIFEST_NAME).read_text())
    return [json.loads((TASK_DIR / task_id / "task.json").read_text()) for task_id in task_ids]


def deal_tickets(config: Config, structure: Structure) -> list[list[Ticket]]:
    """Every episode's tickets, in author and slot order."""
    all_tasks = load_tasks()
    rng = random.Random(config.seed)
    tasks = [task for task in all_tasks if task.get("kind", "standard") == "standard"]
    rng.shuffle(tasks)
    special = {
        kind: [task for task in all_tasks if task.get("kind") == kind]
        for kind in ("misrouted", "contradiction")
    }
    wanted = {"misrouted": config.misrouted, "contradiction": config.contradiction}
    for kind, per in wanted.items():
        if per and config.episodes * per > len(special[kind]):
            raise ValueError(
                f"{config.episodes} episodes x {per} {kind} tickets need "
                f"{config.episodes * per}; there are {len(special[kind])}"
            )
    special_iter = {kind: iter(special[kind]) for kind in special}
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
                difficulty = DIFFICULTIES[(index + episode + slot) % len(DIFFICULTIES)]
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
        _swap_in_special(tickets, wanted, special_iter, config, episode)
        episodes.append(tickets)
    return episodes


def _swap_in_special(tickets, wanted, special_iter, config: Config, episode: int) -> None:
    """Replace some of an episode's tickets with misrouted or contradiction ones.

    Never the confederate's (its scripts need standard tasks), and misrouted ones
    never go to the on-call engineer, who could just push the fix.
    """
    used: set[int] = set()
    for kind in ("misrouted", "contradiction"):
        for _ in range(wanted[kind]):
            eligible = [
                index
                for index, ticket in enumerate(tickets)
                if index not in used
                and ticket.author != config.confederate
                and not (kind == "misrouted" and ticket.author == config.on_call)
            ]
            if not eligible:
                raise ValueError(f"no author can take a {kind} ticket in episode {episode + 1}")
            # Rotate which author gets it across episodes.
            index = eligible[episode % len(eligible)]
            used.add(index)
            tickets[index].task = next(special_iter[kind])


class DailyDealer:
    """MH (Config.carryover): tickets dealt one day at a time, with carryover.

    Each author has a number of slots per day (one more on day 1 for day1_extra).
    Tickets carried over from earlier days fill slots first, oldest first; new tasks
    fill the rest. Every task is used at most once. Standard tasks come from the same
    seeded shuffle as deal_tickets, so the day-1 extra hard tickets (dealt first, in
    day1_extra order) and all of day 1 are the same in every structure. Each day's
    contradiction tickets go to contradiction_authors in turn; if that author has no
    new slot that day, to the next one in the list. Misrouted tasks are never dealt.
    day() returns None, and the run stops, before a day the pool can't fill.
    """

    def __init__(self, config: Config, structure: Structure) -> None:
        self.config = config
        self.structure = structure
        all_tasks = load_tasks()
        rng = random.Random(config.seed)
        self.standard = [task for task in all_tasks if task.get("kind", "standard") == "standard"]
        rng.shuffle(self.standard)
        self.contradictions = [task for task in all_tasks if task.get("kind") == "contradiction"]
        self.slots = config.tickets_per_day or structure.tickets_per_agent
        self.extra = Config.names(config.day1_extra)
        self.contradiction_order = Config.names(config.contradiction_authors) or list(
            structure.agent_ids
        )
        for name in (*self.extra, *self.contradiction_order):
            if name not in structure.agent_ids:
                raise ValueError(f"{name!r} is not on the team {structure.agent_ids}")
        self.backlog: dict[str, list[Ticket]] = {a: [] for a in structure.agent_ids}
        self.contradictions_dealt = 0
        self.stopped = ""
        # Per day: {day, carried, new, contradiction_to, backlog_after, pool_left}.
        self.log: list[dict[str, Any]] = []

    def _ticket(self, task: dict[str, Any], author: str, difficulty: str) -> Ticket:
        return Ticket(
            task=task,
            author=author,
            reviewer=self.structure.reviewer_of(author, 0),
            difficulty=difficulty,
            budget=self.config.budgets[difficulty],
        )

    def day(self, episode: int) -> list[Ticket] | None:
        """The tickets for day ``episode`` (0-based), or None if the pool can't fill it."""
        agents = self.structure.agent_ids
        capacity = {
            a: self.slots + (1 if episode == 0 and a in self.extra else 0) for a in agents
        }
        carried = {a: self.backlog[a][: capacity[a]] for a in agents}
        new_slots = {a: capacity[a] - len(carried[a]) for a in agents}
        # Who gets today's contradiction tickets.
        contradiction_to: list[str] = []
        for _ in range(self.config.contradiction):
            order = self.contradiction_order
            start = self.contradictions_dealt + len(contradiction_to)
            for step in range(len(order)):
                author = order[(start + step) % len(order)]
                if new_slots[author] - contradiction_to.count(author) > 0:
                    contradiction_to.append(author)
                    break
        standard_needed = sum(new_slots.values()) - len(contradiction_to)
        contradictions_left = len(self.contradictions) - self.contradictions_dealt
        # With no new slot anywhere (everyone's day is carryover), today's contradiction
        # ticket is skipped, not owed; the log records it.
        if standard_needed > len(self.standard) or len(contradiction_to) > contradictions_left:
            self.stopped = (
                f"before day {episode + 1}: needs {standard_needed} new standard and "
                f"{self.config.contradiction} contradiction tickets; {len(self.standard)} and "
                f"{contradictions_left} left (contradiction authors with a new slot: "
                f"{len(contradiction_to)})"
            )
            return None
        skipped = self.config.contradiction - len(contradiction_to)
        tickets: list[Ticket] = []
        extras: dict[str, Ticket] = {}
        if episode == 0:
            for author in self.extra:
                extras[author] = self._ticket(self.standard.pop(0), author, "hard")
        for index, author in enumerate(agents):
            self.backlog[author] = self.backlog[author][capacity[author] :]
            tickets += carried[author]
            fresh = new_slots[author] - (1 if author in extras else 0)
            for slot in range(fresh):
                difficulty = DIFFICULTIES[(index + episode + slot) % len(DIFFICULTIES)]
                if author in contradiction_to and slot == 0:
                    task = self.contradictions[self.contradictions_dealt]
                    self.contradictions_dealt += 1
                    contradiction_to.remove(author)
                else:
                    task = self.standard.pop(0)
                tickets.append(self._ticket(task, author, difficulty))
            if author in extras:
                tickets.append(extras[author])
        self.log.append(
            {
                "day": episode + 1,
                "carried": {a: [t.ticket_id for t in carried[a]] for a in agents},
                "contradictions_skipped": skipped,
                "new": {
                    a: [t.ticket_id for t in tickets if t.author == a and not t.carried_from]
                    for a in agents
                },
            }
        )
        return tickets

    def after(self, episode_number: int, tickets: list[Ticket], reviews: list[dict[str, Any]]) -> None:
        """Carry every ticket whose PR wasn't approved to its author's next day."""
        decision = {review["pr"]: review for review in reviews}
        for ticket in tickets:
            review = decision[ticket.number]
            if review["decision"] != APPROVE:
                self.backlog[ticket.author].append(
                    Ticket(
                        task=ticket.task,
                        author=ticket.author,
                        reviewer=ticket.reviewer,
                        difficulty=ticket.difficulty,
                        budget=ticket.budget,
                        carried_from=episode_number,
                        carry_reason=review["reason"],
                    )
                )
        self.log[-1]["backlog_after"] = {a: [t.ticket_id for t in b] for a, b in self.backlog.items()}
        self.log[-1]["pool_left"] = {
            "standard": len(self.standard),
            "contradiction": len(self.contradictions) - self.contradictions_dealt,
        }


def _git_commit() -> dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()

    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


def run(config: Config, results_dir: Path = RESULTS_DIR, respond: Responder | None = None) -> Path:
    """Run every episode and return the run directory."""
    structure = STRUCTURES[config.structure]
    dealer = None
    if config.carryover:
        # Up to one more slot on day 1, for the extra hard ticket.
        structure = with_slots(structure, (config.tickets_per_day or structure.tickets_per_agent) + 1)
        dealer = DailyDealer(config, structure)
        dealt = None
    else:
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
    for number in range(1, config.episodes + 1):
        if dealer is not None:
            tickets = dealer.day(number - 1)
            if tickets is None:
                output["dealing"] = {"log": dealer.log, "stopped": dealer.stopped}
                (run_dir / "run.json").write_text(json.dumps(output, indent=1, ensure_ascii=False))
                break
        else:
            tickets = dealt[number - 1]
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
        if dealer is not None:
            dealer.after(number, tickets, episode.reviews)
            output["dealing"] = {"log": dealer.log, "stopped": dealer.stopped}
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
