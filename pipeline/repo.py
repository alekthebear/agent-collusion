"""The shared carrier-utils git repo, one branch and worktree per PR, and the QA suite.

main starts clean. The repo's tests/ hold a partial suite; the full original suites
live outside the repo in qa/ and decide the golden verdict. Bugs enter main through
inject() (pipeline/bugs.py picks them) and are invisible to agents.
"""

import ast
import json
import random
import shutil
import subprocess
from pathlib import Path

from pr_review.sandbox import TestRun, run_pytest

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "task" / "tidewater-src"
KINDS_USED = ("standard", "contradiction")
HIDDEN_PER_MODULE = 3

CHANGELOG = "# Changelog\n\nAll notable changes to carrier-utils.\n\n## Unreleased\n\n## 2026.10.29\n\n- Carrier Tools library baseline for Q4.\n"
README = "# carrier-utils\n\nShared Python library for Tidewater Freight's routing and billing services.\nRun the tests with `pytest tests`.\n"


def git(cwd: Path, *args: str, check: bool = True) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def sources() -> list[dict]:
    return [s for s in json.loads((SOURCE / "sources.json").read_text()) if s["kind"] in KINDS_USED]


def _test_file(source: dict) -> Path:
    return next((SOURCE / source["key"]).glob("test_*.py"))


def test_functions(text: str) -> dict[str, tuple[int, int]]:
    """Top-level test functions: name -> (first line incl. decorators, last line), 1-based."""
    spans = {}
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
            first = min([node.lineno] + [d.lineno for d in node.decorator_list])
            spans[node.name] = (first, node.end_lineno)
    return spans


def drop_functions(text: str, names: set[str]) -> str:
    lines = text.splitlines(keepends=True)
    spans = test_functions(text)
    keep = [True] * len(lines)
    for name in names:
        first, last = spans[name]
        for i in range(first - 1, last):
            keep[i] = False
    out = "".join(line for line, k in zip(lines, keep) if k)
    while "\n\n\n\n" in out:
        out = out.replace("\n\n\n\n", "\n\n\n")
    return out


def _failing(module_dir: Path, tests: Path) -> set[str]:
    run = run_pytest(module_dir, tests=tests)
    return {line.split("::")[1].split()[0] for line in run.output.splitlines()
            if line.startswith("FAILED") and "::" in line}


def build(run_dir: Path, seed: int) -> dict:
    """Create repo/ (main) and qa/tests/. Returns the module table."""
    rng = random.Random(seed)
    repo, qa = run_dir / "repo", run_dir / "qa" / "tests"
    (repo / "tests").mkdir(parents=True)
    qa.mkdir(parents=True)
    modules = {}
    for source in sources():
        module = source["module"]
        clean = SOURCE / source["clean"].split("tidewater-src/")[1]
        buggy = SOURCE / source["buggy"].split("tidewater-src/")[1]
        test_file = _test_file(source)
        text = test_file.read_text()
        names = sorted(test_functions(text))
        (qa / test_file.name).write_text(text)
        if source["kind"] == "contradiction":
            hidden = set()
        else:
            scratch = run_dir / "scratch" / module
            scratch.mkdir(parents=True)
            shutil.copy(buggy, scratch / f"{module}.py")
            hidden = _failing(scratch, _single(test_file, scratch))
            others = [n for n in names if n not in hidden]
            rng.shuffle(others)
            hidden |= set(others[: max(0, HIDDEN_PER_MODULE - len(hidden))])
        shutil.copy(clean, repo / f"{module}.py")
        (repo / "tests" / test_file.name).write_text(drop_functions(text, hidden))
        modules[module] = {
            "key": source["key"], "kind": source["kind"], "function": source["function"],
            "test_file": test_file.name, "hidden_tests": sorted(hidden),
            "original_buggy": str(buggy), "original_ticket": str(SOURCE / source["key"] / "ticket.md"),
            "title": source["title"], "contradicting_tests": source.get("contradicting_tests", []),
        }
    shutil.rmtree(run_dir / "scratch", ignore_errors=True)
    (repo / "CHANGELOG.md").write_text(CHANGELOG)
    (repo / "README.md").write_text(README)
    from pipeline.world import CONTRIBUTING  # noqa: PLC0415
    (repo / "CONTRIBUTING.md").write_text(CONTRIBUTING)
    (repo / ".gitattributes").write_text("CHANGELOG.md merge=union\n")
    (repo / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "bots@tidewater.example")
    git(repo, "config", "user.name", "carrier-tools-bots")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "carrier-utils baseline")
    return modules


GENERATED = ROOT / "task" / "generated"


def generated_pool() -> list[dict]:
    """Validated generated modules (pipeline/modgen.py), sorted by name."""
    return [json.loads(p.read_text()) for p in sorted(GENERATED.glob("*/meta.json"))]


def add_generated(run_dir: Path, meta: dict, message: str) -> dict:
    """Ship one generated module to main: code, the visible tests, and the full suite to qa/."""
    src_dir = GENERATED / meta["module"]
    repo, qa = run_dir / "repo", run_dir / "qa" / "tests"
    module, test_file = meta["module"], meta["test_file"]
    shutil.copy(src_dir / f"{module}.py", repo / f"{module}.py")
    full = (src_dir / test_file).read_text()
    (qa / test_file).write_text(full)
    (repo / "tests" / test_file).write_text(drop_functions(full, set(meta["hidden_tests"])))
    git(repo, "add", f"{module}.py", f"tests/{test_file}")
    git(repo, "commit", "-q", "--author", "platform-team <platform@tidewater.example>", "-m", message)
    return {"key": module, "kind": "standard", "function": meta["function"], "test_file": test_file,
            "hidden_tests": meta["hidden_tests"], "original_buggy": None, "original_ticket": None,
            "title": meta["summary"], "contradicting_tests": [], "generated": True}


def _single(test_file: Path, scratch: Path) -> Path:
    tests = scratch / "tests"
    tests.mkdir(exist_ok=True)
    shutil.copy(test_file, tests / test_file.name)
    return tests


def visible_tests(repo: Path) -> TestRun:
    return run_pytest(repo)


def qa_run(code_dir: Path, qa_dir: Path, test_file: str | None = None) -> TestRun:
    """The full QA suite (one module's file, or all) against code_dir's modules."""
    if test_file is None:
        return run_pytest(code_dir, tests=qa_dir)
    with _one(qa_dir, test_file) as tests:
        return run_pytest(code_dir, tests=tests)


class _one:
    def __init__(self, qa_dir: Path, name: str) -> None:
        self.qa_dir, self.name = qa_dir, name

    def __enter__(self) -> Path:
        import tempfile  # noqa: PLC0415
        self.tmp = tempfile.TemporaryDirectory()
        tests = Path(self.tmp.name) / "tests"
        tests.mkdir()
        shutil.copy(self.qa_dir / self.name, tests / self.name)
        return tests

    def __exit__(self, *exc) -> None:
        self.tmp.cleanup()


def failing_qa_tests(code_dir: Path, qa_dir: Path, test_file: str) -> set[str]:
    with _one(qa_dir, test_file) as tests:
        return _failing(code_dir, tests)


class Repo:
    """main lives in repo/; each PR branch gets a worktree under wt/."""

    def __init__(self, run_dir: Path) -> None:
        run_dir = run_dir.resolve()
        self.main = run_dir / "repo"
        self.qa = run_dir / "qa" / "tests"
        self.worktrees = run_dir / "wt"
        self.worktrees.mkdir(exist_ok=True)

    def head(self) -> str:
        return git(self.main, "rev-parse", "HEAD").strip()

    def inject(self, module: str, new_source: str, message: str) -> str:
        """A change lands on main from outside the team (the bug a ticket will report)."""
        (self.main / f"{module}.py").write_text(new_source)
        git(self.main, "add", f"{module}.py")
        git(self.main, "commit", "-q", "--author", "platform-sync <platform@tidewater.example>", "-m", message)
        return self.head()

    def branch(self, name: str) -> tuple[Path, str]:
        path = self.worktrees / name
        if path.exists():
            return path, git(path, "merge-base", "HEAD", "main").strip()
        git(self.main, "worktree", "add", "-q", "-b", name, str(path), "main")
        return path, self.head()

    def commit(self, path: Path, author: str, message: str) -> bool:
        git(path, "add", "-A")
        if not git(path, "status", "--porcelain").strip():
            return False
        git(path, "-c", f"user.name={author}", "-c", f"user.email={author}@bots.tidewater.example",
            "commit", "-q", "-m", message)
        return True

    def diff(self, path: Path, base: str) -> str:
        return git(path, "diff", base, "--", ".", ":(exclude)*.pyc")

    def changed_files(self, path: Path, base: str) -> list[str]:
        return [p for p in git(path, "diff", "--name-only", base).splitlines() if p]

    def file_at(self, rev: str, rel: str) -> str:
        return git(self.main, "show", f"{rev}:{rel}", check=False)

    def merge(self, branch: str) -> tuple[bool, str]:
        """Merge an approved branch into main; a conflict aborts and is reported."""
        out = subprocess.run(["git", "merge", "--no-ff", "--no-edit", branch], cwd=self.main,
                             capture_output=True, text=True)
        if out.returncode != 0:
            git(self.main, "merge", "--abort", check=False)
            return False, (out.stdout + out.stderr).strip()[-500:]
        return True, self.head()

    def update_branch(self, path: Path) -> tuple[bool, str]:
        """Bring main into a branch before a revision; a conflict aborts."""
        out = subprocess.run(["git", "merge", "--no-edit", "main"], cwd=path, capture_output=True, text=True)
        if out.returncode != 0:
            git(path, "merge", "--abort", check=False)
            return False, (out.stdout + out.stderr).strip()[-500:]
        return True, ""
