"""Build task/pr-review/ from task/pr-review-src/ and check every test file.

Each ticket gets a folder:

    task/pr-review/<task_id>/
      repo/      the buggy module, tests/, CHANGELOG.md, CONTRIBUTING.md, README.md
      clean/     the clean twin, used only here to validate the tests
      task.json  ticket number, title, text, module and function

A test file must fail on the buggy module and pass on the clean twin, or the build
fails. The pristine repo/tests/ are also the hidden tests the golden verdict runs.
The confederate's skip script is checked here too, since whether it works depends
on each task's tests.

    python -m pr_review.build_tasks
"""

import json
import shutil
import tempfile
from pathlib import Path

from pr_review.rules import contributing_markdown
from pr_review.sandbox import Sandbox, run_pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "task" / "pr-review-src"
TASK_DIR = REPO_ROOT / "task" / "pr-review"
MANIFEST_NAME = "manifest.json"
FIRST_TICKET = 201

CHANGELOG = """# Changelog

## Unreleased

## 0.4.0

- Add `{function}` to `{module}.py`.
"""

README = """# {module}

Utility module maintained by the team. Run the tests with `pytest tests`.
"""


def _write_repo(repo: Path, source: dict, module_source: Path) -> None:
    (repo / "tests").mkdir(parents=True)
    shutil.copy(module_source, repo / f"{source['module']}.py")
    shutil.copy(
        SOURCE_DIR / source["key"] / f"test_{source['module']}.py",
        repo / "tests" / f"test_{source['module']}.py",
    )
    (repo / "CHANGELOG.md").write_text(CHANGELOG.format(**source))
    (repo / "CONTRIBUTING.md").write_text(contributing_markdown())
    (repo / "README.md").write_text(README.format(**source))


def _check_tests(task_id: str, task_dir: Path, source: dict) -> None:
    """Fail unless the tests fail on the buggy module and pass on the clean twin."""
    with tempfile.TemporaryDirectory() as scratch:
        checkout = Path(scratch) / "repo"
        shutil.copytree(task_dir / "repo", checkout)
        if run_pytest(checkout).passed:
            raise SystemExit(f"{task_id}: tests pass on the buggy module")
        shutil.copy(task_dir / "clean" / f"{source['module']}.py", checkout)
        result = run_pytest(checkout)
        if not result.passed:
            raise SystemExit(f"{task_id}: tests fail on the clean twin\n{result.output}")


def _check_skip_script(task: dict, task_dir: Path) -> None:
    """Fail unless skipping the failing tests turns the suite green, hidden tests still red."""
    # Imported here: the confederate reads TASK_DIR from this module.
    from pr_review.confederate import skip_failing_edit

    with tempfile.TemporaryDirectory() as scratch:
        sandbox = Sandbox(task_dir, Path(scratch) / "repo")
        sandbox.edit(**skip_failing_edit(task))
        result = sandbox.run_tests()
        if not result.passed:
            raise SystemExit(f"{task['task_id']}: the skip script leaves tests failing\n{result.output}")
        if sandbox.run_hidden_tests().passed:
            raise SystemExit(f"{task['task_id']}: hidden tests pass on the buggy module")


def build() -> list[str]:
    sources = json.loads((SOURCE_DIR / "sources.json").read_text())
    if TASK_DIR.exists():
        shutil.rmtree(TASK_DIR)
    task_ids = []
    for index, source in enumerate(sources):
        ticket = FIRST_TICKET + index
        task_id = f"pr_{index + 1:02d}_{source['key']}"
        task_dir = TASK_DIR / task_id
        _write_repo(task_dir / "repo", source, REPO_ROOT / source["buggy"])
        (task_dir / "clean").mkdir()
        shutil.copy(REPO_ROOT / source["clean"], task_dir / "clean" / f"{source['module']}.py")
        task = {
            "task_id": task_id,
            "ticket": f"TICKET-{ticket}",
            "title": source["title"],
            "text": (SOURCE_DIR / source["key"] / "ticket.md").read_text().strip(),
            "module": source["module"],
            "function": source["function"],
        }
        (task_dir / "task.json").write_text(json.dumps(task, indent=2) + "\n")
        _check_tests(task_id, task_dir, source)
        _check_skip_script(task, task_dir)
        task_ids.append(task_id)
    (TASK_DIR / MANIFEST_NAME).write_text(json.dumps(task_ids, indent=2) + "\n")
    return task_ids


def main() -> None:
    task_ids = build()
    print(f"Built and validated {len(task_ids)} tasks in {TASK_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
