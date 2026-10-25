"""The names agents see for each other, apart from the agent IDs the code and records use.

Alice, Bob and Carol are the stock cast of cryptography examples and test cases, a hint
that the team is constructed. Config.names gives ordinary names instead; IDs stay
alice, bob and carol everywhere else, so analysis and records don't change. The run
sets the names before its first prompt.
"""

_NAMES: dict[str, str] = {}


def use(names: dict[str, str]) -> None:
    """Show these names for these agent IDs from now on; IDs left out show capitalized."""
    _NAMES.clear()
    _NAMES.update(names)


def display(agent_id: str) -> str:
    return _NAMES.get(agent_id, agent_id.capitalize())


def agent_of(name: str) -> str:
    """The agent ID for a name an agent wrote, or the lowercased name if none matches."""
    lowered = name.strip().lower()
    for agent_id, shown in _NAMES.items():
        if shown.lower() == lowered:
            return agent_id
    return lowered
