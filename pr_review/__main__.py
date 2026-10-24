"""Run one PR-review experiment config, then write its static viewer page.

    python -m pr_review CONFIG.toml [--episodes N] [--seed S]

CONFIG.toml sets Config fields, at least `id`, which names the results folder.
"""

import argparse
from pathlib import Path

from dotenv import load_dotenv

from pr_review.config import load_config
from pr_review.run import RESULTS_DIR, run
from viewer.pr_review.export import export_run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", type=Path)
    parser.add_argument("--episodes", type=int, help="Override the config's episode count")
    parser.add_argument("--seed", type=int, help="Override the config's seed")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()
    load_dotenv()
    config = load_config(args.config, episodes=args.episodes, seed=args.seed)
    run_dir = run(config, args.results_dir)
    print(f"Wrote {run_dir / 'run.json'}")
    print(f"Wrote {export_run(run_dir)}")


if __name__ == "__main__":
    main()
