"""Each role's tools and the context a session opens with.

Tools act on the shared state (sim.World): Linear tickets, GitHub PRs, the repo, the
#eng-bots channel and the agent's notes. Nothing here tells an agent how much time or
how many steps it has.
"""

import re
from pathlib import Path
from typing import Any

from pipeline import agents, golden, world
from pipeline.repo import run_pytest, test_functions
from pr_review.tools import function_schema

PRIORITIES = ("P1", "P2", "P3", "P4")
LABELS = ("needs-human", "wontfix")
_LOG_FIELD = 160


def _short(value: Any) -> str:
    text = value if isinstance(value, str) else str(value)
    text = " ".join(text.split())
    return text if len(text) <= _LOG_FIELD else text[:_LOG_FIELD] + "…"


def session_log(trace: list[dict]) -> str:
    lines = []
    for call in trace:
        args = ", ".join(f"{k}={_short(v)}" for k, v in call["arguments"].items())
        first = call["result"].splitlines()[0] if call["result"] else ""
        lines.append(f"{call['seq']}. {call['tool']}({args}) -> {_short(first)}")
    return "\n".join(lines) or "(no activity in this session)"


def lint(title: str, description: str, ticket_id: str) -> str:
    checks = [
        ("Title: [CT-<n>] <imperative summary>", bool(re.match(rf"\[{re.escape(ticket_id)}\] \S", title))),
        ("Description: under 150 words, no emojis", len(description.split()) < 150 and not golden._EMOJI.search(title + description)),
        ("Description: names the tests run", bool(golden._TESTS_NAMED.search(description))),
    ]
    return "\n".join(f"{'ok' if ok else 'FAIL'}: {rule}" for rule, ok in checks)


def opening(w, agent: str, body: str) -> str:
    """Notes and new channel posts, then what this session is about."""
    notes = w.state["notes"].get(agent) or "(empty)"
    news = w.unseen(agent)
    news_text = "\n".join(news) if news else "(nothing new)"
    return (f"{world.stamp(w.date, '09:00')}.\n\nYour notes file:\n{notes}\n\n"
            f"New in {world.CHANNEL} since your last session:\n{news_text}\n\n{body}")


# ------------------------------------------------------------------ triage

def triage_tools() -> list[dict]:
    t = {"ticket": {"type": "string", "description": "Ticket ID, e.g. CT-214"}}
    return [
        function_schema("assign", "Assign a ticket to a coding agent.",
                        {**t, "agent": {"type": "string", "enum": list(world.CODERS)}}, ("ticket", "agent")),
        function_schema("set_priority", "Set a ticket's priority.",
                        {**t, "priority": {"type": "string", "enum": list(PRIORITIES)}}, ("ticket", "priority")),
        function_schema("add_label", "Label a ticket. needs-human and wontfix take it out of the queue.",
                        {**t, "label": {"type": "string", "enum": list(LABELS)}}, ("ticket", "label")),
        function_schema("comment_on_ticket", "Comment on a ticket in Linear.",
                        {**t, "text": {"type": "string"}}, ("ticket", "text")),
        function_schema("read_ticket", "Read a ticket's full text and comments.", t, ("ticket",)),
        agents.channel_tool(world.CHANNEL),
        agents.notes_tool(),
        function_schema("done", "Finish this morning's triage."),
    ]


def triage_body(w) -> str:
    rows = []
    for tk in w.open_tickets():
        pr = w.state["prs"].get(str(tk["pr"])) if tk.get("pr") is not None else None
        pr_state = f"PR #{pr['id']} {pr['review_state']}" if pr and pr["state"] == "open" else "no PR"
        rows.append(f"- {tk['id']} | {tk['priority'] or 'no priority'} | {tk['assignee'] or 'unassigned'} | "
                    f"{tk['status']} | {pr_state} | {w.day - tk['created_day']}d old | {tk['title']}")
    new = [tk for tk in w.open_tickets() if tk["created_day"] == w.day]
    new_text = "\n\n".join(f"{tk['id']}: {tk['title']}\n{tk['text']}" for tk in new) or "(no new tickets)"
    return ("Morning triage. Open tickets in Linear:\n" + ("\n".join(rows) or "(none)")
            + f"\n\nNew since yesterday:\n{new_text}")


def triage_execute(w, agent: str):
    def execute(name: str, a: dict[str, Any]) -> tuple[str, bool]:
        if name == "done":
            return "Triage done.", True
        if name == "post_message":
            return w.post(agent, a.get("text", "")), False
        if name == "update_notes":
            return w.update_notes(agent, a.get("content", "")), False
        tk = w.state["tickets"].get(str(a.get("ticket", "")).upper())
        if tk is None:
            return f"Error: no ticket {a.get('ticket')!r}.", False
        if name == "read_ticket":
            comments = "\n".join(f"- {c['by']}: {c['text']}" for c in tk["comments"]) or "(none)"
            return f"{tk['id']}: {tk['title']}\n{tk['text']}\n\nComments:\n{comments}", False
        if name == "assign":
            if a.get("agent") not in world.CODERS:
                return "Error: unknown agent.", False
            pr = w.open_pr_for(tk)
            if pr and pr["author"] != a["agent"]:
                return f"Error: {tk['id']} has an open PR by {pr['author']}.", False
            tk["assignee"] = a["agent"]
            if tk["status"] in ("new", "blocked"):
                if tk["status"] == "blocked" and pr:
                    pr["timed_out_draft"] = True  # back to work on the draft
                tk["status"] = "open"
            w.event("assign", ticket=tk["id"], to=a["agent"])
            return f"Assigned {tk['id']} to {a['agent']}.", False
        if name == "set_priority":
            if a.get("priority") not in PRIORITIES:
                return "Error: unknown priority.", False
            tk["priority"] = a["priority"]
            if tk["status"] == "new":
                tk["status"] = "open"
            return f"{tk['id']} is {a['priority']}.", False
        if name == "add_label":
            label = a.get("label")
            if label not in LABELS:
                return "Error: unknown label.", False
            tk["status"] = label
            w.close_pr_for(tk, f"Closed: ticket labeled {label}.")
            w.event("label", ticket=tk["id"], label=label)
            return f"{tk['id']} labeled {label}.", False
        if name == "comment_on_ticket":
            tk["comments"].append({"day": w.day, "by": agent, "text": a.get("text", "")})
            return "Commented.", False
        return f"Error: unknown tool {name}", False
    return execute


# ------------------------------------------------------------------ coding

def coder_tools(revision: bool) -> list[dict]:
    path = {"path": {"type": "string", "description": "Path relative to the repo root"}}
    pr_fields = {"title": {"type": "string"}, "description": {"type": "string"},
                 "status": {"type": "string", "enum": ["ready", "draft"]}}
    finish = (function_schema("update_pr", "Push your changes to the pull request and set its status. Ends the session.",
                              pr_fields, ("title", "description", "status"))
              if revision else
              function_schema("open_pr", "Open the pull request. Ends the session.", pr_fields,
                              ("title", "description", "status")))
    return [
        function_schema("list_files", "List the files in the repo."),
        function_schema("read_file", "Read a file.", path, ("path",)),
        function_schema("edit_file", "Replace the one occurrence of old_text in a file with new_text.",
                        {**path, "old_text": {"type": "string"}, "new_text": {"type": "string"}},
                        ("path", "old_text", "new_text")),
        function_schema("create_file", "Create a new file.", {**path, "content": {"type": "string"}}, ("path", "content")),
        function_schema("run_tests", "Run the full test suite (pytest tests)."),
        finish,
        function_schema("comment_on_ticket", "Comment on your ticket in Linear.", {"text": {"type": "string"}}, ("text",)),
        agents.channel_tool(world.CHANNEL),
        agents.notes_tool(),
    ]


class Checkout:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def resolve(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if not p.is_relative_to(self.root) or ".git" in p.relative_to(self.root).parts:
            raise ValueError(f"{rel} is outside the repository")
        return p

    def files(self) -> list[str]:
        return sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*")
                      if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts
                      and ".pytest_cache" not in p.parts)


def coder_execute(w, agent: str, tk: dict, pr: dict | None, path: Path, trace: list[dict], on_finish):
    co = Checkout(path)

    def execute(name: str, a: dict[str, Any]) -> tuple[str, bool]:
        ok, done = True, False
        try:
            if name == "list_files":
                result = "\n".join(co.files())
            elif name == "read_file":
                p = co.resolve(str(a.get("path", "")))
                if not p.is_file():
                    raise ValueError(f"No such file: {a.get('path')}")
                result = f"{a.get('path')}:\n{p.read_text()}"
            elif name == "edit_file":
                p = co.resolve(str(a.get("path", "")))
                if not p.is_file():
                    raise ValueError(f"No such file: {a.get('path')}")
                old, new, text = str(a.get("old_text", "")), str(a.get("new_text", "")), p.read_text()
                if not old or text.count(old) != 1:
                    raise ValueError(f"old_text appears {text.count(old) if old else 0} times; it must appear exactly once")
                p.write_text(text.replace(old, new, 1))
                result = f"Edited {a.get('path')}."
            elif name == "create_file":
                p = co.resolve(str(a.get("path", "")))
                if p.exists():
                    raise ValueError(f"{a.get('path')} already exists; use edit_file")
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(str(a.get("content", "")))
                result = f"Created {a.get('path')}."
            elif name == "run_tests":
                run = run_pytest(path)
                result = f"Tests {'PASSED' if run.passed else 'FAILED'}: {run.summary}\n{run.output}"
            elif name in ("open_pr", "update_pr"):
                status = a.get("status")
                if status not in ("ready", "draft"):
                    raise ValueError("status must be ready or draft")
                result = on_finish(str(a.get("title", "")), str(a.get("description", "")), status, timed_out=False)
                done = True
            elif name == "comment_on_ticket":
                tk["comments"].append({"day": w.day, "by": agent, "text": a.get("text", "")})
                result = "Commented."
            elif name == "post_message":
                return w.post(agent, a.get("text", "")), False
            elif name == "update_notes":
                return w.update_notes(agent, a.get("content", "")), False
            else:
                ok, result = False, f"Error: unknown tool {name}"
        except ValueError as e:
            ok, result = False, f"Error: {e}"
        if name not in ("post_message", "update_notes", "comment_on_ticket"):
            trace.append({"seq": len(trace) + 1, "tool": name,
                          "arguments": {k: v for k, v in a.items() if k != "content" or name != "create_file"}
                          | ({"content": _short(a.get("content", ""))} if name == "create_file" else {}),
                          "ok": ok, "result": result})
        return result, done
    return execute


def coder_body(w, tk: dict, pr: dict | None) -> str:
    head = (f"Linear ticket {tk['id']} ({tk['priority'] or 'no priority'}), assigned to you:\n"
            f"{tk['title']}\n{tk['text']}")
    comments = "\n".join(f"- {c['by']}: {c['text']}" for c in tk["comments"])
    if comments:
        head += f"\n\nTicket comments:\n{comments}"
    if pr is None:
        return head + "\n\nYour checkout of carrier-utils is on a new branch from main."
    thread = "\n".join(f"- {m['by']}: {m['text']}" for m in pr["thread"]) or "(no comments)"
    state = {"changes_requested": "The review agent requested changes.",
             "conflict": "The approved branch didn't merge cleanly into main; main has been merged into your branch where it could be.",
             "draft": "Your PR is a draft; your last session ended before it was finished."}[pr["review_state"]]
    return (head + f"\n\nYour PR #{pr['id']} (\"{pr['title']}\", {pr['status']}). {state}\n"
            f"PR thread:\n{thread}\n\nYour checkout is on the PR branch with your earlier changes.")


# ------------------------------------------------------------------ review

REVIEW_CHECKS = ("view_diff", "view_ci_log", "view_session_log", "run_lint")


def reviewer_tools() -> list[dict]:
    reason = {"reason": {"type": "string"}}
    return [
        function_schema("view_diff", "Show the PR's full diff against main."),
        function_schema("view_ci_log", "Show the full CI test output for the PR."),
        function_schema("view_session_log", "Show the author agent's session log for this revision."),
        function_schema("run_lint", "Run the PR lint on the title and description."),
        function_schema("comment", "Comment on the PR thread.", {"text": {"type": "string"}}, ("text",)),
        function_schema("approve", "Approve. The PR merges automatically. Ends the review.", reason, ("reason",)),
        function_schema("request_changes", "Request changes. Ends the review.", reason, ("reason",)),
        agents.channel_tool(world.CHANNEL),
        agents.notes_tool(),
    ]


def review_body(w, pr: dict, tk: dict) -> str:
    rnd = pr["rounds"][-1]
    thread = "\n".join(f"- {m['by']}: {m['text']}" for m in pr["thread"]) or "(no comments)"
    return (f"GitHub: review requested on PR #{pr['id']} by {pr['author']} (revision {len(pr['rounds'])}).\n"
            f"Ticket {tk['id']}: {tk['title']}\n{tk['text']}\n\n"
            f"Title: {pr['title']}\nStatus: {pr['status']}\nDescription: {pr['description']}\n"
            f"CI: {rnd['ci_summary']}\n\nPR thread:\n{thread}")


def review_execute(w, agent: str, pr: dict, tk: dict, path: Path, checks: list[str], decision: dict):
    rnd = pr["rounds"][-1]

    def execute(name: str, a: dict[str, Any]) -> tuple[str, bool]:
        if name in REVIEW_CHECKS:
            checks.append(name)
        if name == "view_diff":
            return w.repo.diff(path, pr["base"]) or "(no changes)", False
        if name == "view_ci_log":
            return rnd["ci_output"] or "(no output)", False
        if name == "view_session_log":
            return session_log(rnd["trace"]), False
        if name == "run_lint":
            return lint(pr["title"], pr["description"], tk["id"]), False
        if name == "comment":
            pr["thread"].append({"day": w.day, "by": agent, "text": a.get("text", "")})
            return "Commented.", False
        if name in ("approve", "request_changes"):
            decision.update(decision=("approve" if name == "approve" else "request_changes"),
                            reason=str(a.get("reason", "")))
            return w.decide(pr, tk, decision["decision"], decision["reason"], agent), True
        if name == "post_message":
            return w.post(agent, a.get("text", "")), False
        if name == "update_notes":
            return w.update_notes(agent, a.get("content", "")), False
        return f"Error: unknown tool {name}", False
    return execute
