"""A per-ticket copy of a task repo: files the author edits, and real pytest runs."""

import difflib
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Keep provider credentials out of the test process; keep PATH for the toolchain.
_INHERITED_ENV_VARS = ("PATH", "TMPDIR", "LANG", "LC_ALL")
# One test run's wall-clock bound.
_PROCESS_TIMEOUT = 30
# Test output shown to agents, from the end, where pytest puts the summary.
_OUTPUT_CHARS = 3000
# Paths that must never reach an agent: they name the project.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_ROOT = Path(sys.prefix).resolve()


class SandboxError(ValueError):
    """A file operation the sandbox refuses, reported back to the agent."""


@dataclass(frozen=True)
class TestRun:
    passed: bool
    output: str

    @property
    def summary(self) -> str:
        """pytest's last line, such as "1 failed, 2 passed in 0.02s"."""
        lines = [line for line in self.output.strip().splitlines() if line.strip()]
        return lines[-1].strip("= ") if lines else ""


def _scrub(output: str, repo: Path) -> str:
    """Show the repo as "." and hide where the project and its environment live."""
    output = output.replace(str(repo) + os.sep, "").replace(str(repo), ".")
    output = output.replace(str(_ENV_ROOT), "/opt/python")
    return output.replace(str(_PROJECT_ROOT), "/workspace")


def run_pytest(repo: Path, tests: Path | None = None) -> TestRun:
    """Run pytest on repo's tests/, or on ``tests`` against repo's code."""
    repo = repo.resolve()
    with tempfile.TemporaryDirectory() as home:
        env = {name: os.environ[name] for name in _INHERITED_ENV_VARS if name in os.environ}
        env.update(HOME=home, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(repo))
        command = [
            sys.executable,
            "-m",
            "pytest",
            str(tests or repo / "tests"),
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
            "--rootdir",
            str(repo),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=repo,
                env=env,
                text=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=_PROCESS_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return TestRun(False, f"Test run timed out after {_PROCESS_TIMEOUT}s")
    return TestRun(completed.returncode == 0, _scrub(completed.stdout, repo)[-_OUTPUT_CHARS:])


class Sandbox:
    """One author's working copy of one ticket's repo."""

    def __init__(self, task_dir: Path, root: Path) -> None:
        self.pristine = task_dir / "repo"
        shutil.copytree(self.pristine, root)
        self.root = root.resolve()

    def _resolve(self, path: str) -> Path:
        resolved = (self.root / path).resolve()
        if not resolved.is_relative_to(self.root):
            raise SandboxError(f"{path} is outside the repository")
        return resolved

    def list_files(self) -> list[str]:
        return sorted(
            str(path.relative_to(self.root))
            for path in self.root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        )

    def read(self, path: str) -> str:
        resolved = self._resolve(path)
        if not resolved.is_file():
            raise SandboxError(f"No such file: {path}")
        return resolved.read_text()

    def edit(self, path: str, old_text: str, new_text: str) -> None:
        """Replace the one occurrence of old_text in path with new_text."""
        content = self.read(path)
        if not old_text:
            raise SandboxError("old_text must not be empty")
        count = content.count(old_text)
        if count != 1:
            raise SandboxError(
                f"old_text appears {count} times in {path}; it must appear exactly once"
            )
        self._resolve(path).write_text(content.replace(old_text, new_text, 1))

    def changed_files(self) -> list[str]:
        return [path for path in self.list_files() if self._differs(path)]

    def _differs(self, path: str) -> bool:
        original = self.pristine / path
        return not original.is_file() or original.read_text() != self.read(path)

    def original(self, path: str) -> str:
        original = self.pristine / path
        return original.read_text() if original.is_file() else ""

    def diff(self) -> str:
        """Unified diff of every changed file against the original repo."""
        chunks = []
        for path in self.changed_files():
            chunks += difflib.unified_diff(
                self.original(path).splitlines(keepends=True),
                self.read(path).splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        return "".join(chunks)

    def run_tests(self) -> TestRun:
        """Run the repo's tests/ as they are now, including any edits."""
        return run_pytest(self.root)

    def run_hidden_tests(self) -> TestRun:
        """Run the original tests against the current code, ignoring test edits."""
        with tempfile.TemporaryDirectory() as scratch:
            hidden = Path(scratch) / "tests"
            shutil.copytree(self.pristine / "tests", hidden)
            return run_pytest(self.root, tests=hidden)
