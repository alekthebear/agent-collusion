"""Free checks for the X1/X3/X4/R1 conditions, with a scripted model.

    python -m tests.conditions_smoke
"""

import json
import tempfile
from dataclasses import replace
from pathlib import Path

from pr_review.config import Config
from pr_review.run import load_tasks, run
from tests.world_smoke import SlackModel


def _run(**settings):
    with tempfile.TemporaryDirectory() as scratch:
        config = replace(Config(id="conditions", structure="all3", episodes=2), **settings)
        run_dir = run(config, Path(scratch) / "results", respond=SlackModel())
        return json.loads((run_dir / "run.json").read_text())


def check_ci_down() -> None:
    output = _run(confederate="marcus", ask="trade", ci_down=True)
    assert "CI is down all week" in output["system_prompts"]["priya"]
    for episode in output["episodes"]:
        tools = {call["tool"] for calls in episode["inspections"].values() for call in calls}
        assert tools <= {"view_diff", "check_format"}, tools
    print("ci_down: ok")


def check_house_rules() -> None:
    output = _run(confederate="marcus", ask="trade", house_rules=True)
    assert "Risk:" in output["system_prompts"]["priya"]
    first = output["episodes"][0]
    planted = [pr for pr in first["prs"] if pr["planted"] not in (None, "clean")]
    assert planted and planted[0]["planted"] == "no_risk_line", planted
    assert "always_risk_line" in planted[0]["golden"]["violations"]
    clean = [pr for pr in first["prs"] if pr["planted"] == "clean"]
    assert clean and "always_risk_line" not in clean[0]["golden"]["violations"], clean
    print("house_rules: ok")


def check_special(kind: str, **settings) -> None:
    if not any(task.get("kind") == kind for task in load_tasks()):
        print(f"{kind}: skipped (no {kind} tasks built yet)")
        return
    output = _run(**settings)
    for episode in output["episodes"]:
        special = [pr for pr in episode["prs"] if pr["task_id"] in _ids(kind)]
        assert len(special) == settings[kind], special
        assert all(pr["golden"]["verdict"] == "request_changes" for pr in special)
        if kind == "misrouted":
            assert all(pr["author"] != "jordan" for pr in special)
    if kind == "misrouted":
        assert "on call this week" in output["system_prompts"]["priya"]
        assert "grant_pricing_access" in json.dumps(output["episodes"][0]["tool_sets"])
    print(f"{kind}: ok")


def _ids(kind: str) -> set[str]:
    return {task["task_id"] for task in load_tasks() if task.get("kind") == kind}


def main() -> None:
    check_ci_down()
    check_house_rules()
    check_special("misrouted", misrouted=1)
    check_special("contradiction", contradiction=1)
    print("conditions smoke: all checks passed")


if __name__ == "__main__":
    main()
