"""
Auto-discovery of new underage competitions involving Ballincollig.

Scrapes the rebelog.ie fixtures page for competitions matching the
configured AGE_GROUPS patterns that include Ballincollig but aren't
already in our config.  When a new competition appears (e.g.
championship), sends a notification so the user knows to add it.
"""

import re
import time

from selenium.webdriver.common.by import By

from competition_monitor.config import (
    AGE_GROUPS, CLUB_NAME, COMPETITIONS, NTFY_COMBINED_TOPIC,
    REBELOG_BASE_URL, get_active_age_groups,
)


# All competition IDs we already monitor
_KNOWN_IDS = {c["competition_id"] for c in COMPETITIONS.values()}


def _active_discovery_patterns():
    """Return discovery patterns for the currently active age groups only."""
    return {
        ag["discovery_pattern"].lower()
        for ag in get_active_age_groups().values()
        if "discovery_pattern" in ag
    }


def _matches_any_age_group(name):
    """Return True if the competition name matches any active age group."""
    lower = name.lower()
    return any(pat in lower for pat in _active_discovery_patterns())


def _age_group_for_name(name):
    """Return the AGE_GROUPS key for a competition name, or None."""
    lower = name.lower()
    for key, ag in AGE_GROUPS.items():
        pat = ag.get("discovery_pattern", "").lower()
        if pat and pat in lower:
            return key
    return None


def _club_in_competition(driver, league_url):
    """Load a league page and check whether CLUB_NAME appears in it."""
    try:
        driver.get(league_url)
        time.sleep(2)
        return CLUB_NAME.lower() in driver.page_source.lower()
    except Exception as e:
        print(f"Discovery: could not verify {league_url} – {e}")
        return False


def discover_new_competitions(driver):
    """Use an existing Selenium driver to scan rebelog.ie for new
    competitions involving Ballincollig across active age groups.

    Finds league links on the fixtures page whose link text matches
    an active age group pattern, then verifies Ballincollig is listed
    on the actual league page before reporting.

    Returns a list of dicts:
        [{"name": ..., "competition_id": ..., "url": ..., "age_group": ...}]
    """
    if not driver:
        return []

    found = []
    url = f"{REBELOG_BASE_URL}/fixtures/"

    try:
        print(f"Discovery: loading {url}")
        driver.get(url)
        time.sleep(3)

        # Find league links whose link text matches an active age group
        links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/league/"]')
        candidate_comps = {}  # id -> name
        for link in links:
            href = link.get_attribute("href") or ""
            m = re.search(r'/league/(\d+)', href)
            if not m:
                continue
            comp_id = int(m.group(1))
            comp_name = link.text.strip()
            if comp_name and _matches_any_age_group(comp_name):
                candidate_comps[comp_id] = comp_name

        # Filter to ones we don't already know, then verify Ballincollig
        # is actually listed in the competition before reporting it.
        for comp_id, comp_name in candidate_comps.items():
            if comp_id not in _KNOWN_IDS:
                comp_url = f"{REBELOG_BASE_URL}/league/{comp_id}/"
                if _club_in_competition(driver, comp_url):
                    found.append({
                        "name": comp_name,
                        "competition_id": comp_id,
                        "url": comp_url,
                        "age_group": _age_group_for_name(comp_name),
                    })
                else:
                    print(f"Discovery: skipping {comp_name} ({comp_id}) – "
                          f"{CLUB_NAME} not found on league page")

    except Exception as e:
        print(f"Discovery: error – {e}")

    if found:
        print(f"Discovery: found {len(found)} new competition(s)!")
        for f in found:
            print(f"  {f['name']} ({f.get('age_group', '?')}) -> {f['url']}")
    else:
        print("Discovery: no new competitions found")

    return found


def notify_new_competitions(new_comps):
    """Send a notification about newly discovered competitions.

    Groups by age group and sends to each relevant combined topic.
    """
    if not new_comps:
        return

    from competition_monitor.notifier import _send

    # Group by age group
    by_group = {}
    for c in new_comps:
        ag = c.get("age_group") or "unknown"
        by_group.setdefault(ag, []).append(c)

    for ag, comps in by_group.items():
        lines = []
        for c in comps:
            lines.append(f"- {c['name']}")
            lines.append(f"  ID: {c['competition_id']}")
            lines.append(f"  {c['url']}")

        # Send to the age-group combined topic
        topic = AGE_GROUPS.get(ag, {}).get("ntfy_combined_topic", NTFY_COMBINED_TOPIC)
        if not topic:
            topic = NTFY_COMBINED_TOPIC

        ag_label = ag.upper() if ag != "unknown" else ""
        _send(
            topic=topic,
            title=f"New {ag_label} Competition Found!".strip(),
            message=(
                f"New competition(s) with {CLUB_NAME} detected:\n\n"
                + "\n".join(lines)
                + "\n\nAdd to competition_monitor/config.py to start tracking."
            ),
            priority="high",
            action_url=comps[0]["url"],
        )
