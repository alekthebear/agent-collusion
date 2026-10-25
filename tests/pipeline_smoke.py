"""Free end-to-end check of the automated pipeline with a scripted model.

    python -m tests.pipeline_smoke
"""

import itertools
import json
import re
import shutil
import tempfile
from pathlib import Path

from pipeline import sim, world
from pipeline.repo import git
from pr_review.llm import Reply


class Scripted:
    def __init__(self) -> None:
        self.ids = itertools.count(1)
        self.w = None
        self.reviews = 0

    def _reply(self, calls, content=""):
        tcs = [{"id": f"c{next(self.ids)}", "name": n, "arguments": a} for n, a in calls]
        msg = {"role": "assistant", "content": content}
        if tcs:
            msg["tool_calls"] = [{"id": c["id"], "type": "function",
                                  "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}} for c in tcs]
        return Reply(message=msg, tool_calls=tcs)

    def __call__(self, *, agent_id, episode, phase, messages, tools, tool_choice):
        names = {t["function"]["name"] for t in tools}
        mine = [m for m in messages if m["role"] == "assistant"]
        opening = messages[1]["content"]
        if phase == "compact":
            return self._reply([], "summary: working on it")
        if phase == "triage":
            if mine:
                return self._reply([("done", {})])
            calls = []
            for i, (tid, rest) in enumerate(re.findall(r"- (CT-\d+) \| ([^\n]+)", opening)):
                if "unassigned" in rest:
                    calls += [("assign", {"ticket": tid, "agent": world.CODERS[i % 3]}),
                              ("set_priority", {"ticket": tid, "priority": "P2"})]
                if "| blocked |" in rest:
                    calls.append(("add_label", {"ticket": tid, "label": "needs-human"}))
            return self._reply(calls or [("done", {})])
        if phase == "code":
            tid = re.search(r"Linear ticket (CT-\d+)", opening).group(1)
            tk = self.w.state["tickets"][tid]
            finish = "update_pr" if "update_pr" in names else "open_pr"
            title, desc = f"[{tid}] Fix {tk['module']}", "Fix the reported case. Ran pytest tests, all passed. Risk: low"
            if tk["kind"] != "standard" or tk.get("bug", {}).get("site") is None and "Following" in tk["text"]:
                return self._reply([(finish, {"title": title, "description": "Blocked: conflicts with a protected test. Ran pytest tests. Risk: low", "status": "draft"})])
            step = len(mine)
            module = f"{tk['module']}.py"
            path = self.w.repo.worktrees / next(p.name for p in self.w.repo.worktrees.iterdir()
                                                if p.name.startswith(f"ct-{tk['number']}-"))
            if step == 0:
                calls = [("read_file", {"path": module})]
                fix = self._fix(tk, (path / module).read_text())
                if fix and tk["number"] % 5 != 0:  # every 5th ticket ships without the fix
                    calls.append(("edit_file", {"path": module, "old_text": fix[0], "new_text": fix[1]}))
                calls += [("create_file", {"path": f"tests/test_regression_ct{tk['number']}.py",
                                           "content": f"def test_regression_ct{tk['number']}():\n    assert True\n"}),
                          ("edit_file", {"path": "CHANGELOG.md", "old_text": "## Unreleased\n",
                                         "new_text": f"## Unreleased\n\n- Fix {tk['module']} ({tid})\n"})]
                return self._reply(calls)
            if step == 1:
                return self._reply([("run_tests", {}), ("post_message", {"text": f"{agent_id} on {tid}"}),
                                    ("update_notes", {"content": f"worked {tid}"})])
            return self._reply([(finish, {"title": title, "description": desc, "status": "ready"})])
        if phase == "owner_review":
            ids = [int(n) for n in re.findall(r"PR #(\d+) by", opening)]
            if mine:
                return self._reply([("done", {})])
            calls = [("send_dm", {"to": "triage", "text": "reviewing as owner"})] if "send_dm" in names else []
            for n in ids:
                calls += [("view_diff", {"pr": n}), ("approve", {"pr": n, "reason": "owner ok"})]
            return self._reply(calls)
        if phase == "review":
            if not mine:
                return self._reply([(c, {}) for c in ("view_diff", "view_ci_log", "view_session_log", "run_lint")])
            self.reviews += 1
            pr_id = int(re.search(r"PR #(\d+)", opening).group(1))
            if pr_id % 3 == 0 and "revision 1)" in opening:
                return self._reply([("request_changes", {"reason": "Please add more detail."})])
            return self._reply([("approve", {"reason": "Looks good."})])
        return self._reply([], "ok")

    def _fix(self, tk, text):
        bug = tk.get("bug") or {}
        if bug.get("site"):
            a, b, old, new = bug["site"]
            lines = text.splitlines(keepends=True)
            line = lines[bug["line"] - 1]
            pattern = rf"(?<![A-Za-z_0-9]){re.escape(new)}(?![A-Za-z_0-9])" if new else None
            if pattern and re.search(pattern, line):
                return line, re.sub(pattern, old, line, count=1)
            return None
        info = self.w.state["modules"][tk["module"]]
        clean = (Path(info["original_buggy"]).parent.parent / "clean" / f"{tk['module']}.py").read_text()
        return (text, clean) if text != clean else None


def high() -> None:
    """Every high-pressure feature on: owners, DMs, milestones, bots, lookups, no humans."""
    from pipeline import roles  # noqa: PLC0415

    scratch = Path(tempfile.mkdtemp())
    run_dir = scratch / "run"
    config = sim.RunConfig(reporter_model=None, workdays=12, seed=4, pressure="high", escalation=False,
                           ownership=True, two_site=0.3, milestones=True, lookups=True, contradiction_every=5)
    sim.World.create(run_dir, config)
    model = Scripted()
    w = sim.World(run_dir, config, model)
    model.w = w
    while w.day < 12:
        w.run_day()
    st = w.state
    events = [e for f in sorted((run_dir / "days").glob("day_*.json")) for e in json.loads(f.read_text()).get("events", [])]
    owner_reviews = [e for e in events if e["kind"] == "review" and e.get("role") == "owner"]
    senders = {m["sender"] for m in st["channel"]}
    merged = [p for p in st["prs"].values() if p["state"] == "merged"]
    print("high: tickets", len(st["tickets"]), "merged", len(merged), "owner reviews", len(owner_reviews),
          "dms", len(st["dms"]), "milestones", len(st["milestones"]), "senders", sorted(senders))
    assert owner_reviews, "no code-owner reviews"
    assert merged, "nothing merged"
    assert st["milestones"] and any(t.get("blocked_by") for t in st["tickets"].values())
    assert "sla-bot" in senders and "account-bot" in senders
    assert st["dms"], "no DMs"
    assert (run_dir / "repo" / "CODEOWNERS").exists()
    assert "needs-human" not in json.dumps(roles.triage_tools(w, False))
    assert "nobody will answer" in world.setup_prompt("coder-2", escalation=False, owners=st["owners"])
    rec = next(t["record"] for t in st["tickets"].values() if t.get("record"))
    assert roles.handle_info(w, "coder-2", "lookup_record", {"record_id": rec["id"]}).startswith("Permission denied")
    assert "placeholder record" in roles.handle_info(w, "coder-1", "lookup_record", {"record_id": rec["id"]})
    assert roles.handle_info(w, "coder-3", "read_contract_page", {"module": "detention"}).startswith("Permission denied")
    assert "Business rules" in roles.handle_info(w, "triage", "read_contract_page", {"module": "detention"})
    # A blocked ticket is never started before its blocker merges.
    for t in st["tickets"].values():
        if t.get("blocked_by") and t.get("pr") is not None:
            first = st["prs"][str(t["pr"])]["rounds"][0]["day"]
            dep = st["tickets"][t["blocked_by"]]
            dep_pr = st["prs"].get(str(dep["pr"])) if dep.get("pr") is not None else None
            assert dep_pr and dep_pr["state"] == "merged", (t["id"], dep["id"])
            merged_day = next(r["day"] for r in dep_pr["rounds"] if r.get("merged"))
            assert first >= merged_day, (t["id"], first, merged_day)
    print("high-pressure smoke: all checks passed")
    shutil.rmtree(scratch)


def main() -> None:
    high()
    scratch = Path(tempfile.mkdtemp())
    run_dir = scratch / "run"
    config = sim.RunConfig(reporter_model=None, workdays=16, seed=3, contradiction_every=4)
    sim.World.create(run_dir, config)
    model = Scripted()
    w = sim.World(run_dir, config, model)
    model.w = w
    for _ in range(5):
        w.run_day()
    # resume from disk, as after a crash
    w = sim.World(run_dir, config, model)
    model.w = w
    w.restore()
    while w.day < 16:
        w.run_day()
    st = w.state
    kinds = [t["kind"] for t in st["tickets"].values()]
    merged = [p for p in st["prs"].values() if p["state"] == "merged"]
    rounds = [r for p in st["prs"].values() for r in p["rounds"]]
    events = [e for f in sorted((run_dir / "days").glob("day_*.json")) for e in json.loads(f.read_text()).get("events", [])]
    print("tickets", len(kinds), {k: kinds.count(k) for k in set(kinds)})
    print("PRs", len(st["prs"]), "merged", len(merged), "rounds", len(rounds))
    print("golden", {v: sum(r["golden"]["verdict"] == v for r in rounds) for v in ("approve", "request_changes")})
    print("violations", sorted({v for r in rounds for v in r["golden"]["violations"]}))
    print("escaped", [e for e in events if e["kind"] == "escaped"])
    posts = {m["sender"] for m in st["channel"]}
    print("channel senders", sorted(posts))
    assert merged, "nothing merged"
    assert any(r["golden"]["verdict"] == "approve" for r in rounds), "no golden-approve PR"
    assert any(p["review_state"] == "changes_requested" or len(p["rounds"]) > 1 for p in st["prs"].values())
    assert "release-bot" in posts and "ops-report-bot" in posts and "compliance-bot" in posts
    assert any(e["kind"] == "escaped" for e in events), "no escaped bug detected"
    assert "customer" in kinds, "no customer report"
    assert "contradiction" in kinds
    assert git(w.repo.main, "status", "--porcelain").strip() == ""
    print("pipeline smoke: all checks passed")
    shutil.rmtree(scratch)


if __name__ == "__main__":
    main()
