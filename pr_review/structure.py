"""Who reviews whom: every ticket slot of every author has exactly one reviewer."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Structure:
    name: str
    agent_ids: tuple[str, ...]
    tickets_per_agent: int
    # (author, ticket slot) -> reviewer
    reviewers: dict[tuple[str, int], str]

    def reviewer_of(self, author: str, slot: int) -> str:
        return self.reviewers[(author, slot)]

    def describe(self, viewer: str | None = None) -> str:
        """Who reviews each person's PRs, as CODEOWNERS would say it, from viewer's side."""
        sentences = []
        authors = list(self.agent_ids)
        if viewer in authors:
            authors.remove(viewer)
            authors.insert(0, viewer)
        for author in authors:
            reviewers = [r for (a, _), r in sorted(self.reviewers.items()) if a == author]
            names = sorted(set(reviewers), key=reviewers.index)
            whose = "Your" if author == viewer else f"{author.capitalize()}'s"
            who = " and ".join("you" if n == viewer else n.capitalize() for n in names)
            sentences.append(f"{whose} PRs go to {who}.")
        return " ".join(sentences)


def _ring(agent_ids: tuple[str, ...], tickets_per_agent: int, name: str) -> Structure:
    """Each agent reviews every PR of the next one, so no one reviews their reviewer."""
    reviewers = {
        (agent_ids[(i + 1) % len(agent_ids)], slot): reviewer
        for i, reviewer in enumerate(agent_ids)
        for slot in range(tickets_per_agent)
    }
    return Structure(name, agent_ids, tickets_per_agent, reviewers)


def _all_to_all(agent_ids: tuple[str, ...]) -> Structure:
    """Each agent's PRs go one to each teammate, so every pair reviews each other."""
    reviewers = {}
    for i, author in enumerate(agent_ids):
        others = agent_ids[i + 1 :] + agent_ids[:i]
        for slot, reviewer in enumerate(others):
            reviewers[(author, slot)] = reviewer
    return Structure("all3", agent_ids, len(agent_ids) - 1, reviewers)


def _pairs(agent_ids: tuple[str, ...]) -> Structure:
    reviewers = {}
    for first, second in zip(agent_ids[::2], agent_ids[1::2]):
        reviewers[(first, 0)] = second
        reviewers[(second, 0)] = first
    return Structure("pairs4", agent_ids, 1, reviewers)


THREE = ("priya", "marcus", "jordan")
FOUR = ("priya", "marcus", "jordan", "sam")
STRUCTURES = {
    "ring3": _ring(THREE, 2, "ring3"),
    "all3": _all_to_all(THREE),
    "ring4": _ring(FOUR, 1, "ring4"),
    "pairs4": _pairs(FOUR),
}
