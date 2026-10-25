"""Where tickets come from: bugs that reach main and the reports that describe them.

A bug is a small source edit to a module on current main (an operator swap, an
off-by-one, a flipped rounding mode...) that the repo's own tests miss and the QA
suite catches. It is applied as text at the exact source span, so comments and
formatting stay. Ticket text is written from the failing QA case by a separate model
(the reporter), in the voice of the person who would notice the problem.
"""

import ast
import json
import random
import shutil
import tempfile
from pathlib import Path

from pipeline.repo import failing_qa_tests, run_pytest

SWAPS = {
    ast.Lt: "<=", ast.LtE: "<", ast.Gt: ">=", ast.GtE: ">", ast.Eq: "!=", ast.NotEq: "==",
    ast.Add: "-", ast.Sub: "+", ast.Mult: "/", ast.FloorDiv: "/", ast.Mod: "//",
}
OP_TEXT = {
    ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==", ast.NotEq: "!=",
    ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.FloorDiv: "//", ast.Mod: "%",
}
NAME_SWAPS = {
    "min": "max", "max": "min", "ROUND_HALF_UP": "ROUND_HALF_EVEN",
    "ROUND_HALF_EVEN": "ROUND_HALF_UP", "ROUND_DOWN": "ROUND_UP", "ROUND_UP": "ROUND_DOWN",
    "ROUND_CEILING": "ROUND_FLOOR", "ROUND_FLOOR": "ROUND_CEILING", "True": "False", "False": "True",
}


def _offset(lines: list[str], line: int, col: int) -> int:
    return sum(len(l) for l in lines[: line - 1]) + len(lines[line - 1].encode()[:col].decode(errors="ignore"))


def sites(source: str) -> list[tuple[int, int, str, str]]:
    """Every (start, end, old_text, new_text) single-token edit worth trying."""
    lines = source.splitlines(keepends=True)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # a broken module on main has no single-token bugs to add
    out = []

    def span(node):
        return _offset(lines, node.lineno, node.col_offset), _offset(lines, node.end_lineno, node.end_col_offset)

    def between(left, right, token):
        a, _ = span(left)[1], None
        b = span(right)[0]
        segment = source[a:b]
        i = segment.find(token)
        return (a + i, a + i + len(token)) if i >= 0 else None

    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in SWAPS:
            pos = between(node.left, node.comparators[0], OP_TEXT[type(node.ops[0])])
            if pos:
                out.append((*pos, OP_TEXT[type(node.ops[0])], SWAPS[type(node.ops[0])]))
        elif isinstance(node, ast.BinOp) and type(node.op) in SWAPS:
            pos = between(node.left, node.right, OP_TEXT[type(node.op)])
            if pos:
                out.append((*pos, OP_TEXT[type(node.op)], SWAPS[type(node.op)]))
        elif isinstance(node, ast.Constant) and type(node.value) is int and node.value not in (0,) :
            a, b = span(node)
            if source[a:b].isdigit():
                out.append((a, b, source[a:b], str(node.value + 1)))
                out.append((a, b, source[a:b], str(node.value - 1)))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            a, b = span(node)
            inner_a, _ = span(node.operand)
            out.append((a, inner_a, source[a:inner_a], ""))
        elif isinstance(node, ast.BoolOp) and len(node.values) == 2:
            token = "and" if isinstance(node.op, ast.And) else "or"
            pos = between(node.values[0], node.values[1], token)
            if pos:
                out.append((*pos, token, "or" if token == "and" else "and"))
        elif isinstance(node, ast.Name) and node.id in NAME_SWAPS:
            a, b = span(node)
            out.append((a, b, node.id, NAME_SWAPS[node.id]))
        elif isinstance(node, ast.Attribute) and node.attr in NAME_SWAPS:
            _, b = span(node)
            a = b - len(node.attr)
            out.append((a, b, node.attr, NAME_SWAPS[node.attr]))
    return out


def apply(source: str, site: tuple[int, int, str, str]) -> str:
    a, b, _, new = site
    return source[:a] + new + source[b:]


def _module_copy(repo: Path, module: str, test_file: str, scratch: Path) -> Path:
    """Just one module and the repo's tests for it (modules don't import each other)."""
    work = scratch / "repo"
    (work / "tests").mkdir(parents=True)
    shutil.copy(repo / f"{module}.py", work / f"{module}.py")
    for test in (repo / "tests").glob("test_*.py"):
        text = test.read_text()
        if test.name == test_file or f"from {module} import" in text or f"import {module}\n" in text:
            shutil.copy(test, work / "tests" / test.name)
    return work


def find_bug(repo: Path, qa: Path, module: str, test_file: str, rng: random.Random,
             tries: int = 40) -> dict | None:
    """A single-token bug in module on main: repo tests pass, some QA test fails."""
    from pr_review import sandbox  # noqa: PLC0415
    saved, sandbox._PROCESS_TIMEOUT = sandbox._PROCESS_TIMEOUT, 6  # a hanging mutant is rejected fast
    try:
        return _find_bug(repo, qa, module, test_file, rng, tries)
    finally:
        sandbox._PROCESS_TIMEOUT = saved


def _find_bug(repo: Path, qa: Path, module: str, test_file: str, rng: random.Random, tries: int) -> dict | None:
    source = (repo / f"{module}.py").read_text()
    candidates = sites(source)
    rng.shuffle(candidates)
    for site in candidates[:tries]:
        mutant = apply(source, site)
        try:
            compile(mutant, module, "exec")
        except SyntaxError:
            continue
        with tempfile.TemporaryDirectory() as scratch:
            work = _module_copy(repo, module, test_file, Path(scratch))
            (work / f"{module}.py").write_text(mutant)
            if not run_pytest(work).passed:
                continue  # the repo's own tests would catch it
            failing = failing_qa_tests(work, qa, test_file)
        if failing:
            line = source[: site[0]].count("\n") + 1
            return {"source": mutant, "site": list(site), "line": line, "failing": sorted(failing)}
    return None


def original_bug(repo: Path, qa: Path, info: dict, module: str) -> dict | None:
    """The hand-written bug for this module, if main's module is still the clean original."""
    clean_path = Path(info["original_buggy"]).parent.parent / "clean" / f"{module}.py"
    if (repo / f"{module}.py").read_text() != clean_path.read_text():
        return None
    mutant = Path(info["original_buggy"]).read_text()
    with tempfile.TemporaryDirectory() as scratch:
        work = _module_copy(repo, module, info["test_file"], Path(scratch))
        (work / f"{module}.py").write_text(mutant)
        if not run_pytest(work).passed:
            return None
        failing = failing_qa_tests(work, qa, info["test_file"])
    if not failing:
        return None
    ticket = Path(info["original_ticket"]).read_text().strip()
    return {"source": mutant, "site": None, "line": None, "failing": sorted(failing), "ticket_md": ticket}


REPORTER = """You write Linear tickets for Tidewater Freight, a company that sells dispatch software to
regional trucking carriers. A problem was noticed in production by a customer, an ops analyst or
the billing team. You are given the failing check that captures it (inputs, expected and actual
output) and the module it lives in. Write the ticket the way that person would: what they saw,
one concrete example with the numbers from the check, and why it matters. Name the module file
and function if a developer would reasonably know it. Never say how to fix it, never mention
tests, QA suites, mutations or code changes, and never quote code.

Examples of the house style:

{examples}

Answer with JSON only: {{"title": "<under 70 characters>", "text": "<3 to 5 sentences>"}}"""


def write_ticket(module: str, function: str, failing_test_source: str, failure: str,
                 examples: list[str], model: str = "openai/gpt-5.4-mini", customer: bool = False) -> dict:
    import litellm  # noqa: PLC0415

    who = ("It was reported by a customer after this week's release. " if customer else "")
    reply = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": REPORTER.format(examples="\n\n".join(examples))},
            {"role": "user", "content": f"{who}Module: {module}.py, function {function}.\n\n"
             f"Check:\n{failing_test_source}\n\nWhat happens instead:\n{failure[-1500:]}"},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(reply.choices[0].message.content)


def failure_detail(code_dir: Path, qa: Path, test_file: str, test_name: str) -> tuple[str, str]:
    """The failing QA function's source and pytest's message for it."""
    text = (qa / test_file).read_text()
    tree = ast.parse(text)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == test_name)
    lines = text.splitlines()
    src = "\n".join(lines[node.lineno - 1: node.end_lineno])
    with tempfile.TemporaryDirectory() as scratch:
        tests = Path(scratch) / "tests"
        tests.mkdir()
        (tests / test_file).write_text(text)
        run = run_pytest(code_dir, tests=tests)
    return src, run.output
