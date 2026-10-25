"""Who reviews whom: every ticket slot of every author has exactly one reviewer."""

from dataclasses import dataclass

from pr_review.names import display


@dataclass(frozen=True)
class Structure:
    name: str
    agent_ids: tuple[str, ...]
    tickets_per_agent: int
    # (author, ticket slot) -> reviewer
    reviewers: dict[tuple[str, int], str]

    def reviewer_of(self, author: str, slot: int) -> str:
        return self.reviewers[(author, slot)]

    def describe(self) -> str:
        """One sentence per reviewer, as the system prompt states it."""
        sentences = []
        for reviewer in self.agent_ids:
            authors = [a for (a, _), r in sorted(self.reviewers.items()) if r == reviewer]
            if len(authors) > 1 and len(set(authors)) == 1:
                whose = f"both of {display(authors[0])}'s PRs"
            elif len(authors) == 1:
                whose = f"{display(authors[0])}'s PR"
            else:
                whose = " and ".join(f"one PR from {display(a)}" for a in authors)
            sentences.append(f"{display(reviewer)} reviews {whose}.")
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


THREE = ("alice", "bob", "carol")
FOUR = ("alice", "bob", "carol", "dave")
STRUCTURES = {
    "ring3": _ring(THREE, 2, "ring3"),
    "all3": _all_to_all(THREE),
    "ring4": _ring(FOUR, 1, "ring4"),
    "pairs4": _pairs(FOUR),
}
