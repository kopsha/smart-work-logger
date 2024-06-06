#!/usr/bin/env python3
import re
from argparse import ArgumentParser, Namespace
from collections import defaultdict, namedtuple
from functools import reduce
from datetime import date, timedelta
from statistics import mean
from types import SimpleNamespace

from helpers.generic import git_log_actions, load_config, reverse_workdays

AuthorCommitStats = namedtuple(
    "AuthorCommitStats", "date author insertions deletions tickets"
)
Stats = namedtuple("Stats", "insertions deletions tickets")


def default_stats():
    return Stats(0, 0, set())


def main(args: Namespace, config: SimpleNamespace):
    ## Use settings and arguments
    last = config.today
    first = last - timedelta(days=28 * 2)
    ignore_pattern = re.compile(config.ignore_file_pattern)
    ticket_pattern = re.compile(config.ticket_pattern)
    skip = set()

    ## Merge and index all GIT commits by date
    commits_index = defaultdict(list)
    seen_files = set()
    seen_authors = set()
    for repo in config.repositories:
        history, commit_actions = git_log_actions(
            repo, start=first, end=last, skip_files=ignore_pattern
        )
        for commit in history:
            seen_authors.add(commit.author.title())

            insertions, deletions = 0, 0
            for action in commit_actions[commit.hash]:
                seen_files.add(action.path)
                insertions += int(action.insertions)
                deletions += int(action.deletions)
            a_date = date.fromisoformat(commit.date)

            tickets = set(ticket_pattern.findall(commit.message))

            commits_index[commit.date].append(
                AuthorCommitStats(
                    a_date,
                    commit.author.title(),
                    insertions,
                    deletions,
                    tickets
                )
            )

    ## Build weekly stats
    author_weekly = {author: defaultdict(default_stats) for author in seen_authors}
    weeks = set()
    for day in reverse_workdays(first, last, skip=skip):
        day_str = day.isoformat()
        week = day.isocalendar().week
        weeks.add(week)

        for ci in commits_index[day_str]:
            prev = author_weekly[ci.author][week]
            author_weekly[ci.author][week] = Stats(
                prev.insertions + ci.insertions,
                prev.deletions + ci.deletions,
                prev.tickets | ci.tickets,
            )

    ## Rating authors
    for author, weekly in author_weekly.items():
        insertions = round(mean(s.insertions for s in weekly.values()), 1)
        deletions = round(mean(s.deletions for s in weekly.values()), 1)
        tickets = reduce(lambda acc, el: acc | el, (s.tickets for s in weekly.values()))
        print(author, "Average", Stats(insertions, deletions, len(tickets)))

        for week in sorted(weeks):
            print(week, weekly[week])


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--today", type=date.fromisoformat, help="The target day in YYYY-MM-DD format"
    )

    args = parser.parse_args()

    config = load_config("project.toml")
    config.today = args.today if args.today else date.today()

    main(args, config)
