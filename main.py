#!/usr/bin/env python3
from datetime import date, timedelta, datetime
from collections import namedtuple, defaultdict
import os
import re
import subprocess

from jira import JIRA

from pprint import pprint


WorklogEntry = namedtuple("WorklogEntry", "date issue time_spent author")
GitlogEntry = namedtuple("GitlogEntry", "date time message")
TICKET_PATTERN = re.compile(r"#([A-Z]{4}-\d+)")
DAILY_HOURS = 8.0


def connect():
    api_user = os.getenv("API_USER")
    api_key = os.getenv("API_TOKEN")
    api_root = "https://jibecompany.atlassian.net"
    client = JIRA(options={"server": api_root}, basic_auth=(api_user, api_key))

    user = client.myself()
    print("Connected as", user["displayName"], "::", user["accountId"])

    return client, user


def first_and_last(of_date: date):
    start = of_date.replace(day=1)

    if of_date.month == 12:  # Special case for December
        end = of_date.replace(year=of_date.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = of_date.replace(month=of_date.month + 1, day=1) - timedelta(days=1)

    return start, end


def get_worklogs(client: JIRA, user: dict, first: date, last: date):
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
                worklogs[str(entry.date)].append(entry)

    return worklogs


def reverse_workdays(start: date, end: date, skip: set):
    current = end
    while current >= start:
        if current.weekday() < 5 and current not in skip:
            yield current
        current -= timedelta(days=1)


def make_skip_days(date_items):
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


def exec_no_fail(command):
    """runs shell command and capture the output"""
    result = subprocess.run(command, shell=True, capture_output=True)
    if result.returncode:
        print(f"Error executing: {command}")
        exit(result.stderr.decode("utf-8").strip())
    return result.stdout.decode("utf-8").strip()


def git_log_filter(repository_path: str, start: date, end: date, email: str):
    """parses all git commits between the dates filtered by the author email"""
    root = os.path.abspath(repository_path)
    repo_name = os.path.basename(root)
    branch = exec_no_fail(f"git -C {root} branch --show-current")

    print(f"Updating repository {repo_name} on {branch=}")
    exec_no_fail(f"git -C {root} pull")
    cmd = (
        f"git -C {root} log --since={start.isoformat()} --until={end.isoformat()} "
        f"--date=format:'%Y-%m-%d?&?%H:%M:%S' --pretty=format:'%cd?&?%s' --author={email}"
    )
    output = exec_no_fail(cmd)
    entries = [GitlogEntry(*line.split("?&?")) for line in output.splitlines()]

    return entries


def find_all_ticket_ids(gitlog_entries):
    tickets = dict()
    for entry in gitlog_entries:
        found_tickets = TICKET_PATTERN.findall(entry.message)
        for ticket in found_tickets:
            if ticket == "SOOL-2349":
                ticket = "SOOL-2340"
            tickets.setdefault(ticket, None)

    return list(tickets.keys())


def make_time_logs(author: str, day: str, goal_hours: float, tickets: list):
    effort = goal_hours / len(tickets)
    logs = [WorklogEntry(day, t, effort, author) for t in tickets]
    return logs


def publish_jira_worklogs(client: JIRA, worklogs: list):
    """Adds a worklog to a JIRA ticket."""
    for log in worklogs:
        print(f" -> Pushing {log.time_spent} h on {log.issue}, for {log.date}")
        client.add_worklog(
            issue=log.issue,
            timeSpent=f"{log.time_spent}h",
            started=datetime.fromisoformat(log.date),
        )


def main():
    ## These might turn into program args
    repos = [
        "../../work/partner-portal/",
        "../../work/configurator-api/",
        "../../work/configurator-www",
    ]
    any_date = date(2024, 1, 5)

    ## Start the job
    first, last = first_and_last(any_date)
    skip = make_skip_days(
        ["2024-01-01..2024-01-05", "2024-01-24", "2024-01-29..2024-01-31"]
    )

    ## Read JIRA worklogs
    client, user = connect()
    worklogs = get_worklogs(client, user["accountId"], first, last)

    ## Read and merge all GIT logs
    gitlogs = defaultdict(list)
    for repo in repos:
        logs = git_log_filter(repo, first, last, user["emailAddress"])
        for log in logs:
            gitlogs[log.date].append(log)

    ## Fill in missing days
    current_task = "SOOL-2215"  # This may be set from program args
    for day in reverse_workdays(first, last, skip):
        day_str = str(day)

        day_logs = sorted(gitlogs[day_str], key=lambda x: x.time, reverse=True)
        day_tickets = find_all_ticket_ids(day_logs)
        tickets = [current_task] + day_tickets if current_task else day_tickets

        remaining_hours = float(DAILY_HOURS) - sum(
            x.time_spent for x in worklogs[day_str]
        )
        if remaining_hours > 0 and tickets:
            current_task = tickets[-1]
            new_logs = make_time_logs(
                user["accountId"], day_str, remaining_hours, tickets
            )
            publish_jira_worklogs(client, new_logs)


if __name__ == "__main__":
    main()
