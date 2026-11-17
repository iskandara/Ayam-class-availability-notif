# Class seat watcher

Sends a phone notification every morning at 10am (Melbourne time) reminding you to check the
[Melbourne Law Masters subject page](https://law.unimelb.edu.au/students/masters/studies/enrolment/mlm-subjects).
Tap the notification to open the page.

## Setup
1. Install the **ntfy** app (iOS / Android) and subscribe to your topic (server: ntfy.sh).
2. In this repo: Settings → Secrets and variables → Actions → secret `NTFY_TOPIC` = that topic.
3. Actions → **daily-reminder** → Run workflow, to test.

## Files
- `remind.py` + `daily-reminder` workflow: the daily reminder (scheduled).
- `check.py` + `live-check-test` workflow: tries to read the page automatically. Manual only;
  the site's bot protection usually blocks it, and it will tell you if so.

Tip: also email the Law School enrolment team about a waitlist, since the page is not real-time.
