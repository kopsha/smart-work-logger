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


def publish_blocks(config: SimpleNamespace, data: dict):
    token = config.slack.bot_token
    channel_id = config.slack.channel
    message = "Hello, this is a test message from Python using requests!"
    send_slack_message(token, channel_id, message)


def main(args: Namespace, config: SimpleNamespace):
    ## Use settings and arguments
    # last = config.today
    # first = last - timedelta(days=7 * 8)
    # ignore_pattern = re.compile(config.ignore_file_pattern)
    # ticket_pattern = re.compile(config.ticket_pattern)
    # skip = set()
    #
    # ## Merge and index all GIT commits by date
    # commits_index = defaultdict(list)
    # seen_files = set()
    # seen_authors = set()
    # for repo in config.repositories:
    #     history, commit_actions = git_log_actions(
    #         repo, start=first, end=last, skip_files=ignore_pattern
    #     )
    #     for commit in history:
    #         seen_authors.add(commit.author.title())
    #
    #         insertions, deletions = 0, 0
    #         for action in commit_actions[commit.hash]:
    #             seen_files.add(action.path)
    #             insertions += int(action.insertions)
    #             deletions += int(action.deletions)
    #         a_date = date.fromisoformat(commit.date)
    #
    #         tickets = set(ticket_pattern.findall(commit.message))
    #
    #         commits_index[commit.date].append(
    #             AuthorCommitStats(
    #                 a_date, commit.author.title(), insertions, deletions, tickets
    #             )
    #         )
    #
    # ## Build weekly stats
    # author_weekly = {
    #     author: defaultdict(default_stats) for author in sorted(seen_authors)
    # }
    # weeks = set()
    # fridays = set()
    # for day in reverse_workdays(first, last, skip=skip):
    #     day_str = day.isoformat()
    #     week = day.isocalendar().week
    #     weeks.add(week)
    #
    #     days_to_friday = 4 - day.weekday()
    #     friday = day + timedelta(days=days_to_friday)
    #     fridays.add(friday.isoformat())
    #
    #     for ci in commits_index[day_str]:
    #         prev = author_weekly[ci.author][week]
    #         author_weekly[ci.author][week] = Stats(
    #             prev.insertions + ci.insertions,
    #             prev.deletions + ci.deletions,
    #             prev.tickets | ci.tickets,
    #         )
    #
    # # Extract all weeks
    # weeks = sorted({week for weekly in author_weekly.values() for week in weekly})
    #
    # # Prepare data for plotting
    # plt.figure(figsize=(14, 8))
    #
    # # Calculate the metrics and plot for each author
    # markers = ["x", "*", "o", "+", "d"]
    # for i, (author, weekly) in enumerate(author_weekly.items()):
    #     metrics = [
    #         (stats.insertions * 3 + stats.deletions) / 4
    #         for week in weeks
    #         for stats in [weekly[week]]
    #     ]
    #     plt.plot(weeks, metrics, marker=markers[i % len(markers)], label=author)
    #
    # plt.xlabel("Weeks")
    # plt.ylabel("Metric")
    # plt.title("Weekly Metrics per Author")
    # plt.xticks(weeks, [f"Week {week}" for week in weeks], rotation=45)
    # plt.legend()
    # plt.tight_layout()
    #
    # plt.savefig(f"weekly_metrics_{config.today}.png")

    slack = SlackClient(config.slack.bot_token, config.slack.channel)
    slack.upload_image(
        f"Weekly metrics up-to {config.today}",
        f"weekly_metrics_{config.today}.png"
    )


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--today", type=date.fromisoformat, help="The target day in YYYY-MM-DD format"
    )

    args = parser.parse_args()

    config = load_config("project.toml")
    config.today = args.today if args.today else date.today()

    main(args, config)
