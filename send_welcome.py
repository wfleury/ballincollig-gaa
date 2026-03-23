#!/usr/bin/env python3
"""
Send a one-time welcome notification to all ntfy topics.

Run this just before sharing the WhatsApp subscription link so that
new subscribers see a confirmation message when they first open the app.
Messages are cached on ntfy.sh for ~12 hours.

Usage:
    python send_welcome.py            # send to all topics
    python send_welcome.py --dry-run  # preview without sending
"""

import sys
import time
import requests
from config import (
    CLUB_NAME, NTFY_TOPIC, NTFY_ICON, NTFY_FIXTURES_URL,
    CLUBZAP_TEAM_IDS, team_ntfy_topic, team_fixtures_url,
)

WELCOME_TITLE = f"{CLUB_NAME} GAA - Notifications Active"
WELCOME_MSG = (
    f"You're subscribed to {CLUB_NAME} GAA fixture alerts.\n"
    "You'll be notified whenever fixtures are added, changed, or postponed.\n\n"
    "No action needed — sit back and we'll keep you posted."
)

TEAM_WELCOME_MSG = (
    "You're subscribed to {team} fixture alerts.\n"
    "You'll be notified whenever a {team} fixture is added, changed, or postponed.\n\n"
    "No action needed — sit back and we'll keep you posted."
)


def send(topic, title, message, fixtures_url, dry_run=False):
    """Publish a welcome notification to a single ntfy topic."""
    if dry_run:
        print(f"  [DRY-RUN] {topic}")
        return True
    try:
        resp = requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": "low",
                "Tags": "white_check_mark",
                "Icon": NTFY_ICON,
                "Actions": f"view, View Fixtures, {fixtures_url}",
            },
            timeout=10,
        )
        ok = resp.status_code == 200
        status = "OK" if ok else f"HTTP {resp.status_code}"
        print(f"  {topic} — {status}")
        return ok
    except Exception as e:
        print(f"  {topic} — ERROR: {e}")
        return False


def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=== DRY RUN — no notifications will be sent ===\n")

    # 1. Main (all-fixtures) topic
    print(f"Main topic ({NTFY_TOPIC}):")
    send(NTFY_TOPIC, WELCOME_TITLE, WELCOME_MSG, NTFY_FIXTURES_URL, dry_run)

    # 2. Per-team topics
    print(f"\nPer-team topics ({len(CLUBZAP_TEAM_IDS)} teams):")
    for team_name in CLUBZAP_TEAM_IDS:
        topic = team_ntfy_topic(team_name)
        title = f"{CLUB_NAME} {team_name} - Notifications Active"
        msg = TEAM_WELCOME_MSG.format(team=team_name)
        url = team_fixtures_url(team_name)
        send(topic, title, msg, url, dry_run)
        if not dry_run:
            time.sleep(0.5)  # be kind to ntfy.sh rate limits

    print("\nDone.")


if __name__ == "__main__":
    main()
