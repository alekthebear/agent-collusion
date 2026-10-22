"""Extend stored pair sequences into sequences for larger groups.

Each episode keeps its two tasks, in order, so the first two agents of a group get
exactly the tasks the pair got. Each added task has the episode's task type, is
unused elsewhere in that sequence, and shares no code spec_key with the episode's
other tasks. Choices are seeded per sequence file, so rebuilding gives the same
sequences.

    python -m experiments.extend_sequences \
        --source task/task_sequences_50x10 \
        --output task/task_sequences_ring3_50x10 \
        --group-size 3
"""

import argparse
import json
import random
from pathlib import Path

from experiments.tasks import (
    _task_pool_by_id,
    read_task_groups,
    sequence_entries,
    task_spec_key,
    task_type_of,
)

EXTENSION_RECORD = "extended_sequence_record.json"


def extend_sequence(
    entries: list[dict[str, list[str]]],
    pool: dict[str, dict],
    group_size: int,
    rng: random.Random,
) -> list[dict[str, list[str]]]:
    """Add tasks to every episode until each has ``group_size``."""
    used = {task_id for entry in entries for task_id in entry["tasks"]}
    extended = []
    for entry in entries:
        tasks = list(entry["tasks"])
        task_type = task_type_of(pool[tasks[0]])
        while len(tasks) < group_size:
            taken_specs = {task_spec_key(pool[t]) for t in tasks} - {""}
            candidates = sorted(
                task_id
                for task_id, task in pool.items()
                if task_id not in used
                and task_type_of(task) == task_type
                and task_spec_key(task) not in taken_specs
            )
            if not candidates:
                raise ValueError(f"No unused {task_type} task left for {tasks}")
            choice = rng.choice(candidates)
            tasks.append(choice)
            used.add(choice)
        extended.append({"tasks": tasks})
    return extended


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", required=True, help="Directory of pair sequences.")
    parser.add_argument("--output", required=True, help="Directory to write.")
    parser.add_argument("--group-size", type=int, required=True)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    repo_root = Path.cwd().resolve()
    pool = _task_pool_by_id(repo_root)
    source = Path(args.source)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    manifests = sorted(source.glob("rep*_sampled_manifest.json"))
    if not manifests:
        raise ValueError(f"No rep*_sampled_manifest.json files in {source}")
    for manifest in manifests:
        document = json.loads(manifest.read_text(encoding="utf-8"))
        rng = random.Random(f"{args.seed}:{manifest.name}")
        groups = extend_sequence(sequence_entries(document), pool, args.group_size, rng)
        path = output / manifest.name
        path.write_text(
            json.dumps({"groups": groups}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        # Validate with the same loader the runner uses.
        read_task_groups(path, repo_root, args.group_size)
    (output / EXTENSION_RECORD).write_text(
        json.dumps(
            {
                "description": (
                    "Written by experiments.extend_sequences: each source episode "
                    "keeps its tasks in order, with tasks of the same type added."
                ),
                "source": str(source),
                "group_size": args.group_size,
                "seed": args.seed,
                "reps": len(manifests),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(manifests)} sequences to {output}")


if __name__ == "__main__":
    main()
