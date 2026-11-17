#!/usr/bin/env python3
"""Watch the Melbourne Law Masters subject page and push a phone alert via ntfy.

Usage:
  python check.py            # alert only if a watched subject is NOT "Subject full"
  python check.py --digest   # always send a status summary
  python check.py --file x.html --dry-run   # test on a saved page, print only

Env: NTFY_TOPIC (required unless --dry-run)
"""
import argparse
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

URL = "https://law.unimelb.edu.au/students/masters/studies/enrolment/mlm-subjects"

# What to watch. "dates" = only offerings starting on one of these (page format: "06 Apr 27").
# Leave dates empty to watch every offering of that subject.
WATCH = [
    {"label": "Negotiation and Dispute Resolution (LAWS90080)",
     "match": "negotiation and dispute resolution", "dates": ["06 Apr 27", "14 Apr 27"]},
    {"label": "International Economic Law (Apr 2027)",
     "match": "international economic law", "dates": [r"\d{2} Apr 27"]},
    {"label": "International Commercial Arbitration",
     "match": "international commercial arbitration", "dates": []},
]


class RowParser(HTMLParser):
    """Collect every <tr> as a list of cell texts."""

    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell, self._in_cell = [], None, [], False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._in_cell, self._cell = True, []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._in_cell:
            self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._in_cell = False
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._in_cell:
            self._cell.append(data)


def classify(row_text):
    t = row_text.lower()
    if "subject full" in t:
        return "FULL"
    if "self-enrol" in t or "self enrol" in t:
        return "OPEN"
    if "enrolment request" in t:
        return "REQUEST"
    return "UNKNOWN"


def fetch(path=None):
    """Return (status_code, html)."""
    if path:
        return 200, open(path, encoding="utf-8").read()
    req = urllib.request.Request(URL, headers={"User-Agent": "class-seat-watcher (personal, a few requests per day)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def is_bot_challenge(code, html):
    """The site sits behind Cloudflare, which can answer scripts with a 'Just a moment...' page."""
    return code in (403, 429, 503) and ("_cf_chl_opt" in html or "Just a moment" in html)


def last_updated(html):
    """The page's own 'Last updated: 21 Oct 2026 9:29am' stamp, if present."""
    text = re.sub(r"<[^>]+>", " ", html)
    m = re.search(r"Last updated:?\s*(\d{1,2} \w{3} \d{4},? \d{1,2}:\d{2}\s*[ap]m)", text, re.I)
    return m.group(1) if m else None


def evaluate(html):
    p = RowParser()
    p.feed(html)
    rows = p.rows
    if not any(re.search(r"LAWS\d{5}", " ".join(r)) for r in rows):
        return None, rows  # layout changed or page failed to load
    results = []
    for w in WATCH:
        found = []
        for r in rows:
            text = " ".join(r)
            if w["match"] not in text.lower():
                continue
            if w["dates"] and not any(re.search(d, text, re.I) for d in w["dates"]):
                continue
            start = re.search(r"\d{2} [A-Z][a-z]{2} \d{2}", text)
            found.append({"name": r[0], "start": start.group(0) if start else "?",
                          "status": classify(text), "raw": r[-1]})
        results.append({"label": w["label"], "offerings": found})
    return results, rows


def notify(title, body, priority="default", tags=""):
    topic = os.environ["NTFY_TOPIC"]
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}", data=body.encode("utf-8"),
        headers={"Title": title, "Priority": priority, "Tags": tags, "Click": URL})
    urllib.request.urlopen(req, timeout=30).read()


ICON = {"FULL": "FULL", "OPEN": "OPEN - self-enrol!", "REQUEST": "OPEN - submit enrolment request!",
        "UNKNOWN": "CHECK PAGE (unrecognised status)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--digest", action="store_true")
    ap.add_argument("--file")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--gate", action="store_true",
                    help="only run at 01,04,07,10,13,16,19,22 Melbourne time")
    a = ap.parse_args()
    send = (lambda *x, **k: print("NOTIFY:", x, k)) if a.dry_run else notify

    if a.gate:
        hour = datetime.now(ZoneInfo("Australia/Melbourne")).hour
        if hour % 3 != 1:
            print(f"Melbourne hour {hour}: not a check slot, skipping")
            return 0

    code, html = fetch(a.file)
    if is_bot_challenge(code, html):
        send("Seat watcher: blocked by the website",
             "The uni site's bot protection refused this automated check. "
             "Open the page yourself to see the current status.", "high", "warning")
        print(f"HTTP {code}: Cloudflare challenge, page not readable", file=sys.stderr)
        return 1

    stamp = last_updated(html)
    results, rows = evaluate(html)
    if results is None:
        send("Seat watcher: page changed", "Could not find the subject table. Check the page manually.",
             "high", "warning")
        print(f"HTTP {code}: no subject rows found", file=sys.stderr)
        return 1

    lines, alert = [], False
    for r in results:
        if not r["offerings"]:
            lines.append(f"{r['label']}: not listed yet")
            continue
        for o in r["offerings"]:
            lines.append(f"{o['name']} ({o['start']}): {ICON[o['status']]}")
            alert |= o["status"] != "FULL"
    if stamp:
        lines.append(f"Page last updated: {stamp}")
    body = "\n".join(lines)
    print(body)

    if alert:
        send("SEAT AVAILABLE - enrol now", body, "urgent", "rotating_light")
    elif a.digest:
        send("Class status: all full", body, "default", "calendar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
