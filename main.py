#!/usr/bin/env python3
from datetime import date, timedelta, datetime
from collections import namedtuple, defaultdict
import heapq
import os

from jira import JIRA

from pprint import pprint


WorklogEntry = namedtuple("WorklogEntry", "date issue time_spent author")


def connect():
    api_user = os.getenv("API_USER")
    api_key = os.getenv("API_TOKEN")
    api_root = "https://jibecompany.atlassian.net"
    client = JIRA(options={"server": api_root}, basic_auth=(api_user, api_key))

    user = client.myself()
    print("Connected as", user["displayName"], "::", user["accountId"])

    return client, user["accountId"]


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


def workdays(start: date, end: date):
    current = start
    while current <= end:
        if current.weekday() < 5:
            yield current
        current += timedelta(days=1)


def main():
    client, user = connect()

    any_date = date(2023, 12, 1)
    first, last = first_and_last(any_date)
    my_worklogs = get_worklogs(client, user, first, last)

    total = 0
    for day in workdays(first, last):
        daily_logs = my_worklogs.get(str(day), [])
        daily_hours = sum(log.time_spent for log in daily_logs)
        print(day, daily_hours)
        total += daily_hours

    print(f"{total=}")

if __name__ == "__main__":
    main()
