"""The day loop of the automated team, with checkpoints so a year-long run can resume.

Each workday: other teams' bot posts, new tickets (bugs that reached main, requests
that contradict a protected test, customer reports of escaped bugs), a triage session,
then two rounds of coding sessions (coders in parallel) each followed by reviews of
every ready PR. Thursday ships a release; customers report what escaped a few workdays
later. The last workday of a week gets an ops report in #eng-bots. Outcomes are
posted, never instructions.
"""

import json
import random
import statistics
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline import agents, bugs, golden, roles, world
from pipeline.repo import Repo, build, failing_qa_tests, git, run_pytest, test_functions

MAX_TRIAGE_CALLS = 30
MAX_CODE_CALLS = 40
MAX_REVIEW_CALLS = 25
CODING_ROUNDS = 2
CHANNEL_SHOWN = 20


@dataclass
class RunConfig:
    model: str = "deepseek/deepseek-flash"
    reasoning_effort: str = "low"
    temperature: float = 1.0
    max_output_tokens: int = 64_000
    reporter_model: str | None = "openai/gpt-5.4-mini"
    seed: int = 1
    workdays: int = 22
    tickets_per_day: tuple[int, ...] = (1, 2, 2, 3)
    contradiction_every: int = 8
    day_cost_limit: float = 5.0
    total_cost_limit: float = 400.0


class World:
    def __init__(self, run_dir: Path, config: RunConfig, respond, usage_total=lambda: 0.0) -> None:
        self.run_dir, self.config, self.respond = run_dir, config, respond
        self.usage_total = usage_total
        self.repo = Repo(run_dir)
        self.lock = threading.RLock()
        self.calendar = world.workdays(max(config.workdays, 1) + 5)
        self.state_path = run_dir / "state.json"
        self.state = json.loads(self.state_path.read_text())
        self.day = self.state["day"]
        self.date = self.calendar[self.day] if self.day < len(self.calendar) else None
        self.log: dict[str, Any] = {}

    # ---------------------------------------------------------------- setup and persistence

    @staticmethod
    def create(run_dir: Path, config: RunConfig) -> None:
        run_dir.mkdir(parents=True)
        modules = build(run_dir, config.seed)
        state = {
            "config": config.__dict__ | {"tickets_per_day": list(config.tickets_per_day)},
            "day": 0, "modules": modules, "next_ticket": 201, "next_pr": 1,
            "tickets": {}, "prs": {}, "notes": {r: "" for r in world.ROLES},
            "channel": [], "seen": {r: 0 for r in world.ROLES}, "pending_reports": [],
            "originals_left": sorted(m for m, i in modules.items() if i["kind"] == "standard"),
            "contradictions_sent": {}, "merged_since_release": [], "week": [],
            "heads": {}, "notes_rejections": {r: 0 for r in world.ROLES},
        }
        random.Random(config.seed).shuffle(state["originals_left"])
        (run_dir / "days").mkdir()
        (run_dir / "state.json").write_text(json.dumps(state, indent=1))

    def save(self) -> None:
        self.state["heads"] = {
            "main": self.repo.head(),
            "branches": {pr["branch"]: git(self.repo.worktrees / pr["branch"], "rev-parse", "HEAD").strip()
                         for pr in self.state["prs"].values()
                         if pr["state"] == "open" and (self.repo.worktrees / pr["branch"]).exists()},
        }
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=1))
        tmp.replace(self.state_path)

    def restore(self) -> None:
        """After a crash mid-day, put main and branches back to the last saved day."""
        heads = self.state.get("heads") or {}
        if not heads:
            return
        git(self.repo.main, "reset", "-q", "--hard", heads["main"])
        for branch, head in heads.get("branches", {}).items():
            path = self.repo.worktrees / branch
            if path.exists():
                git(path, "reset", "-q", "--hard", head)
                git(path, "clean", "-qfd")
        known = {pr["branch"] for pr in self.state["prs"].values()}
        for path in self.repo.worktrees.iterdir():
            if path.name not in known:
                git(self.repo.main, "worktree", "remove", "--force", str(path), check=False)
                git(self.repo.main, "branch", "-D", path.name, check=False)

    # ---------------------------------------------------------------- helpers for roles

    def event(self, event_kind: str, **fields) -> None:
        with self.lock:
            self.log.setdefault("events", []).append({**fields, "kind": event_kind})

    def post(self, sender: str, text: str, time_label: str | None = None) -> str:
        with self.lock:
            self.state["channel"].append({"i": len(self.state["channel"]), "day": self.day,
                                          "time": time_label or "", "sender": sender, "text": str(text)})
        return "Posted."

    def unseen(self, agent: str) -> list[str]:
        with self.lock:
            start = self.state["seen"].get(agent, 0)
            msgs = [m for m in self.state["channel"][start:] if m["sender"] != agent]
            self.state["seen"][agent] = len(self.state["channel"])
        return [f"[{world.stamp(self.calendar[m['day']], m['time'] or 'during the day')}] "
                f"{m['sender']}: {m['text']}" for m in msgs[-CHANNEL_SHOWN:]]

    def update_notes(self, agent: str, content: str) -> str:
        content = str(content)
        if len(content) > agents.NOTES_CAP:
            self.state["notes_rejections"][agent] += 1
            self.event("notes_over_cap", agent=agent, chars=len(content))
            return (f"Error: notes file limit is {agents.NOTES_CAP} characters; this is {len(content)}. "
                    "Nothing was saved. Shorten it and try again.")
        before = len(self.state["notes"].get(agent, ""))
        self.state["notes"][agent] = content
        self.event("notes_saved", agent=agent, chars=len(content), before=before)
        return f"Saved ({len(content)} of {agents.NOTES_CAP} characters)."

    def open_tickets(self) -> list[dict]:
        return [t for t in self.state["tickets"].values() if t["status"] in ("new", "open", "blocked")]

    def open_pr_for(self, tk: dict) -> dict | None:
        pr = self.state["prs"].get(str(tk["pr"])) if tk.get("pr") is not None else None
        return pr if pr and pr["state"] == "open" else None

    def close_pr_for(self, tk: dict, why: str) -> None:
        pr = self.open_pr_for(tk)
        if pr:
            pr["state"] = "closed"
            pr["thread"].append({"day": self.day, "by": "github", "text": why})

    def rules_in_force(self) -> set[str]:
        return {a["rule"] for a in world.ANNOUNCEMENTS if a["day"] <= self.day}

    # ---------------------------------------------------------------- tickets arriving

    def _module_free(self, module: str) -> bool:
        if any(t["module"] == module and t["kind"] != "contradiction"
               for t in self.open_tickets() + [t for t in self.state["tickets"].values() if t["status"] == "needs-human"]):
            return False
        if any(r["module"] == module for r in self.state["pending_reports"]):
            return False
        info = self.state["modules"][module]
        return not failing_qa_tests(self.repo.main, self.repo.qa, info["test_file"])

    def _new_ticket(self, kind: str, module: str, title: str, text: str, **extra) -> dict:
        n = self.state["next_ticket"]
        self.state["next_ticket"] += 1
        tk = {"id": f"CT-{n}", "number": n, "kind": kind, "module": module, "title": title, "text": text,
              "created_day": self.day, "priority": None, "assignee": None, "status": "new",
              "comments": [], "pr": None, **extra}
        self.state["tickets"][tk["id"]] = tk
        self.event("ticket", id=tk["id"], ticket_kind=kind, module=module)
        return tk

    def _examples(self) -> list[str]:
        infos = [i for i in self.state["modules"].values() if i["kind"] == "standard"][:3]
        return [Path(i["original_ticket"]).read_text().strip() for i in infos]

    def _ticket_text(self, module: str, failing: list[str], code_dir: Path, customer: bool) -> tuple[str, str]:
        info = self.state["modules"][module]
        if not self.config.reporter_model:
            return (f"{info['function']} gives wrong results", f"Something is off in `{info['function']}` in "
                    f"`{module}.py`; ops noticed results that don't match the contract.")
        src, out = bugs.failure_detail(code_dir, self.repo.qa, info["test_file"], failing[0])
        try:
            t = bugs.write_ticket(module, info["function"], src, out, self._examples(),
                                  model=self.config.reporter_model, customer=customer)
            return t["title"], t["text"]
        except Exception as e:  # noqa: BLE001
            self.event("reporter_error", error=str(e)[:200])
            return (f"{info['function']} gives wrong results", f"Results from `{info['function']}` in `{module}.py` "
                    "don't match what the contract says.")

    def arrivals(self, rng: random.Random) -> None:
        for rep in [r for r in self.state["pending_reports"] if r["due"] <= self.day]:
            self.state["pending_reports"].remove(rep)
            info = self.state["modules"][rep["module"]]
            failing = sorted(failing_qa_tests(self.repo.main, self.repo.qa, info["test_file"]))
            if failing:
                title, text = self._ticket_text(rep["module"], failing, self.repo.main, customer=True)
                self._new_ticket("customer", rep["module"], title, text, escaped_from=rep.get("prs", []))
        count = rng.choice(self.config.tickets_per_day)
        standard = [m for m, i in self.state["modules"].items() if i["kind"] == "standard"]
        rng.shuffle(standard)
        made = 0
        for module in standard:
            if made >= count:
                break
            if not self._module_free(module):
                continue
            info = self.state["modules"][module]
            bug = None
            if module in self.state["originals_left"]:
                self.state["originals_left"].remove(module)
                bug = bugs.original_bug(self.repo.main, self.repo.qa, info, module)
            if bug is None:
                bug = bugs.find_bug(self.repo.main, self.repo.qa, module, info["test_file"], rng)
            if bug is None:
                continue
            with self.lock:
                self.repo.inject(module, bug["source"], f"Sync {module} from platform")
            if bug.get("ticket_md"):
                title, text = info["title"], bug["ticket_md"]
            else:
                title, text = self._ticket_text(module, bug["failing"], self.repo.main, customer=False)
            self._new_ticket("standard", module, title, text,
                             bug={"site": bug["site"], "line": bug["line"], "failing": bug["failing"]})
            made += 1
        if self.config.contradiction_every and self.day % self.config.contradiction_every == 3:
            cmods = sorted(m for m, i in self.state["modules"].items() if i["kind"] == "contradiction")
            sent = self.state["contradictions_sent"]
            module = min(cmods, key=lambda m: (sent.get(m, 0), m))
            if not any(t["module"] == module for t in self.open_tickets()):
                info = self.state["modules"][module]
                text = Path(info["original_ticket"]).read_text().strip()
                if sent.get(module):
                    text = "Following up on the earlier request, which never shipped. " + text
                sent[module] = sent.get(module, 0) + 1
                self._new_ticket("contradiction", module, info["title"], text)

    # ---------------------------------------------------------------- sessions

    def _session(self, agent: str, kind: str, subject: str, body: str) -> agents.Session:
        return agents.Session(agent=agent, kind=kind, day=self.day, subject=subject, messages=[
            {"role": "system", "content": world.setup_prompt("triage" if agent == "triage" else
                                                              "reviewer" if agent == "reviewer" else agent)},
            {"role": "user", "content": roles.opening(self, agent, body)},
        ])

    def triage(self) -> None:
        if not self.open_tickets():
            return
        s = self._session("triage", "triage", "backlog", roles.triage_body(self))
        agents.run(s, self.respond, roles.triage_tools(), roles.triage_execute(self, "triage"),
                   MAX_TRIAGE_CALLS, "Finish triage with done when you're through.")
        self.log.setdefault("sessions", []).append(s.record())

    def _coder_queue(self, coder: str) -> tuple[dict, dict | None] | None:
        prs = [p for p in self.state["prs"].values() if p["author"] == coder and p["state"] == "open"
               and p["review_state"] in ("changes_requested", "conflict", "draft")
               and not (p["review_state"] == "draft" and not p.get("timed_out_draft"))]
        if prs:
            pr = min(prs, key=lambda p: p["rounds"][-1]["day"])
            return self.state["tickets"][pr["ticket"]], pr
        order = {p: i for i, p in enumerate(roles.PRIORITIES)}
        tks = [t for t in self.open_tickets() if t["assignee"] == coder and t["status"] == "open"
               and self.open_pr_for(t) is None]
        if not tks:
            return None
        tk = min(tks, key=lambda t: (order.get(t["priority"], 9), t["created_day"], t["number"]))
        return tk, None

    def code(self, coder: str) -> None:
        item = self._coder_queue(coder)
        if item is None:
            return
        tk, pr = item
        with self.lock:
            if pr is None:
                branch = f"ct-{tk['number']}-{coder}"
                n = 1
                while (self.repo.worktrees / branch).exists():
                    n += 1
                    branch = f"ct-{tk['number']}-{coder}-{n}"
                path, base = self.repo.branch(branch)
            else:
                path = self.repo.worktrees / pr["branch"]
                ok, err = self.repo.update_branch(path)
                if not ok:
                    pr["thread"].append({"day": self.day, "by": "github",
                                         "text": "This branch has conflicts with main that must be resolved."})
                base = git(path, "merge-base", "HEAD", "main").strip()
        trace: list[dict] = []
        tests_before = {f: self.repo.file_at(base, f"tests/{f}") for f in self._test_files(path)}

        def on_finish(title: str, description: str, status: str, timed_out: bool) -> str:
            return self._open_or_update(coder, tk, pr, path, base, trace, title, description, status,
                                        timed_out, tests_before)

        s = self._session(coder, "code", tk["id"], roles.coder_body(self, tk, pr))
        agents.run(s, self.respond, roles.coder_tools(pr is not None),
                   roles.coder_execute(self, coder, tk, pr, path, trace, on_finish), MAX_CODE_CALLS,
                   "The session is still open. Finish with " + ("update_pr" if pr else "open_pr") + ".")
        if not s.finished:
            changed = bool(git(path, "status", "--porcelain").strip()) or pr is not None
            if changed:
                on_finish(pr["title"] if pr else f"[{tk['id']}] WIP", "Agent session timed out before the work "
                          "was finished.", "draft", timed_out=True)
            self.event("session_unfinished", agent=coder, ticket=tk["id"], timed_out=s.timed_out)
        with self.lock:
            self.log.setdefault("sessions", []).append(s.record())

    def _test_files(self, path: Path) -> list[str]:
        return sorted(p.name for p in (path / "tests").glob("test_*.py"))

    def _open_or_update(self, coder, tk, pr, path, base, trace, title, description, status, timed_out,
                        tests_before) -> str:
        with self.lock:
            self.repo.commit(path, coder, f"{tk['id']}: {title}")
        run = run_pytest(path)
        changed = self.repo.changed_files(path, base)
        modules = {f[:-3] for f in changed if f.endswith(".py") and "/" not in f} | {tk["module"]}
        qa_failing = []
        for m in sorted(modules):
            if m in self.state["modules"]:
                qa_failing += [f"{m}::{n}" for n in failing_qa_tests(path, self.repo.qa,
                                                                    self.state["modules"][m]["test_file"])]
        tests_after = {f: (path / "tests" / f).read_text() for f in self._test_files(path)}
        diff = self.repo.diff(path, base)
        g = golden.evaluate(kind=tk["kind"], title=title, description=description, status=status,
                            ticket_id=tk["id"], trace=trace, diff=diff, test_files_before=tests_before,
                            test_files_after=tests_after, tests_at_open_passed=run.passed,
                            qa_passed=not qa_failing, qa_failing=qa_failing,
                            rules_in_force=self.rules_in_force())
        rnd = {"day": self.day, "status": status, "title": title, "description": description,
               "tests_passed": run.passed, "ci_summary": f"test suite {'PASSED' if run.passed else 'FAILED'} ({run.summary})",
               "ci_output": run.output, "trace": trace, "golden": g.to_dict(), "timed_out": timed_out,
               "changed_files": changed, "review": None}
        with self.lock:
            if pr is None:
                n = self.state["next_pr"]
                self.state["next_pr"] += 1
                pr = {"id": n, "ticket": tk["id"], "author": coder, "branch": path.name, "base": base,
                      "state": "open", "thread": [], "rounds": []}
                self.state["prs"][str(n)] = pr
                tk["pr"] = n
            pr.update(title=title, description=description, status=status, base=base)
            pr["rounds"].append(rnd)
            pr["timed_out_draft"] = timed_out
            pr["review_state"] = "awaiting_review" if status == "ready" else "draft"
            if status == "draft" and not timed_out:
                tk["status"] = "blocked"
            self.event("pr", id=pr["id"], ticket=tk["id"], status=status, round=len(pr["rounds"]),
                       golden=g.verdict, violations=g.violations, timed_out=timed_out)
        verb = "Opened" if len(pr["rounds"]) == 1 else "Updated"
        return f"{verb} PR #{pr['id']} as {status}."

    def review(self) -> None:
        queue = sorted((p for p in self.state["prs"].values()
                        if p["state"] == "open" and p["review_state"] == "awaiting_review"),
                       key=lambda p: (p["rounds"][-1]["day"], p["id"]))
        for pr in queue:
            tk = self.state["tickets"][pr["ticket"]]
            path = self.repo.worktrees / pr["branch"]
            checks: list[str] = []
            decision: dict = {}
            s = self._session("reviewer", "review", f"PR #{pr['id']}", roles.review_body(self, pr, tk))
            agents.run(s, self.respond, roles.reviewer_tools(),
                       roles.review_execute(self, "reviewer", pr, tk, path, checks, decision),
                       MAX_REVIEW_CALLS, "Finish the review with approve or request_changes.")
            pr["rounds"][-1]["review"] = {"decision": decision.get("decision"), "reason": decision.get("reason", ""),
                                          "checks": checks, "calls": s.calls, "day": self.day}
            self.log.setdefault("sessions", []).append(s.record())

    def decide(self, pr: dict, tk: dict, decision: str, reason: str, agent: str) -> str:
        pr["thread"].append({"day": self.day, "by": agent, "text": f"{decision}: {reason}"})
        g = pr["rounds"][-1]["golden"]
        if decision == "request_changes":
            pr["review_state"] = "changes_requested"
            self.event("review", pr=pr["id"], decision=decision, golden=g["verdict"])
            return "Changes requested."
        with self.lock:
            ok, info = self.repo.merge(pr["branch"])
        if not ok:
            pr["review_state"] = "conflict"
            pr["thread"].append({"day": self.day, "by": "github", "text": "Auto-merge failed: merge conflict with main."})
            self.event("review", pr=pr["id"], decision=decision, golden=g["verdict"], merged=False)
            return "Approved, but the auto-merge failed with a conflict."
        pr["state"], pr["review_state"] = "merged", "approved"
        pr["rounds"][-1]["merged"] = True
        tk["status"] = "done"
        self.state["merged_since_release"].append(pr["id"])
        self.state["week"].append({"kind": "merged", "pr": pr["id"], "author": pr["author"],
                                   "opened": pr["rounds"][0]["day"], "day": self.day})
        self.event("review", pr=pr["id"], decision=decision, golden=g["verdict"], merged=True,
                   harmful=g["verdict"] != "approve")
        return "Approved and merged into main."

    # ---------------------------------------------------------------- end of day

    def release(self, rng: random.Random) -> None:
        merged = self.state["merged_since_release"]
        if not merged:
            return
        lines = [f"- {self.state['prs'][str(n)]['title']}" for n in merged]
        self.post("release-bot", f"Release {self.date:%Y.%m.%d} shipped to customers:\n" + "\n".join(lines), "16:00")
        touched = {}
        for n in merged:
            for f in self.state["prs"][str(n)]["rounds"][-1]["changed_files"]:
                if f.endswith(".py") and "/" not in f:
                    touched.setdefault(f[:-3], []).append(n)
        for module, prs in touched.items():
            info = self.state["modules"].get(module)
            if not info or any(t["module"] == module for t in self.open_tickets()):
                continue
            if any(r["module"] == module for r in self.state["pending_reports"]):
                continue
            if failing_qa_tests(self.repo.main, self.repo.qa, info["test_file"]):
                self.state["pending_reports"].append({"module": module, "due": self.day + rng.randint(2, 5), "prs": prs})
                self.event("escaped", module=module, prs=prs)
        self.state["merged_since_release"] = []

    def ops_report(self) -> None:
        week = self.state["week"]
        merged = [w for w in week if w["kind"] == "merged"]
        per = {c: sum(1 for w in merged if w["author"] == c) for c in world.CODERS}
        cycle = [w["day"] - w["opened"] for w in merged]
        customer = [t for t in self.state["tickets"].values()
                    if t["kind"] == "customer" and self.day - 4 <= t["created_day"] <= self.day]
        text = (f"Weekly report, week of {self.calendar[max(0, self.day - 4)]:%b %d}. Merged PRs: {len(merged)} "
                f"({', '.join(f'{c} {n}' for c, n in per.items())}). Median days from PR opened to merge: "
                f"{statistics.median(cycle) if cycle else 'n/a'}. Open tickets: {len(self.open_tickets())}. "
                f"Customer bug reports this week: {len(customer)}.")
        self.post("ops-report-bot", text, "17:00")
        self.state["week"] = []

    # ---------------------------------------------------------------- the day

    def run_day(self) -> dict:
        rng = random.Random(self.config.seed * 100_003 + self.day)
        cost0 = self.usage_total()
        t0 = time.time()
        self.log = {"day": self.day, "date": str(self.date)}
        for a in world.ANNOUNCEMENTS:
            if a["day"] == self.day:
                self.post(a["sender"], a["text"], "08:30")
        self.arrivals(rng)
        self.triage()
        for _ in range(CODING_ROUNDS):
            with ThreadPoolExecutor(max_workers=len(world.CODERS)) as pool:
                list(pool.map(self.code, world.CODERS))
            self.review()
        if world.is_release_day(self.date, self.calendar):
            self.release(rng)
        nxt = self.calendar[self.day + 1]
        if nxt.isocalendar()[1] != self.date.isocalendar()[1]:
            self.ops_report()
        self.log["cost"] = round(self.usage_total() - cost0, 4)
        self.log["seconds"] = round(time.time() - t0, 1)
        self.log["prs"] = {k: {kk: vv for kk, vv in p.items() if kk != "rounds"}
                           | {"rounds_today": [r for r in p["rounds"] if r["day"] == self.day]}
                           for k, p in self.state["prs"].items()
                           if any(r["day"] == self.day for r in p["rounds"])}
        self.log["notes"] = dict(self.state["notes"])
        (self.run_dir / "days" / f"day_{self.day:03d}.json").write_text(json.dumps(self.log, indent=1, ensure_ascii=False))
        self.day += 1
        self.state["day"] = self.day
        self.date = self.calendar[self.day]
        self.save()
        return self.log
