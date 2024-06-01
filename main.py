#!/usr/bin/env python3
import os
import re
import subprocess
import tomllib
from argparse import ArgumentParser, Namespace
from collections import abc, defaultdict, namedtuple
from datetime import date, datetime, timedelta
from math import isclose
from types import SimpleNamespace

from jira import JIRA

WorklogEntry = namedtuple("WorklogEntry", "date issue time_spent author")
GitlogEntry = namedtuple("GitlogEntry", "date time message")


def ns_from(config: dict) -> SimpleNamespace:
    """Creates namespace objects from config dictionary"""

    for key, value in config.items():
        if isinstance(value, dict):
            config[key] = ns_from(value)
    return SimpleNamespace(**config)


def load_config(filename: str) -> SimpleNamespace:
    """Parses a TOML configuration file"""

    with open(filename, "rb") as config_file:
        config = tomllib.load(config_file)

    # Environment variable overrides
    if api_user := os.getenv("API_USER"):
        config["jira"]["api_user"] = api_user
    if api_key := os.getenv("API_TOKEN"):
        config["jira"]["api_key"] = api_key

    ns_config = ns_from(config)
    return ns_config


def connect(config: SimpleNamespace) -> tuple[JIRA, dict]:
    """Establishes a connection to the JIRA server and returns the client and user information"""

    client = JIRA(
        options={"server": config.jira.server},
        basic_auth=(config.jira.api_user, config.jira.api_key),
    )

    user = client.myself()
    print("Connected as", user["displayName"], "::", user["accountId"])

    return client, user


def get_worklogs(
    client: JIRA, user: str, first: date, last: date
) -> defaultdict[str, list[WorklogEntry]]:
    """Fetches existing worklogs from JIRA for a given user and date range."""

    print("Looking up JIRA worklogs between", first, "and", last)
    query = (
        f"worklogAuthor = {user} AND worklogDate >= {first} AND worklogDate <= {last}"
    )
    issues = client.search_issues(query, expand="changelog", maxResults=False)

    worklogs = defaultdict(list)
    for issue in issues:
        for log in client.worklogs(issue.id):
            logged_date = datetime.strptime(log.started[:10], "%Y-%m-%d").date()
            if first <= logged_date <= last and log.author.accountId == user:
                entry = WorklogEntry(
                    date=logged_date,
                    issue=issue.key,
                    time_spent=log.timeSpentSeconds / 3600,
                    author=log.author.displayName,
                )
                worklogs[entry.date.isoformat()].append(entry)

    return worklogs


def reverse_workdays(
    start: date, end: date, skip: set[date]
) -> abc.Generator[date, None, None]:
    """Generates workdays in reverse order from end to start, excluding specified skip days."""

    current = end
    while current >= start:
        if current.weekday() < 5 and current not in skip:
            yield current
        current -= timedelta(days=1)


def make_skip_days(date_items: list[str]) -> set[date]:
    """Parses a list of dates or ranges to create a set of dates to be skipped"""

    skip_days = set()
    for item in date_items:
        if ".." in item:
            left, right = item.split("..")
            first = date.fromisoformat(left)
            last = date.fromisoformat(right)

            it = first
            while it <= last:
                if it.weekday() < 5:
                    skip_days.add(it)
                it += timedelta(days=1)
        else:
            it = date.fromisoformat(item)
            if it.weekday() < 5:
                skip_days.add(it)

    return skip_days


def shell(command: str) -> str:
    """Runs shell command and capture the output"""

    result = subprocess.run(command, shell=True, capture_output=True)
    if result.returncode:
        raise ChildProcessError(result.stderr.decode("utf-8").strip())

    return result.stdout.decode("utf-8").strip()


def git_log_filter(
    repository_path: str, start: date, end: date, author: str
) -> list[GitlogEntry]:
    """Parses git commits within date range filtered by the author email"""

    root = os.path.abspath(repository_path)
    repo_name = os.path.basename(root)
    branch = shell(f"git -C {root} branch --show-current")

    print(f"Updating repository {repo_name} on {branch=}")
    shell(f"git -C {root} pull")
    cmd = (
        f"git -C {root} log --since={start.isoformat()} --until={end.isoformat()} "
        f"--date=format:'%Y-%m-%d?&?%H:%M:%S' --pretty=format:'%cd?&?%s' --{author=}"
    )
    output = shell(cmd)
    entries = [GitlogEntry(*line.split("?&?")) for line in output.splitlines()]

    return entries


def find_all_ticket_ids(
    gitlog_entries: list[GitlogEntry], use_pattern: re.Pattern
) -> list[str]:
    """Finds all ticket IDs in git log entries using a regex pattern."""

    tickets = dict()
    for entry in gitlog_entries:
        found_tickets = use_pattern.findall(entry.message)
        for ticket in found_tickets:
            if ticket.startswith("FOOD"):
                ticket = ticket.replace("FOOD", "DATAU")
            tickets.setdefault(ticket, None)

    return list(tickets.keys())


def make_time_logs(
    author: str, day: str, goal_hours: float, tickets: list[str]
) -> list[WorklogEntry]:
    """Creates worklog entries for a given day and set of tickets."""
    effort = goal_hours / len(tickets)
    logs = [WorklogEntry(day, t, effort, author) for t in tickets]
    return logs


def preview_day_logs(worklogs: list):
    for log in worklogs:
        print(f" -> Assumed {log.time_spent}h on {log.issue}, for {log.date}")


def publish_jira_worklogs(worklogs: dict[str, list[WorklogEntry]], client: JIRA):
    for logs in worklogs.values():
        for log in logs:
            client.add_worklog(
                issue=log.issue,
                timeSpent=f"{log.time_spent}h",
                started=datetime.fromisoformat(log.date),
            )


def main(args: Namespace, config: SimpleNamespace):
    ## Use settings and arguments
    first = config.today.replace(day=1)
    last = config.today
    skip = make_skip_days(config.skip_days)
    current_task = args.current_task
    daily_target = float(config.daily_target)
    daily_ticket, daily_duration = config.daily_meeting

    ticket_pattern = re.compile(config.ticket_pattern)
    author_pattern = config.git_author_pattern

    ## Read JIRA worklogs
    client, user = connect(config)
    worklogs = get_worklogs(client, user["accountId"], first, last)

    ## Read and merge all GIT logs
    gitlogs = defaultdict(list)
    for repo in config.repositories:
        logs = git_log_filter(repo, first, last, author_pattern)
        for log in logs:
            gitlogs[log.date].append(log)

    ## Compute new logs by filling incomplete days
    missing_logs = defaultdict(list)
    for day in reverse_workdays(first, last, skip):
        day_str = day.isoformat()

        day_logs = sorted(gitlogs[day_str], key=lambda x: x.time, reverse=True)
        day_tickets = find_all_ticket_ids(day_logs, use_pattern=ticket_pattern)
        if current_task and current_task not in day_tickets:
            tickets = [current_task] + day_tickets
        else:
            tickets = day_tickets

        already_booked = sum(x.time_spent for x in worklogs[day_str])
        remaining_hours = daily_target - already_booked
        daily_meetings = set(
            x.issue
            for x in worklogs[day_str]
            if x.issue == daily_ticket and isclose(x.time_spent, daily_duration)
        )

        if tickets:
            current_task = tickets[-1]

        if remaining_hours > 0 and tickets:
            if daily_meetings:
                meeting_logs = []
            else:
                meeting_logs = make_time_logs(user["accountId"], day_str, daily_duration, [daily_ticket])
                remaining_hours -= daily_duration

            new_logs = meeting_logs + make_time_logs(
                user["accountId"], day_str, remaining_hours, tickets
            )
            preview_day_logs(new_logs)
            missing_logs[day_str].extend(new_logs)
        else:
            print(f" -> No logs needed for {day_str}, {already_booked=} hours.")

    ## Actually writing something
    if args.publish:
        publish_jira_worklogs(missing_logs, client)
        print(f"Published {len(missing_logs)} work logs to {config.jira.server}.")
    else:
        print("Worklogs were not published, please run with --publish.")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "-p",
        "--publish",
        action="store_true",
        help="Publishes the generated logs to JIRA",
    )
    parser.add_argument(
        "--today", type=date.fromisoformat, help="The target day in YYYY-MM-DD format"
    )
    parser.add_argument(
        "--current-task",
        type=str,
        help="Specifies the current task to start logging from",
    )

    args = parser.parse_args()

    config = load_config("project.toml")
    config.today = args.today if args.today else date.today()

    main(args, config)
