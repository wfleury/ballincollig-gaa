"""
Auto-discovery of new underage competitions involving Ballincollig.

Three discovery methods (each additive, run in order):

1. **Dropdown scan** (HTTP) — parse the competition dropdown on
   rebelog.ie/fixtures/ for options matching active age-group patterns.
   Fast, no Selenium needed, catches most new competitions.

2. **Fixture-link scan** (Selenium) — find league links in the rendered
   fixtures page.  Catches competitions visible as upcoming fixtures.

3. **Sequential ID probe** (HTTP) — check IDs above the highest known
   competition ID.  Catches competitions not listed on the fixtures
   page at all (e.g. play-offs created at the last minute).

All methods verify Ballincollig is on the league page before reporting.
"""

import re
import time
import warnings
from html import unescape

import requests
from selenium.webdriver.common.by import By

from competition_monitor.config import (
    AGE_GROUPS, CLUB_NAME, COMPETITIONS, NTFY_COMBINED_TOPIC,
    REBELOG_BASE_URL, get_active_age_groups,
)

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
}

# All competition IDs we already monitor
_KNOWN_IDS = {c["competition_id"] for c in COMPETITIONS.values()}

# How many IDs above the highest known to probe
_PROBE_RANGE = 50


def _active_discovery_patterns():
    """Return discovery patterns for the currently active age groups only."""
    return {
        ag["discovery_pattern"].lower()
        for ag in get_active_age_groups().values()
        if "discovery_pattern" in ag
    }


def _normalise_age_label(name):
    """Normalise age-group labels: 'Fé 14' / 'Fe 14' / 'Fé14' -> 'fe14'.

    Accent removal must happen *before* space removal so that
    'fé 14' becomes 'fe 14' first, then the regex collapses the space.
    """
    lower = name.lower()
    # Step 1: strip accented é -> e (must be first so regex word-boundary works)
    lower = lower.replace('\xe9', 'e')
    # Step 2: collapse 'fe 14' -> 'fe14'
    return re.sub(r'\bfe\s+(\d)', r'fe\1', lower)


def _matches_any_age_group(name):
    """Return True if the competition name matches any active age group.

    Normalises 'Fe 14' -> 'Fe14' and 'Fé14' -> 'Fe14' so patterns match.
    """
    normalised = _normalise_age_label(name)
    return any(pat in normalised for pat in _active_discovery_patterns())


def _age_group_for_name(name):
    """Return the AGE_GROUPS key for a competition name, or None."""
    normalised = _normalise_age_label(name)
    for key, ag in AGE_GROUPS.items():
        pat = ag.get("discovery_pattern", "").lower()
        if pat and pat in normalised:
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


def _club_in_competition_http(comp_id):
    """Check whether CLUB_NAME appears on a league page via HTTP.

    Returns (True/False, competition_name) — name extracted from page title.
    """
    url = f"{REBELOG_BASE_URL}/league/{comp_id}/"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15, verify=False)
        if resp.status_code != 200:
            return False, ""
        html = resp.text
        has_club = CLUB_NAME.lower() in html.lower()
        # Extract competition name from page heading
        m = re.search(r'<h2[^>]*>([^<]+)</h2>', html)
        if not m:
            m = re.search(r'League Table\s+(.+?)(?:<|$)', html)
        name = unescape(m.group(1).strip()) if m else ""
        return has_club, name
    except Exception:
        return False, ""


def _discover_from_dropdown():
    """Scan the competition dropdown on rebelog.ie/fixtures/ via HTTP.

    Returns dict of {comp_id: comp_name} for unknown competitions
    matching active age groups.
    """
    candidates = {}
    url = f"{REBELOG_BASE_URL}/fixtures/"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=30, verify=False)
        if resp.status_code != 200:
            print(f"Discovery dropdown: HTTP {resp.status_code}")
            return candidates

        # Parse <option value="12345">Competition Name</option>
        for m in re.finditer(
            r'<option[^>]*value=["\']?(\d+)["\']?[^>]*>([^<]+)</option>',
            resp.text,
        ):
            comp_id = int(m.group(1))
            comp_name = unescape(m.group(2).strip())
            if comp_id not in _KNOWN_IDS and _matches_any_age_group(comp_name):
                candidates[comp_id] = comp_name

    except Exception as e:
        print(f"Discovery dropdown: error – {e}")

    print(f"Discovery dropdown: {len(candidates)} unknown candidates")
    return candidates


def _discover_by_probing():
    """Probe sequential IDs above the highest known competition ID.

    Catches competitions not listed on the fixtures page (e.g. play-offs
    created at the last minute that aren't in the dropdown).

    Returns dict of {comp_id: comp_name} for competitions involving
    Ballincollig that match active age groups.
    """
    candidates = {}
    max_known = max(_KNOWN_IDS) if _KNOWN_IDS else 0
    start = max_known + 1
    end = max_known + _PROBE_RANGE

    print(f"Discovery probe: checking IDs {start}–{end}")
    for comp_id in range(start, end + 1):
        if comp_id in _KNOWN_IDS:
            continue
        has_club, name = _club_in_competition_http(comp_id)
        if has_club and name and _matches_any_age_group(name):
            candidates[comp_id] = name
            print(f"  Probe hit: {comp_id} -> {name}")

    print(f"Discovery probe: {len(candidates)} new competitions found")
    return candidates


def discover_new_competitions(driver):
    """Scan rebelog.ie for new competitions involving Ballincollig.

    Uses three methods:
    1. Dropdown scan (HTTP) — fast, covers most competitions
    2. Fixture-link scan (Selenium) — catches visible fixture links
    3. Sequential ID probe (HTTP) — catches unlisted competitions

    Returns a list of dicts:
        [{"name": ..., "competition_id": ..., "url": ..., "age_group": ...}]
    """
    all_candidates = {}  # comp_id -> comp_name

    # Method 1: Dropdown scan (HTTP, no Selenium needed)
    try:
        all_candidates.update(_discover_from_dropdown())
    except Exception as e:
        print(f"Discovery: dropdown scan error – {e}")

    # Method 2: Fixture-link scan (Selenium)
    if driver:
        try:
            url = f"{REBELOG_BASE_URL}/fixtures/"
            print(f"Discovery: loading {url}")
            driver.get(url)
            time.sleep(3)

            links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/league/"]')
            for link in links:
                href = link.get_attribute("href") or ""
                m = re.search(r'/league/(\d+)', href)
                if not m:
                    continue
                comp_id = int(m.group(1))
                comp_name = link.text.strip()
                if (comp_id not in _KNOWN_IDS
                        and comp_id not in all_candidates
                        and comp_name
                        and _matches_any_age_group(comp_name)):
                    all_candidates[comp_id] = comp_name

        except Exception as e:
            print(f"Discovery: fixture-link scan error – {e}")

    # Method 3: Sequential ID probe (HTTP)
    try:
        all_candidates.update(_discover_by_probing())
    except Exception as e:
        print(f"Discovery: probe error – {e}")

    # Verify Ballincollig is in each candidate competition
    found = []
    for comp_id, comp_name in all_candidates.items():
        comp_url = f"{REBELOG_BASE_URL}/league/{comp_id}/"
        # Use HTTP verification (faster, no Selenium needed)
        has_club, page_name = _club_in_competition_http(comp_id)
        if has_club:
            # Prefer the page name if the dropdown name was HTML-encoded
            display_name = page_name or comp_name
            found.append({
                "name": display_name,
                "competition_id": comp_id,
                "url": comp_url,
                "age_group": _age_group_for_name(display_name),
            })
        else:
            print(f"Discovery: skipping {comp_name} ({comp_id}) – "
                  f"{CLUB_NAME} not found on league page")

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
