"""
ntfy notification sender for Competition Results Monitor.

Sends push notifications for new results, fixture changes,
and all-clear messages.  Each competition has its own ntfy topic,
plus a combined topic per age group.
"""

import os
import requests

from competition_monitor.config import CLUB_NAME, NTFY_ICON, combined_topic_for, competition_url
from gaa_utils import gaa_total


def _priority():
    """Low priority when COMP_NTFY_QUIET is set (CI), high otherwise."""
    return "low" if os.environ.get("COMP_NTFY_QUIET") else "high"


_MAX_BODY_BYTES = 3900  # ntfy.sh converts bodies >4096 bytes to attachment.txt


def _send(topic, title, message, priority=None, action_url=None):
    """Post a message to ntfy.sh."""
    headers = {
        "Title": title,
        "Priority": priority or _priority(),
        "Icon": NTFY_ICON,
        "Content-Type": "text/plain; charset=utf-8",
    }
    if action_url:
        headers["Actions"] = f"view, View Competition, {action_url}"

    body = message.encode("utf-8")
    if len(body) > _MAX_BODY_BYTES:
        truncated = body[: _MAX_BODY_BYTES - 40]
        # avoid cutting mid-character
        truncated = truncated.decode("utf-8", errors="ignore").encode("utf-8")
        body = truncated + b"\n\n... (truncated)"

    try:
        resp = requests.post(
            f"https://ntfy.sh/{topic}",
            data=body,
            headers=headers,
            timeout=10,
        )
        status = "ok" if resp.status_code == 200 else f"status {resp.status_code}"
        print(f"ntfy -> {topic}: {status}")
    except Exception as e:
        print(f"ntfy -> {topic}: FAILED – {e}")


def _send_both(comp_config, title, message, priority=None, action_url=None):
    """Send to the per-competition topic AND the age-group combined topic."""
    comp_topic = comp_config["ntfy_topic"]
    combined = combined_topic_for(comp_config)
    _send(comp_topic, title, message, priority=priority, action_url=action_url)
    if combined and combined != comp_topic:
        _send(combined, title, message, priority=priority,
              action_url=action_url)


def _format_score(result):
    """Format a GAA score as readable text.

    Input:  {"home": "Ballincollig", "away": "Mallow",
             "home_score": "1-6", "away_score": "5-8", "date": "..."}
    Output: "Ballincollig 1-6  v  Mallow 5-8"
    """
    return (f"{result['home']} {result['home_score']}  v  "
            f"{result['away_score']} {result['away']}")


def _our_result_line(result):
    """Describe a Ballincollig result in plain English."""
    home_total = gaa_total(result["home_score"])
    away_total = gaa_total(result["away_score"])

    is_home = CLUB_NAME.lower() in result["home"].lower()
    our_total = home_total if is_home else away_total
    their_total = away_total if is_home else home_total
    opponent = result["away"] if is_home else result["home"]

    if our_total > their_total:
        verb = "defeated"
    elif our_total < their_total:
        verb = "lost to"
    else:
        verb = "drew with"

    our_score = result["home_score"] if is_home else result["away_score"]
    their_score = result["away_score"] if is_home else result["home_score"]

    return f"{CLUB_NAME} {our_score} {verb} {opponent} {their_score}"


# ------------------------------------------------------------------
# Public notification helpers
# ------------------------------------------------------------------

def notify_our_result(comp_config, diff, comp_name):
    """High-priority notification for each Ballincollig result."""
    url = competition_url(comp_config)
    for r in diff["our_new_results"]:
        line = _our_result_line(r)
        standing = ""
        if diff.get("our_standing"):
            s = diff["our_standing"]
            standing = f"\nLeague position: {s['position']} ({s['pts']} pts)"

        _send_both(
            comp_config,
            title=f"{CLUB_NAME} {comp_name} - Result",
            message=f"{line}{standing}",
            priority="high" if not os.environ.get("COMP_NTFY_QUIET") else "low",
            action_url=url,
        )


def notify_other_results(comp_config, diff, comp_name):
    """Normal-priority round-up of non-Ballincollig results."""
    others = [r for r in diff["new_results"]
              if r not in diff["our_new_results"]]
    if not others:
        return

    MAX_SHOW = 15
    lines = [_format_score(r) for r in others[:MAX_SHOW]]
    if len(others) > MAX_SHOW:
        lines.append(f"... and {len(others) - MAX_SHOW} more")
    body = "\n".join(lines)
    url = competition_url(comp_config)

    _send_both(
        comp_config,
        title=f"{comp_name} - Other Results",
        message=body,
        action_url=url,
    )


def notify_fixture_changes(comp_config, diff, comp_name):
    """Notification for fixture time/venue/date updates."""
    parts = []
    for fixture, changes in diff["fixture_changes"]:
        header = f"{fixture['date']} {fixture['home']} vs {fixture['away']}"
        detail = ", ".join(changes)
        parts.append(f"{header}\n  {detail}")

    for fixture in diff["new_fixtures"]:
        parts.append(
            f"NEW: {fixture['date']} {fixture['time']} "
            f"{fixture['home']} vs {fixture['away']}"
        )

    for fixture in diff["removed_fixtures"]:
        parts.append(
            f"REMOVED: {fixture['date']} "
            f"{fixture['home']} vs {fixture['away']}"
        )

    if not parts:
        return

    MAX_PARTS = 20
    if len(parts) > MAX_PARTS:
        extra = len(parts) - MAX_PARTS
        parts = parts[:MAX_PARTS]
        parts.append(f"... and {extra} more changes")

    url = competition_url(comp_config)
    _send_both(
        comp_config,
        title=f"{comp_name} - Fixture Update",
        message="\n\n".join(parts),
        action_url=url,
    )


def notify_first_run(comp_config, diff, comp_name):
    """Low-priority initialisation message."""
    url = competition_url(comp_config)
    _send_both(
        comp_config,
        title=f"{comp_name} - Monitor Started",
        message=(
            f"Now monitoring {comp_name}.\n"
            f"{diff['result_count']} results, "
            f"{diff['fixture_count']} upcoming fixtures.\n"
            f"{len(diff['table'])} teams in the table."
        ),
        priority="low",
        action_url=url,
    )


def notify_all_clear(comp_config, diff, comp_name):
    """Low-priority 'no changes' heartbeat sent to the combined topic only.

    Per-competition topics only receive notifications when there are
    actual changes, keeping noise down for subscribers.
    """
    combined = combined_topic_for(comp_config)
    if not combined:
        return

    url = competition_url(comp_config)

    standing = ""
    if diff.get("our_standing"):
        s = diff["our_standing"]
        standing = f"\nLeague position: {s['position']} ({s['pts']} pts)"

    _send(
        combined,
        title=f"{comp_name} - All Clear",
        message=(
            f"No new results or fixture changes.\n"
            f"{diff['result_count']} results, "
            f"{diff['fixture_count']} upcoming."
            f"{standing}"
        ),
        priority="low",
        action_url=url,
    )
