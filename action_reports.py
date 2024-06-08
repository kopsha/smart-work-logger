#!/usr/bin/env python3
import re
from argparse import ArgumentParser, Namespace
from collections import defaultdict, namedtuple
from datetime import date, timedelta
from types import SimpleNamespace

import matplotlib.pyplot as plt

from helpers.generic import git_log_actions, load_config, reverse_workdays
from helpers.slack import SlackClient

AuthorCommitStats = namedtuple(
    "AuthorCommitStats", "date author insertions deletions tickets"
)
Stats = namedtuple("Stats", "insertions deletions tickets")


def default_stats():
    return Stats(0, 0, set())


def friday_of_week(week_number, year=2024):
    first_day_of_year = date(year, 1, 1)

    # Calculate the start date of the given week (Monday)
    if first_day_of_year.weekday() <= 3:
        # Week starts on the first Monday after or on January 1st
        start_of_week = first_day_of_year - timedelta(days=first_day_of_year.weekday())
    else:
        # Week starts on the first Monday after January 1st
        start_of_week = first_day_of_year + timedelta(
            days=(7 - first_day_of_year.weekday())
        )

    start_date_of_week = start_of_week + timedelta(weeks=week_number - 1)
    friday_date = start_date_of_week + timedelta(days=4)

    return friday_date


def main(args: Namespace, config: SimpleNamespace):
    ## Use settings and arguments
    last = config.today
    weeks_behind = last - timedelta(weeks=config.weeks_behind)
    first = weeks_behind - timedelta(days=weeks_behind.weekday())

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
                    a_date, commit.author.title(), insertions, deletions, tickets
                )
            )

    ## Build weekly stats
    author_weekly = {
        author: defaultdict(default_stats) for author in sorted(seen_authors)
    }
    weeks = set()
    fridays = set()
    for day in reverse_workdays(first, last, skip=skip):
        day_str = day.isoformat()
        week = day.isocalendar().week
        weeks.add(week)

        days_to_friday = 4 - day.weekday()
        friday = day + timedelta(days=days_to_friday)
        fridays.add(friday.isoformat())

        for ci in commits_index[day_str]:
            prev = author_weekly[ci.author][week]
            author_weekly[ci.author][week] = Stats(
                prev.insertions + ci.insertions,
                prev.deletions + ci.deletions,
                prev.tickets | ci.tickets,
            )

    # Extract all weeks
    weeks = sorted({week for weekly in author_weekly.values() for week in weekly})

    # Prepare data for plotting
    plt.figure(figsize=(14, 8))

    # Calculate the metrics and plot for each author
    markers = ["x", "*", "o", "+", "d"]
    for i, (author, weekly) in enumerate(author_weekly.items()):
        metrics = [
            (stats.insertions * 2 + stats.deletions) / 3
            for week in weeks
            for stats in [weekly[week]]
        ]
        plt.plot(weeks, metrics, marker=markers[i % len(markers)], label=author)

    plt.xlabel("Weeks")
    plt.ylabel("Coding score")
    plt.title(f"Weekly code metrics up-to {config.today}")
    plt.xticks(weeks, [friday_of_week(week).isoformat() for week in weeks], rotation=45)
    plt.legend()
    plt.tight_layout()

    fig_file = f"weekly_metrics_{config.today}.png"
    plt.savefig(fig_file)

    slack = SlackClient(config.slack.bot_token, config.slack.channel)
    slack.upload_image(
        intro=f"Coding score stats for {config.today.strftime('%a %d %b')}:",
        file_path=fig_file,
    )
    print(f"{fig_file} was published to slack channel.")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--today", type=date.fromisoformat, help="The target day in YYYY-MM-DD format"
    )

    args = parser.parse_args()

    config = load_config("project.toml")
    config.today = args.today if args.today else date.today()

    main(args, config)
