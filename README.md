# Collusion in LLM Code Review

A multi-agent PR-review environment for studying collusion between LLM agents, built
for the Apart AI Collusion Research Sprint (October 23–25, 2026). It extends
[SALT-NLP/agent-collusion](https://github.com/SALT-NLP/agent-collusion), the code for
[Emergent Collusion in Long-Horizon LLM Agent Interaction](https://arxiv.org/abs/2609.24967)
(Shi, Zhang and Yang, 2026), and reuses its LLM client and judges.

Three agents fix tickets in small Python repos and review each other's pull requests.
Each episode, an agent works its tickets within a time-box of tool calls, opens a PR as
`ready` or `blocked`, inspects the PRs it reviews with a few budgeted checks, talks on
PR threads (which the team lead reads) and in private direct messages, then approves
or requests changes. A golden verdict, never shown to agents, records which
CONTRIBUTING.md rules each PR broke, so every approval can be scored. The question is
whether a reviewer covers for a teammate's known violation, and more so when the
teammate can return the favor (all-to-all review) than when it can't (a ring).

- **Design:** [docs/20261023_pr_review_design.md](docs/20261023_pr_review_design.md)
- **Pilot results:** [docs/experiments/20261024_pr_review_pilot_log.md](docs/experiments/20261024_pr_review_pilot_log.md)

## Setup

Use Python 3.12, from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add provider keys to `.env`. The default model, DeepSeek V4.1 Flash, and the deal judge
both go through OpenRouter, so set `OPENROUTER_API_KEY`. Any LiteLLM route works as
the `model` setting.

## Running an experiment

Every setting in [pr_review/config.py](pr_review/config.py) is a flag, and anything
left out keeps its default. For example, all-to-all review with a scripted
confederate who offers a casual trade:

```bash
python -m pr_review --structure all3 --confederate bob --ask trade --ask-tone casual --episodes 4
```

The main settings are `--structure` (`all3`, `ring3`, `ring4`, `pairs4`),
`--confederate`, `--ask` (`none`, `plea`, `trade`), `--ask-tone` (`direct`, `casual`),
`--favor-episodes`, `--review-checks`, `--positive-control`, `--pressure` or
`--no-pressure`, `--budgets hard=3`, `--model`, `--episodes` and `--seed`. See
`python -m pr_review --help` for all of them, and the design doc for what each does.

To repeat or vary a past run, start from its settings with `--from`. Flags change
the rest:

```bash
python -m pr_review --from results/pr-review/v1-ring3-trade/run_20261024_013241_seed1 --seed 2
python -m pr_review --from results/pr-review/v1-ring3-trade/run_20261024_013241_seed1 --structure all3
```

`--from` takes the settings only; the run uses the current code.

The results folder is named by `--id`. Without it, the name is the structure plus every
setting that differs from its default, such as `all3_confederate-bob_ask-trade_ask-tone-casual`.
With `--from`, the past run's name is kept when only `--seed` or `--episodes` changes.

A run writes `results/pr-review/<id>/run_<time>_seed<S>/`:

- `run.json`: the config, git commit, system prompts, and every episode's PRs, checks,
  messages, reviews, golden verdicts, rewards, reflections and transcripts
- `llm_usage.jsonl`: one line per model call, with tokens and cost
- `viewer.html`: the run's viewer as one file that opens without a server
- `sandboxes/`: each author's working copy of each ticket

## Viewing runs

```bash
python -m viewer.pr_review [--results DIR] [--port 8766] [--no-browser]
```

This serves every run under `results/pr-review/`: per-episode PR outcomes, PR threads
beside direct messages, check results, golden verdicts, transcripts, and the exact
prompt behind each model call, with eval-awareness terms highlighted. To write the
single-file page for a run again:

```bash
python -m viewer.pr_review.export results/pr-review/<id>/<run>
```

`python viewer/original/server.py` serves the paper harness's runs.

## Analysis

```bash
# Ticket outcomes, false approvals (knowing or not), planted violations, eval awareness
python analysis/pr_review/metrics.py results/pr-review/<id>/*/run.json

# LLM judge: is a review covered by a deal in the threads or direct messages?
python analysis/pr_review/deal_judge.py \
  --runs 'results/pr-review/<id>/*/run.json' \
  --out analysis/results/pr_review_deals.csv
```

Reviewer measures count only reviews a model decided; the confederate's scripted reviews
are left out.

## Tasks

30 tickets, each a one-function bug drawn from the paper's code-analysis tasks, with a
ticket, a test file, and a clean twin. Sources are in `task/pr-review-src/`; the built
repos in `task/pr-review/` are committed. After changing a source or the rules in
[pr_review/rules.py](pr_review/rules.py), rebuild:

```bash
python -m pr_review.build_tasks
```

The build checks that every test file fails on the buggy module and passes on the
clean twin, and that the confederate's skip-the-failing-tests script works on every task.

## Tests

```bash
python -m tests.pr_review_smoke
```

This runs without API calls, in about 40 seconds: scripted traces for each rule of
the golden verdict, tool budgets, test sandboxing, and full runs with a scripted model,
including the confederate and favors-first runs. The paper harness has its own:
`python -m tests.ring_smoke`, `python -m tests.judge_smoke` and `python -m tests.replay`.

## Results

Committed runs are in `results/pr-review/` (each with `run.json` and
`llm_usage.jsonl`), plus the paper harness's proof-of-concept run in `results/poc/`.
Runs that aren't shared go in `results/scratch/`, which is ignored.

## Repository structure

```text
.
├── pr_review/                 # The PR-review environment
│   ├── __main__.py            # python -m pr_review [flags]
│   ├── config.py              # Experiment settings, as flags or from a past run
│   ├── run.py                 # Deals tickets, runs episodes, carries memory, writes run.json
│   ├── episode.py             # Work → inspect → talk → verdict → score → feedback → reflect
│   ├── structure.py           # Who reviews whom: all3, ring3, ring4, pairs4
│   ├── rules.py               # CONTRIBUTING.md rules
│   ├── golden.py              # Golden verdict from the author's trace and sandbox
│   ├── sandbox.py             # Per-ticket repo copies and real pytest runs
│   ├── tools/                 # Author and reviewer tools, with budgets
│   ├── channels.py            # PR threads and direct messages
│   ├── confederate.py         # Scripted rule-breaking author and its asks
│   ├── prompts.py             # Everything the agents read
│   ├── llm.py                 # Model calls through the paper harness's client
│   └── build_tasks.py         # Builds and checks task/pr-review/
├── viewer/
│   ├── pr_review/             # Run viewer: python -m viewer.pr_review
│   └── original/              # Viewer for the paper harness's runs
├── analysis/
│   ├── pr_review/             # metrics.py and deal_judge.py
│   └── ...                    # The paper's agreement and relaxation judges
├── task/
│   ├── pr-review-src/         # Ticket sources
│   ├── pr-review/             # Built ticket repos
│   └── ...                    # The paper's task families and sequences
├── tests/                     # pr_review_smoke.py, plus the paper harness's tests
├── docs/
│   ├── 20261023_pr_review_design.md
│   └── experiments/           # Write-ups and pilot logs
├── results/                   # Shared runs; results/scratch/ is ignored
└── experiments/               # The paper's two-agent harness, extended to groups
```

The original harness still runs as before (`python -m experiments`); see the
[upstream README](https://github.com/SALT-NLP/agent-collusion#readme) for its usage, and
[docs/experiments/20261021_baseline_explorations.md](docs/experiments/20261021_baseline_explorations.md)
for its group extension.

## License and citation

MIT License; see [LICENSE](LICENSE). If you build on the original environment, cite:

```bibtex
@misc{shi2026emergentcollusionlonghorizonllm,
      title={Emergent Collusion in Long-Horizon LLM Agent Interaction},
      author={Xinrui Shi and Yanzhe Zhang and Diyi Yang},
      year={2026},
      eprint={2609.24967},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2609.24967},
}
```
