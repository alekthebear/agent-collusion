"""Manifest loading, episode task-group resolution, and task-path resolution."""

import json
import re
from pathlib import Path
from typing import Any

# Code tasks use Python resources directly.

# Display IDs expose only category and index, hiding descriptive task and twin slugs.
# Internal manifest IDs remain available for evaluation and output traceability.
TASK_TYPE_DISPLAY_CATEGORIES = {
    "code_analysis": 1,
    "record_extraction": 2,
    "data_search": 3,
}
_TASK_ID_INDEX = re.compile(r"^[A-Za-z]+_(\d+)_")

# Task resources are written relative to the repository root, both in the pool
# manifests below and in the resource paths they hold.
TASK_ROOT = "task"
DEFAULT_TASK_SEQUENCES = f"{TASK_ROOT}/task_sequences_50x10"
# The same sequences with tasks added for larger groups, keyed by group size.
GROUP_TASK_SEQUENCES = {3: f"{TASK_ROOT}/task_sequences_ring3_50x10"}


def default_task_sequences(group_size: int) -> str:
    """The stored sequences for a group of this size."""
    if group_size == 2:
        return DEFAULT_TASK_SEQUENCES
    try:
        return GROUP_TASK_SEQUENCES[group_size]
    except KeyError:
        raise ValueError(
            f"No stored task sequences for groups of {group_size}; build them with "
            "python -m experiments.extend_sequences"
        ) from None
DEFAULT_TASK_MANIFESTS = (
    f"{TASK_ROOT}/code-analysis/task_manifest_code50.json",
    f"{TASK_ROOT}/text-extraction/task_manifest_text50.json",
    f"{TASK_ROOT}/data-search/task_manifest_data_search50.json",
)


def read_manifest(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_task_pool(repo_root: Path) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    missing: list[Path] = []
    for manifest_path in (repo_root / name for name in DEFAULT_TASK_MANIFESTS):
        if not manifest_path.exists():
            missing.append(manifest_path)
            continue
        tasks.extend(read_manifest(manifest_path))
    if missing:
        missing_text = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Missing default task manifest(s): {missing_text}")
    return tasks


def _task_pool_by_id(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Index all pool manifests by task_id, rejecting duplicate identifiers."""
    pool: dict[str, dict[str, Any]] = {}
    for task in _read_task_pool(repo_root):
        task_id = str(task.get("task_id", ""))
        if not task_id:
            raise ValueError(f"Task pool entry without a task_id: {task}")
        if task_id in pool:
            raise ValueError(f"Task id appears twice in the task pool: {task_id}")
        pool[task_id] = task
    return pool


def _copy_task(task: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(task, ensure_ascii=False))


def task_spec_key(task: dict[str, Any]) -> str:
    """Return the shared spec_key for code-task twins, or an empty key otherwise."""
    return str(task.get("spec_key", ""))


def _pairing_error(first: dict[str, Any], second: dict[str, Any]) -> str | None:
    """Return the reason a task pair is invalid, or None.

    Pairs require the same task type, different instances, and different code spec_keys.
    Code twins would let an agent infer its peer's answer from its own task.
    """
    if task_type_of(first) != task_type_of(second):
        return (
            f"task types differ: {task_type_of(first)} vs {task_type_of(second)}"
        )
    if str(first.get("task_id")) == str(second.get("task_id")):
        return f"both agents were dealt the same task: {first.get('task_id')}"
    if is_code_task_type(task_type_of(first)):
        if task_spec_key(first) and task_spec_key(first) == task_spec_key(second):
            return (
                "the two tasks are clean/buggy twins sharing spec_key "
                f"{task_spec_key(first)!r}, so either agent could read the other's "
                "ground truth off its own"
            )
    return None


def validate_task_group(tasks: tuple[dict[str, Any], ...]) -> None:
    """Validate an episode's tasks, every pair of them under the pairing rules."""
    for index, first in enumerate(tasks):
        for second in tasks[index + 1 :]:
            error = _pairing_error(first, second)
            if error is not None:
                raise ValueError(
                    f"Invalid task pair ({first.get('task_id')}, "
                    f"{second.get('task_id')}): {error}"
                )


def read_task_groups(
    manifest_path: Path,
    repo_root: Path,
    group_size: int = 2,
) -> list[tuple[dict[str, Any], ...]]:
    """Resolve a stored episode sequence against the pool manifests.

    A sequence lists its episodes under "pairs" or, for larger groups, "groups".
    Preserve episode order, validate every episode, and reject repeated tasks.
    """
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = sequence_entries(document) if isinstance(document, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError(
            f"{manifest_path} is not a task sequence: expected an object with a "
            'non-empty "pairs" or "groups" list of {"tasks": [id, ...]} entries.'
        )
    pool = _task_pool_by_id(repo_root)
    groups: list[tuple[dict[str, Any], ...]] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        where = f"{manifest_path} episode {index}"
        task_ids = entry.get("tasks") if isinstance(entry, dict) else None
        if not isinstance(task_ids, list) or len(task_ids) != group_size:
            raise ValueError(f'{where}: expected "tasks" with {group_size} ids')
        unknown = sorted(set(entry) - {"tasks"})
        if unknown:
            # Sequence entries identify tasks; task metadata and run settings come from elsewhere.
            raise ValueError(f"{where}: unknown key(s) {', '.join(unknown)}")
        tasks: list[dict[str, Any]] = []
        for task_id in map(str, task_ids):
            if task_id not in pool:
                raise ValueError(
                    f"{where}: no task {task_id!r} in the pool under "
                    f"{repo_root / TASK_ROOT}"
                )
            if task_id in seen:
                raise ValueError(
                    f"{manifest_path}: task {task_id!r} is in more than one episode"
                )
            seen.add(task_id)
            tasks.append(_copy_task(pool[task_id]))
        validate_task_group(tuple(tasks))
        groups.append(tuple(tasks))
    return groups


def sequence_entries(document: dict[str, Any]) -> Any:
    """A sequence's episode entries, whichever key the sequence uses."""
    return document.get("groups", document.get("pairs"))


def sanitize_label(label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", label.strip())
    return cleaned.strip("_")


def task_type_of(task: dict[str, Any]) -> str:
    return str(task.get("task_type", "code_analysis"))


def is_code_task_type(task_type: str) -> bool:
    return task_type == "code_analysis"


def display_task_id(task: dict[str, Any]) -> str:
    """Derive the agent-visible ID as "<category digit>-<two-digit index>"."""
    task_type = task_type_of(task)
    category = TASK_TYPE_DISPLAY_CATEGORIES.get(task_type)
    if category is None:
        raise ValueError(f"No display category for task_type: {task_type}")
    task_id = str(task.get("task_id", ""))
    match = _TASK_ID_INDEX.match(task_id)
    if not match:
        raise ValueError(
            f"Cannot derive a display id from task_id {task_id!r}: expected a "
            "leading '<prefix>_<number>_' segment"
        )
    return f"{category}-{int(match.group(1)):02d}"


def task_file_path(task: dict[str, Any], key: str, repo_root: Path) -> Path:
    """Resolve a task resource to an absolute path."""
    path = Path(task[key])
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()
