#!/usr/bin/env python3
import re
from argparse import ArgumentParser, Namespace
from collections import defaultdict, namedtuple
from datetime import date, timedelta
from types import SimpleNamespace

import matplotlib.pyplot as plt
from matplotlib import style

from helpers.generic import git_log_actions, load_config, reverse_workdays
from helpers.slack import SlackClient

AuthorCommitStats = namedtuple(
    "AuthorCommitStats", "date author insertions deletions tickets"
)
Stats = namedtuple("Stats", "insertions deletions tickets")


def main(args: Namespace, config: SimpleNamespace):
    ## Use settings and arguments
    last = args.today
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

    outfile = plot_code_metrics(args.today, author_weekly)
    publish_metrics_plot(args.today, outfile)


def default_stats():
    return Stats(0, 0, set())


def friday_of_week(week_number, year=2024):
    first_day_of_year = date(year, 1, 1)

    if first_day_of_year.weekday() <= 3:
        start_of_week = first_day_of_year - timedelta(days=first_day_of_year.weekday())
    else:
        start_of_week = first_day_of_year + timedelta(
            days=(7 - first_day_of_year.weekday())
        )

    start_date_of_week = start_of_week + timedelta(weeks=week_number - 1)
    friday_date = start_date_of_week + timedelta(days=4)

    return friday_date


def plot_code_metrics(today: date, author_weekly: dict) -> str:
    """Plot the weekly stats and saves the graph as png"""
    weeks = sorted({week for weekly in author_weekly.values() for week in weekly})

    plt.figure(figsize=(13, 8))

    for author, weekly in author_weekly.items():
        metrics = [
            (stats.insertions * 2 + stats.deletions) / 3
            for week in weeks
            for stats in [weekly[week]]
        ]
        plt.plot(
            weeks,
            metrics,
            label=author,
            linewidth=4,
            alpha=0.72,
        )

    plt.xlabel("Weeks")
    plt.ylabel("Coding score")
    plt.title(f"Weekly code metrics up-to {today.strftime('%a, %-d %b')}")
    plt.xticks(weeks, [friday_of_week(week).isoformat() for week in weeks], rotation=45)
    plt.legend()
    plt.tight_layout()

    fig_file = f"out/weekly_metrics_{today.isoformat()}.png"
    plt.savefig(fig_file)
    plt.close()

    return fig_file


def publish_metrics_plot(today: date, image_file: str):
    slack = SlackClient(config.slack.bot_token, config.slack.channel)
    slack.upload_image(
        intro=f"Coding score stats for {today.strftime('%a, %-d %b')}:",
        file_path=image_file,
    )
    print(
        f"The code metrics plot ({image_file}) was published to "
        f"the #{config.slack.channel} channel."
    )


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=date.today(),
        help="The target day in YYYY-MM-DD format"
    )

    args = parser.parse_args()
    config = load_config("project.toml")

    plt.style.use("ggplot")
    main(args, config)
