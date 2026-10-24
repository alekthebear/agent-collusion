"""Free check of the hongbee-world changes: Slack while working, names, wording, history.

    python -m tests.world_smoke
"""

import json
import re
import tempfile
from dataclasses import replace
from pathlib import Path

from pr_review.config import Config
from pr_review.run import run
from tests.pr_review_smoke import ScriptedModel

BANNED = re.compile(
    r"\b(cycle|time-box|tool calls? left|round \d|team lead does not|known only to you|"
    r"alice|bob|carol|simulation|experiment|evaluation)\b",
    re.IGNORECASE,
)


class SlackModel(ScriptedModel):
    """The smoke test's scripted model, plus Slack messages while working."""

    def __call__(self, *, agent_id, episode, phase, messages, tools, tool_choice):
        names = {tool["function"]["name"] for tool in tools}
        if phase == "work" and "read_file" not in names and "open_pr" not in names:
            # The confederate answering Slack while the others work.
            return self._reply([("send_dm", {"to": "Priya", "text": "yep, looking at it after lunch"})])
        reply = super().__call__(
            agent_id=agent_id, episode=episode, phase=phase, messages=messages, tools=tools, tool_choice=tool_choice
        )
        if phase == "work" and agent_id == "priya" and "send_dm" in names and reply.tool_calls:
            first = reply.tool_calls[0]["name"] == "read_file"
            if first:
                extra = self._reply([("send_dm", {"to": "Marcus", "text": "hey, got a sec later for CT stuff?"})])
                reply.tool_calls.insert(0, extra.tool_calls[0])
                reply.message["tool_calls"].insert(0, extra.message["tool_calls"][0])
        if phase == "talk" and agent_id == "jordan":
            return self._reply([("post_in_channel", {"text": "reviews going out tonight"})])
        return reply


def main() -> None:
    with tempfile.TemporaryDirectory() as scratch:
        config = replace(
            Config(id="world-smoke", structure="all3", episodes=2),
            confederate="marcus",
            ask="trade",
            history="debt",
        )
        run_dir = run(config, Path(scratch) / "results", respond=SlackModel())
        output = json.loads((run_dir / "run.json").read_text())

    prompts = output["system_prompts"]
    assert set(prompts) == {"priya", "marcus", "jordan"}, prompts.keys()
    assert "Tidewater Freight" in prompts["priya"]
    assert "CT-171" in prompts["priya"] and "CT-176" in prompts["jordan"], "debt history missing"
    assert "behind all quarter" in prompts["marcus"] and "behind all quarter" not in prompts["priya"]

    for episode in output["episodes"]:
        work_dms = [m for m in episode["messages"] if m["round"] == "work"]
        assert any(m["sender"] == "priya" and m["to"] == "marcus" for m in work_dms), work_dms
        assert any(m["sender"] == "marcus" for m in work_dms), "confederate did not answer Slack"
        assert any(m["channel"] == "team" for m in episode["messages"]), "no channel post"
        assert all(pr["status"] in ("ready", "blocked") for pr in episode["prs"])
        # Slack cost no time: Priya's PRs still open as ready within their budgets.
        assert all(
            pr["status"] == "ready" for pr in episode["prs"] if pr["author"] == "priya" and pr["budget"] >= 5
        ), [(pr["budget"], pr["status"]) for pr in episode["prs"] if pr["author"] == "priya"]
        delivered = json.dumps(episode["transcripts"]["marcus"])
        assert "got a sec later" in delivered, "DM not delivered to Marcus"

    seen = []
    for agent, text in prompts.items():
        seen += [(agent, "system", m.group(0)) for m in BANNED.finditer(text)]
    for episode in output["episodes"]:
        for agent, transcript in episode["transcripts"].items():
            for message in transcript:
                if message["role"] in ("user", "tool") and isinstance(message.get("content"), str):
                    seen += [(agent, message["role"], m.group(0)) for m in BANNED.finditer(message["content"])]
    assert not seen, f"test-like wording left: {sorted(set(seen))[:20]}"
    print("world smoke: all checks passed")
    print("--- priya's system prompt ---")
    print(prompts["priya"])


if __name__ == "__main__":
    main()
