#!/usr/bin/env python3
from datetime import date
from collections import defaultdict
from types import SimpleNamespace
from argparse import ArgumentParser, Namespace


from helpers.generic import (
    make_skip_days,
    load_config,
    connect,
    get_worklogs,
    reverse_workdays,
)


def main(args: Namespace, config: SimpleNamespace):
    ## Use settings and arguments
    first = config.today.replace(day=1)
    last = config.today
    skip = make_skip_days(config.skip_days)

    ## Read JIRA worklogs
    client, _ = connect(config)
    user_email = args.user or config.jira.api_user

    users = client.search_users(query=user_email)
    if len(users) != 1:
        print("Users matching", user_email)
        print(*users, sep=",\n")
        raise RuntimeError(f"Expected exactly one user, found {len(users)}")

    user = users.pop()
    worklogs = get_worklogs(client, user.accountId, first, last)

    print("Found worklogs of", user.displayName)
    tickets_acc = defaultdict(float)
    hours_acc = 0.0

    print("* Daily summary *")
    for day in reverse_workdays(first, last, skip):
        day_str = day.isoformat()
        
        if day_str in worklogs:
            tickets = {log.issue for log in worklogs[day_str]}
            hours = sum(log.time_spent for log in worklogs[day_str])

            for log in worklogs[day_str]:
                tickets_acc[log.issue] += log.time_spent

            day_tickets = ", ".join(sorted(tickets))
            print(f"  -  {day_str}: {hours:5.1f} ({day_tickets})")
            hours_acc += hours

    print("\n", "* Ticket summary *")
    for issue, hours in tickets_acc.items():
        print(f"  -  {issue:10}: {hours:>6.1f} h")
    print("               -----------")
    print(f"       (total)   {hours_acc:>6.1f} h")



if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-u", "--user", type=str)
    parser.add_argument("--today", type=date.fromisoformat)
    args = parser.parse_args()

    config = load_config("project.toml")
    config.today = args.today if args.today else date.today()

    main(args, config)
