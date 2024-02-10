# smart-work-logger

Introducing this clever little tool that's about to make your workday a breeze,
with just a hint of magic!

Imagine your git history and JIRA logs going on a date, deciding to team up and
save you hours of tedious work. This nifty script dives deep into the sea of
your git commits, fishes out those precious ticket references, then waltzes over
to JIRA to check what's been logged.

Finding gaps? Fear not! It deftly fills in those missing hours based on your
commits, ensuring your JIRA worklog reflects all your hard work, without you
breaking a sweat.


## ToDO:

- [x] Read values from a config file
- [x] Add proper support for vacation days
- [x] Allow setting ticket id regex
- [x] Add parameter for commit/publish changes
- [ ] Add support for logging daily meetings


## Usage and configuration

To get started, all you need is your trusty [project.toml](./project.toml) file.
This file should include your JIRA credentials, the repositories you're working
with, eventual vacation days and your expected daily work hours.


### Environment variables override

To offer flexibility, Smart Work Logger allows the overriding of specific
configurations through environment variables:

- `API_USER`: Overrides the JIRA API username specified in toml file.
- `API_TOKEN`: Overrides the JIRA API token specified in toml file.

These overrides ensure that your setup can be easily shared without modifying
configuration files, offering both convenience and an additional layer of
security.


### Program arguments

Smart Work Logger supports several command-line arguments to customize its
behavior on each run:
- `--publish`: This flag tells the program to actually post the work logs to
  JIRA. Without this flag, the script runs in a dry-run mode, showing you what
  it would do without making any changes.
- `--today`: Specifies the target day for logging work in YYYY-MM-DD format.
  If not provided, the script assumes the current day.
- `--current_task`: Allows you to specify a JIRA ticket that will be used to
  start the logging process (which works in reverse from today to first day of
  the month). 

These arguments add a layer of control, letting you tailor the logging process
to your needs on a day-to-day basis, whether you're catching up on logs or
prepping for a day of focused work.

By leveraging Smart Work Logger, you're not just automating a task; you're
reclaiming time and ensuring your work logs accurately reflect your
contributions.

It's a small change in your workflow with a big impact on your productivity and
accuracy.


### Running in virtual environment

The [run.sh](./run.sh) script is designed to ensure that your Python script runs
within a virtual environment, leveraging environment variables defined in a .env
file.

Make sure you have a virtual environment set up for your project, using
[requirements.in](./requirements.in).

Configure your `.env` file: define sensible credential variables, for example:
```bash
API_USER=anyone
API_KEY=hasasecret
```

The script automatically exports all variables defined in .env to the
environment, making them accessible to the Python script.

