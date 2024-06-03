#!/usr/bin/env python3
import re
from argparse import ArgumentParser, Namespace
from collections import namedtuple
from datetime import date
from types import SimpleNamespace

import pandas as pd

from helpers.generic import git_log_actions, load_config

GitCommitStats = namedtuple("GitCommitStats", "date year week author insertions deletions")


def main(args: Namespace, config: SimpleNamespace):
    ## Use settings and arguments
    first = config.today.replace(month=1, day=1)
    last = config.today
    ignore_pattern = re.compile(config.ignore_file_pattern)

    ## Read and merge all GIT logs
    data = list()
    files = set()

    for repo in config.repositories:
        print(f"{repo=}")
        history, commit_actions = git_log_actions(
            repo, start=first, end=last, skip_files=ignore_pattern
        )
        for commit in history:
            insertions, deletions = 0, 0
            for a in commit_actions[commit.hash]:
                files.add(a.path)
                print(a)
                insertions += int(a.insertions)
                deletions += int(a.deletions)
            a_date = date.fromisoformat(commit.date)
            data.append(
                GitCommitStats(a_date, a_date.year, a_date.isocalendar().week, commit.author, insertions, deletions)
            )

    df = pd.DataFrame(data)
    with pd.ExcelWriter("action_report.xlsx", engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)
    print("Wrote", len(data), "rows to action_report.xlsx")
    print(*sorted(files), sep="\n")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--today", type=date.fromisoformat, help="The target day in YYYY-MM-DD format"
    )

    args = parser.parse_args()

    config = load_config("project.toml")
    config.today = args.today if args.today else date.today()

    main(args, config)
