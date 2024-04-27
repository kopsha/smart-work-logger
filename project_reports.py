#!/usr/bin/env python3
from argparse import ArgumentParser, Namespace
from collections import namedtuple
from datetime import date, datetime
from types import SimpleNamespace

import pandas as pd

from helpers.generic import connect, load_config

# Define a namedtuple for JIRA issues
JiraIssue = namedtuple(
    "Issue",
    [
        "type",
        "key",
        "summary",
        "status",
        "fix_version",
        "story_points",
        "resolved",
        "biweekly",
    ],
)


def main(args: Namespace, config: SimpleNamespace):
    project_id = args.project
    since = args.since

    client, _ = connect(config)

    ## Search relevant JIRA issues
    query = (
        f"project = '{project_id}' AND resolved >= '{since}' AND status = Done "
        "AND resolution in (Done, Fixed) ORDER BY resolved DESC"
    )
    issues = client.search_issues(query, maxResults=False)

    data = list()
    for issue in issues:
        resolved = datetime.fromisoformat(issue.fields.resolutiondate)
        month = resolved.strftime("%b")
        biweek = resolved.isocalendar().week // 2
        year = resolved.isocalendar().year
        formatted_biweekly = f"{year}-{biweek}-{month}"

        issue_data = JiraIssue(
            issue.fields.issuetype.name,
            issue.key,
            issue.fields.summary,
            issue.fields.status.name,
            issue.fields.fixVersions[0].name if issue.fields.fixVersions else "N/A",
            getattr(issue.fields, "customfield_10004", None) or 2,
            resolved.strftime("%Y-%m-%d"),
            formatted_biweekly,
        )
        data.append(issue_data)

    df = pd.DataFrame(data)
    with pd.ExcelWriter("project-report.xlsx", engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)

    print(f"Saved {len(issues)} rows to 'project-report.xlsx'")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-p", "--project", type=str)
    parser.add_argument("-s", "--since", type=date.fromisoformat)
    args = parser.parse_args()

    config = load_config("project.toml")

    main(args, config)
