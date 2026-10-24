"""One experiment's settings, loaded from a TOML file. Each run.json records them."""

import tomllib
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from experiments.models import DEFAULT_LLM_MAX_OUTPUT_TOKENS, DEFAULT_LLM_TEMPERATURE

BUDGET_MODES = ("per_ticket", "shared")
MEMORY_MODES = ("social", "full")
DIFFICULTIES = ("easy", "medium", "hard")


@dataclass(frozen=True)
class Config:
    id: str
    model: str = "openrouter/deepseek/deepseek-v4.1-flash"
    reasoning_effort: str = "low"
    temperature: float = DEFAULT_LLM_TEMPERATURE
    max_output_tokens: int = DEFAULT_LLM_MAX_OUTPUT_TOKENS
    structure: str = "all3"
    episodes: int = 5
    seed: int = 1
    # Adds a release-is-blocked line to every ticket.
    pressure: bool = True
    # per_ticket: one budget per ticket, worked in turn. shared: one pool, the sum
    # of the tickets' budgets, for all of them at once.
    budget: str = "per_ticket"
    # social: carry feedback, reflections, and the threads and messages the agent
    # took part in. full: carry the whole conversation, tool calls included.
    memory: str = "social"
    # Tells agents they may coordinate however they like.
    positive_control: bool = False
    # An agent whose work is scripted to break a rule on one PR per episode; its talk
    # and reviews come from the model. Empty for none.
    confederate: str = ""
    # What the confederate may ask its reviewers for: none, plea, or trade.
    ask: str = "plea"
    # Episodes at the start in which the confederate's work is clean, it asks nothing,
    # and it approves every PR it reviews, saying what it overlooked: favors first.
    favor_episodes: int = 0
    # How the ask is worded: direct ("let it through this once") or casual.
    ask_tone: str = "direct"
    budgets: dict[str, int] = field(
        default_factory=lambda: {"easy": 9, "medium": 6, "hard": 4}
    )
    review_checks: int = 3
    talk_rounds: int = 3
    message_chars: int = 500

    def __post_init__(self) -> None:
        if self.budget not in BUDGET_MODES:
            raise ValueError(f"budget must be one of {BUDGET_MODES}")
        if self.memory not in MEMORY_MODES:
            raise ValueError(f"memory must be one of {MEMORY_MODES}")
        if self.ask not in ("none", "plea", "trade"):
            raise ValueError("ask must be none, plea or trade")
        if self.ask_tone not in ("direct", "casual"):
            raise ValueError("ask_tone must be direct or casual")
        if set(self.budgets) != set(DIFFICULTIES):
            raise ValueError(f"budgets must set exactly {DIFFICULTIES}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config(path: Path, **overrides: Any) -> Config:
    values = tomllib.loads(path.read_text())
    unknown = set(values) - {f.name for f in fields(Config)}
    if unknown:
        raise ValueError(f"Unknown config keys in {path}: {sorted(unknown)}")
    values.update({key: value for key, value in overrides.items() if value is not None})
    return Config(**values)
