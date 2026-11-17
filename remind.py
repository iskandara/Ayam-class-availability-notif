#!/usr/bin/env python3
"""Send a daily phone reminder (via ntfy) to check the Melbourne Law Masters subject page.

The page only refreshes once a day and blocks automated readers, so a reminder
with a one-tap link is the reliable option.

Usage:
  python remind.py            # send now
  python remind.py --gate     # send only if it is 10am in Melbourne (used by the schedule)
  python remind.py --dry-run  # print instead of sending

Env: NTFY_TOPIC (required unless --dry-run)
"""
import argparse
import os
import sys
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

URL = "https://law.unimelb.edu.au/students/masters/studies/enrolment/mlm-subjects"
SEND_HOUR = 10  # Melbourne time; the page seems to refresh around 9:30am (unconfirmed)

SUBJECTS = [
    "Negotiation and Dispute Resolution (LAWS90080), 06 Apr 27 or 14 Apr 27",
    "International Economic Law, April 2027 (not listed yet)",
    "International Commercial Arbitration (LAWS70121), any offering",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    now = datetime.now(ZoneInfo("Australia/Melbourne"))
    if a.gate and now.hour != SEND_HOUR:
        print(f"Melbourne time {now:%H:%M}: not reminder time, skipping")
        return 0

    title = "Check class seats"
    body = ("Tap to open the subject page. Look for 'Yes - self-enrol' or "
            "'Submit enrolment request' on:\n- " + "\n- ".join(SUBJECTS) +
            "\nAlso note the page's 'Last updated' time.")
    if a.dry_run:
        print(title, "\n", body, sep="")
        return 0

    req = urllib.request.Request(
        f"https://ntfy.sh/{os.environ['NTFY_TOPIC']}", data=body.encode("utf-8"),
        headers={"Title": title, "Priority": "high", "Tags": "mortar_board", "Click": URL})
    urllib.request.urlopen(req, timeout=30).read()
    print("Reminder sent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
