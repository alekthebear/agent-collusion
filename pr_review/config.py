"""One experiment's settings, from command-line flags or a past run. Each run.json records them.

Every Config field is a flag (``ask_tone`` is ``--ask-tone``). ``--from`` starts from
a past run's settings, and flags override them.
"""

import argparse
import json
from dataclasses import MISSING, asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Any

from experiments.models import DEFAULT_LLM_MAX_OUTPUT_TOKENS, DEFAULT_LLM_TEMPERATURE

from pr_review.structure import STRUCTURES

BUDGET_MODES = ("per_ticket", "shared")
MEMORY_MODES = ("social", "full")
DIFFICULTIES = ("easy", "medium", "hard")
ASKS = ("none", "plea", "trade")
ASK_TONES = ("direct", "casual")
# Settings that don't change the condition: changing them keeps a past run's id, and
# the automatic id leaves them out.
_SAME_CONDITION = ("episodes", "seed")


@dataclass(frozen=True)
class Config:
    # Names the results folder. Empty on the command line: built from the settings.
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
        if self.structure not in STRUCTURES:
            raise ValueError(f"structure must be one of {tuple(STRUCTURES)}")
        if self.budget not in BUDGET_MODES:
            raise ValueError(f"budget must be one of {BUDGET_MODES}")
        if self.memory not in MEMORY_MODES:
            raise ValueError(f"memory must be one of {MEMORY_MODES}")
        if self.ask not in ASKS:
            raise ValueError(f"ask must be one of {ASKS}")
        if self.ask_tone not in ASK_TONES:
            raise ValueError(f"ask_tone must be one of {ASK_TONES}")
        if set(self.budgets) != set(DIFFICULTIES):
            raise ValueError(f"budgets must set exactly {DIFFICULTIES}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_CHOICES = {
    "structure": tuple(STRUCTURES),
    "budget": BUDGET_MODES,
    "memory": MEMORY_MODES,
    "ask": ASKS,
    "ask_tone": ASK_TONES,
}


def _default(config_field: Any) -> Any:
    if config_field.default_factory is not MISSING:
        return config_field.default_factory()
    return config_field.default


def _budgets(text: str) -> dict[str, int]:
    """Parse "hard=3" or "easy=9,medium=6,hard=4"; difficulties left out keep their value."""
    budgets = {}
    for part in text.split(","):
        difficulty, _, calls = part.partition("=")
        if difficulty.strip() not in DIFFICULTIES or not calls.strip().isdigit():
            raise argparse.ArgumentTypeError(f"expected DIFFICULTY=CALLS with one of {DIFFICULTIES}")
        budgets[difficulty.strip()] = int(calls)
    return budgets


def add_config_arguments(parser: argparse.ArgumentParser) -> None:
    """One flag per Config field, plus --from. Flags left out are None."""
    parser.add_argument(
        "--from",
        dest="from_run",
        type=Path,
        metavar="RUN",
        help="start from a past run's settings: its run.json or run directory",
    )
    for config_field in fields(Config):
        flag = "--" + config_field.name.replace("_", "-")
        default = _default(config_field)
        if config_field.name == "id":
            help_text = "names the results folder; default: built from the settings"
        else:
            help_text = f"default: {default}"
        if config_field.type is bool:
            parser.add_argument(flag, action=argparse.BooleanOptionalAction, help=help_text)
        elif config_field.name == "budgets":
            parser.add_argument(flag, type=_budgets, metavar="DIFFICULTY=CALLS,...", help=help_text)
        else:
            parser.add_argument(
                flag, type=config_field.type, choices=_CHOICES.get(config_field.name), help=help_text
            )


def load_run_config(path: Path) -> dict[str, Any]:
    """The settings a past run recorded, from its run.json or run directory."""
    run_json = path / "run.json" if path.is_dir() else path
    values = json.loads(run_json.read_text())["config"]
    unknown = set(values) - {config_field.name for config_field in fields(Config)}
    if unknown:
        raise ValueError(f"Unknown config keys in {run_json}: {sorted(unknown)}")
    return values


def config_from_args(args: argparse.Namespace) -> Config:
    """The Config the flags describe, on top of --from's run if given.

    The id is --id if given, else the past run's when only the seed or episode count
    changed, else one built from the settings.
    """
    values = load_run_config(args.from_run) if args.from_run else {}
    overrides = {
        config_field.name: getattr(args, config_field.name)
        for config_field in fields(Config)
        if getattr(args, config_field.name) is not None
    }
    if "budgets" in overrides:
        base = values.get("budgets") or _default(Config.__dataclass_fields__["budgets"])
        overrides["budgets"] = {**base, **overrides["budgets"]}
    values.update(overrides)
    keep_id = "id" in overrides or (args.from_run and not set(overrides) - set(_SAME_CONDITION))
    config = Config(**{**values, "id": values.get("id", "") if keep_id else ""})
    return config if config.id else replace(config, id=auto_id(config))


def _id_part(name: str, value: Any) -> str:
    name = name.replace("_", "-")
    if isinstance(value, bool):
        return name if value else f"no-{name}"
    if isinstance(value, dict):
        return name + "-" + "-".join(f"{key}{number}" for key, number in value.items())
    if name == "model":
        value = str(value).split("/")[-1]
    return f"{name}-{value}"


def auto_id(config: Config) -> str:
    """The structure, then every setting that differs from its default, in field order."""
    parts = [config.structure]
    for config_field in fields(Config):
        value = getattr(config, config_field.name)
        skip = config_field.name in ("id", "structure", *_SAME_CONDITION)
        if not skip and value != _default(config_field):
            parts.append(_id_part(config_field.name, value))
    return "_".join(parts)
