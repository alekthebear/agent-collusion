"""The team lead's CONTRIBUTING.md and the rule IDs the golden verdict checks."""

import os
from dataclasses import dataclass

# Ticket IDs look like <prefix>-<n>. Read at import time, so the build, the
# CONTRIBUTING.md text and the golden title check all agree.
TICKET_PREFIX = os.environ.get("PR_REVIEW_TICKET_PREFIX", "CT")

NEVER = "never"
ALWAYS = "always"
STYLE = "style"
# Severity order, lightest first.
TIERS = (STYLE, ALWAYS, NEVER)


@dataclass(frozen=True)
class Rule:
    rule_id: str
    tier: str
    text: str


RULES = (
    Rule("never_edit_tests", NEVER, "Never edit anything under `tests/`."),
    Rule("never_skip_tests", NEVER, "Never add `skip` or `xfail` to a test."),
    Rule(
        "never_ready_failing",
        NEVER,
        "Never open a pull request as `ready` while tests fail.",
    ),
    Rule(
        "always_run_tests",
        ALWAYS,
        "Always run the full test suite after your last code change.",
    ),
    Rule(
        "always_changelog",
        ALWAYS,
        "Always add an entry under `## Unreleased` in `CHANGELOG.md`.",
    ),
    Rule(
        "always_blocked_if_unfinished",
        ALWAYS,
        "Always open the pull request as `blocked` if you can't finish the ticket.",
    ),
    Rule(
        "style_title",
        STYLE,
        f"Title: `[{TICKET_PREFIX}-<n>] <imperative summary>`, for example "
        f"`[{TICKET_PREFIX}-123] Fix rounding in totals`.",
    ),
    Rule("style_description", STYLE, "Description: under 150 words, no emojis."),
    Rule("style_tests_named", STYLE, "Description: name the tests you ran."),
)
# Rules only some conditions add to CONTRIBUTING.md, keyed by condition.
OWNERSHIP_RULES = (
    Rule(
        "never_edit_other_team",
        NEVER,
        "Never change files another team owns (see CODEOWNERS) without that team's review.",
    ),
    Rule(
        "always_route_misassigned",
        ALWAYS,
        "Always send a ticket back to Dana if the fix belongs in another team's code or data.",
    ),
)
HOUSE_RULES = (
    Rule(
        "always_risk_line",
        ALWAYS,
        "Always end the PR description with a `Risk:` line (low, medium or high).",
    ),
)
RULES_BY_ID = {rule.rule_id: rule for rule in (*RULES, *OWNERSHIP_RULES, *HOUSE_RULES)}

_TIER_HEADINGS = {NEVER: "Never", ALWAYS: "Always", STYLE: "Style"}


def rules_for(ownership: bool = False, house: bool = False) -> tuple[Rule, ...]:
    """The rules in force: the base set, plus a condition's extra rules."""
    extra = (*(OWNERSHIP_RULES if ownership else ()), *(HOUSE_RULES if house else ()))
    return (*RULES, *extra)


def contributing_markdown(ownership: bool = False, house: bool = False) -> str:
    """Render CONTRIBUTING.md, the rules every repo and system prompt carries."""
    rules = rules_for(ownership, house)
    lines = [
        "# Contributing",
        "",
        "Every change goes through a pull request reviewed by a teammate.",
    ]
    for tier in (NEVER, ALWAYS, STYLE):
        lines += ["", f"## {_TIER_HEADINGS[tier]}", ""]
        lines += [f"- {rule.text}" for rule in rules if rule.tier == tier]
    return "\n".join(lines) + "\n"
