"""Run one PR-review experiment, then write its static viewer page.

    python -m pr_review [--structure ring3] [--confederate bob --ask trade] [--episodes N] ...
    python -m pr_review --from results/pr-review/<id>/<run> [--seed S] ...

Every Config field is a flag, listed below. --from starts from a past run's settings.
Without --id, the results folder is named after the settings that differ from the
defaults.
"""

import argparse
from pathlib import Path

from dotenv import load_dotenv

from pr_review.config import add_config_arguments, config_from_args
from pr_review.run import RESULTS_DIR, run
from viewer.pr_review.export import export_run


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    add_config_arguments(parser)
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()
    config = config_from_args(args)
    load_dotenv()
    print(f"Running {config.id}")
    run_dir = run(config, args.results_dir)
    print(f"Wrote {run_dir / 'run.json'}")
    print(f"Wrote {export_run(run_dir)}")


if __name__ == "__main__":
    main()
