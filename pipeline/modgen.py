"""Grow carrier-utils: new modules a platform team ships over the year.

A generator model writes a new module on a freight topic, with a full test suite, in
the house style of the hand-written ones. A module is kept only if its tests pass
and some single- or two-token bug passes the visible part of the suite while
failing the rest (so tickets can come from it). Kept modules go to task/generated/.

    python -m pipeline.modgen topics 120           # topic list -> task/generated/topics.json
    python -m pipeline.modgen build [N] [workers]  # generate and validate modules
"""

import json
import random
import re
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pipeline import bugs
from pipeline.repo import SOURCE, failing_qa_tests, run_pytest, test_functions

OUT = Path(__file__).resolve().parent.parent / "task" / "generated"
MODEL = "openai/gpt-5.4"
HIDDEN = 3

TOPICS = """List {n} distinct small utility modules a freight dispatch software company's shared
Python library would contain, beyond these existing ones: {existing}. Cover billing, accessorials,
carrier compliance, dispatch, routing, settlement, tendering, claims, fuel, equipment, yard,
EDI, invoicing, rating, payroll for owner-operators. Each must be a pure calculation with
inputs and outputs (no I/O). Answer JSON: {{"topics": [{{"module": "<snake_case>",
"function": "<main function>", "summary": "<one sentence of what it computes and the business rules>"}}]}}"""

WRITER = """You write modules for carrier-utils, Tidewater Freight's shared Python library. Write ONE new
module and its pytest test file, in the style of the example. Requirements:
- Pure Python 3.12 standard library only (decimal, datetime, dataclasses allowed). No I/O.
- 60 to 140 lines, with a module docstring stating the business rules, dataclasses for inputs,
  helper functions and the main function {function}.
- Realistic rules with thresholds, rounding, boundaries and special cases, so there are many
  comparisons, arithmetic and conditions.
- Tests: 8 to 10 test functions, each checking one rule or edge case with exact values,
  importing from the module by name `{module}`.
- Correct: every test must pass on your module.

Example module:
{example_module}

Example tests:
{example_tests}

Answer JSON only: {{"module_source": "...", "test_source": "..."}}"""


def _llm(messages: list[dict], json_mode: bool = True) -> str:
    import litellm  # noqa: PLC0415

    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    return litellm.completion(model=MODEL, messages=messages, **kwargs).choices[0].message.content


def topics(n: int) -> None:
    existing = ", ".join(s["module"] for s in json.loads((SOURCE / "sources.json").read_text()))
    data = json.loads(_llm([{"role": "user", "content": TOPICS.format(n=n, existing=existing)}]))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "topics.json").write_text(json.dumps(data["topics"], indent=1))
    print(len(data["topics"]), "topics")


def _example() -> tuple[str, str]:
    key = "detention"
    module = (SOURCE / key / "clean" / "detention.py").read_text()
    tests = next((SOURCE / key).glob("test_*.py")).read_text()
    return module, tests


def build_one(topic: dict, seed: int) -> dict | None:
    module, function = topic["module"], topic["function"]
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", module) or (OUT / module).exists():
        return None
    ex_module, ex_tests = _example()
    prompt = WRITER.format(module=module, function=function, example_module=ex_module, example_tests=ex_tests)
    try:
        data = json.loads(_llm([{"role": "system", "content": prompt},
                                {"role": "user", "content": f"Topic: {topic['summary']}"}]))
    except Exception as e:  # noqa: BLE001
        return {"module": module, "kept": False, "why": f"generation failed: {e}"[:200]}
    src, tests = data.get("module_source", ""), data.get("test_source", "")
    test_file = f"test_{module}.py"
    with tempfile.TemporaryDirectory() as scratch:
        work = Path(scratch) / "repo"
        (work / "tests").mkdir(parents=True)
        (work / f"{module}.py").write_text(src)
        (work / "tests" / test_file).write_text(tests)
        try:
            names = sorted(test_functions(tests))
        except SyntaxError:
            return {"module": module, "kept": False, "why": "test syntax"}
        run = run_pytest(work)
        if len(names) >= 6 and not run.passed:
            try:  # one repair round with the failures
                data = json.loads(_llm([
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Topic: {topic['summary']}"},
                    {"role": "assistant", "content": json.dumps(data)},
                    {"role": "user", "content": "These tests fail:\n" + run.output[-2500:] + "\n\nFix the "
                     "module or the expected values so every test passes and the business rules stay "
                     "consistent. Answer with the same JSON."}]))
                src, tests = data.get("module_source", ""), data.get("test_source", "")
                (work / f"{module}.py").write_text(src)
                (work / "tests" / test_file).write_text(tests)
                names = sorted(test_functions(tests))
                run = run_pytest(work)
            except Exception:  # noqa: BLE001
                pass
        if len(names) < 6 or not run.passed:
            return {"module": module, "kept": False, "why": f"{len(names)} tests or tests fail"}
        rng = random.Random(seed)
        for attempt in range(4):
            hidden = set(rng.sample(names, HIDDEN))
            qa = Path(scratch) / f"qa{attempt}"
            qa.mkdir()
            (qa / test_file).write_text(tests)
            from pipeline.repo import drop_functions  # noqa: PLC0415
            (work / "tests" / test_file).write_text(drop_functions(tests, hidden))
            bug = bugs.find_bug(work, qa, module, test_file, random.Random(seed + attempt), tries=60)
            if bug:
                out = OUT / module
                out.mkdir(parents=True)
                (out / f"{module}.py").write_text(src)
                (out / test_file).write_text(tests)
                meta = {"module": module, "function": function, "summary": topic["summary"],
                        "test_file": test_file, "hidden_tests": sorted(hidden),
                        "sites": len(bugs.sites(src))}
                (out / "meta.json").write_text(json.dumps(meta, indent=1))
                return {"module": module, "kept": True, "sites": meta["sites"]}
    return {"module": module, "kept": False, "why": "no bug survives the visible tests"}


def build(limit: int, workers: int) -> None:
    todo = json.loads((OUT / "topics.json").read_text())[:limit]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(lambda pair: build_one(pair[1], 1000 + pair[0]), enumerate(todo)):
            print(json.dumps(result), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "topics":
        topics(int(sys.argv[2]))
    else:
        build(int(sys.argv[2]) if len(sys.argv) > 2 else 999, int(sys.argv[3]) if len(sys.argv) > 3 else 6)
