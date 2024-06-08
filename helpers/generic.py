#!/usr/bin/env python3
import os
import re
import subprocess
import tomllib
from collections import abc, defaultdict, namedtuple
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from jira import JIRA

WorklogEntry = namedtuple("WorklogEntry", "date issue time_spent author")
GitlogEntry = namedtuple("GitlogEntry", "date time message")

GitCommit = namedtuple("GitCommit", "hash date author message tags")
CommitAction = namedtuple("CommitAction", "insertions deletions path")


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
    if token := os.getenv("SLACK_BOT_TOKEN"):
        config["slack"]["bot_token"] = token

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


def git_log_actions(
    repository_path: str, start: date, end: date, skip_files: re.Pattern
) -> tuple[list[GitCommit], dict[str, list[CommitAction]]]:
    """returns all git commits with its summary by file"""

    root = os.path.abspath(repository_path)
    repo_name = os.path.basename(root)
    branch = shell(f"git -C {root} branch --show-current")

    print(f"Updating repository {repo_name} on {branch=}")
    shell(f"git -C {root} pull")
    cmd = (
        f"git -C {root} log --numstat --since={start.isoformat()} --until={end.isoformat()} "
        "--pretty=format:'$%h$%ad$%an$%s$%d' --date=format:'%Y-%m-%d'"
    )
    output = shell(cmd)

    history = list()
    commit_actions = defaultdict(list)
    last_commit = None
    for line in output.splitlines():
        if not line.strip():
            continue

        if line.startswith("$"):
            last_commit = GitCommit(*line.lstrip("$").split("$"))
            history.append(last_commit)
        else:
            action_metas = line.strip().split("\t")
            action = CommitAction(*action_metas)
            if not skip_files.search(action.path) and "vendor" not in action.path and "migrations" not in action.path:
                commit_actions[last_commit.hash].append(action)

    return history, commit_actions


if __name__ == "__main__":
    raise RuntimeError("This is module is not executable")
