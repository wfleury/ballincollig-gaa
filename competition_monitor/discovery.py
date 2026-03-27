"""
Auto-discovery of new Fe14 competitions involving Ballincollig.

Scrapes the rebelog.ie fixtures page for any Fe14 competition that
includes Ballincollig but isn't already in our config.  When a new
competition appears (e.g. championship), sends a notification so the
user knows to add it.
"""

import re
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from competition_monitor.config import (
    CLUB_NAME, COMPETITIONS, NTFY_COMBINED_TOPIC, REBELOG_BASE_URL,
)


# All competition IDs we already monitor
_KNOWN_IDS = {c["competition_id"] for c in COMPETITIONS.values()}


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
    Fe14 competitions involving Ballincollig.

    Returns a list of dicts: [{"name": ..., "competition_id": ..., "url": ...}]
    """
    if not driver:
        return []

    found = []
    url = f"{REBELOG_BASE_URL}/fixtures/"

    try:
        print(f"Discovery: loading {url}")
        driver.get(url)
        time.sleep(3)

        # Wait for fixture elements
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, 'ul[data-date]'))
            )
        except TimeoutException:
            print("Discovery: no fixture elements found, trying links approach")

        # Approach 1: look for competition links with Fe14 + Ballincollig nearby
        # The fixtures page lists competitions as headings with links to /league/{id}/
        page_source = driver.page_source

        # Find all league links
        league_pattern = re.compile(
            r'href=["\'](?:https?://rebelog\.ie)?/league/(\d+)/?["\'][^>]*>([^<]+)<',
            re.IGNORECASE,
        )
        # Also grab data attributes from fixture elements
        comp_pattern = re.compile(
            r'data-compname="([^"]*fe14[^"]*)"',
            re.IGNORECASE,
        )
        # Collect all Fe14 competition IDs from league links
        fe14_comps = {}  # id -> name
        for m in league_pattern.finditer(page_source):
            comp_id = int(m.group(1))
            comp_name = m.group(2).strip()
            if 'fe14' in comp_name.lower() or 'fé14' in comp_name.lower():
                fe14_comps[comp_id] = comp_name

        # Also check data-compname attributes
        for m in comp_pattern.finditer(page_source):
            comp_name = m.group(1)
            # Try to find a league link for this competition
            link_match = re.search(
                r'href=["\'](?:https?://rebelog\.ie)?/league/(\d+)/?["\']',
                page_source[:m.start()][-2000:],  # search nearby
            )
            if link_match:
                fe14_comps[int(link_match.group(1))] = comp_name

        # Filter to ones we don't already know, then verify Ballincollig
        # is actually listed in the competition before reporting it.
        for comp_id, comp_name in fe14_comps.items():
            if comp_id not in _KNOWN_IDS:
                comp_url = f"{REBELOG_BASE_URL}/league/{comp_id}/"
                if _club_in_competition(driver, comp_url):
                    found.append({
                        "name": comp_name,
                        "competition_id": comp_id,
                        "url": comp_url,
                    })
                else:
                    print(f"Discovery: skipping {comp_name} ({comp_id}) – "
                          f"{CLUB_NAME} not found on league page")

        # Approach 2: scan fixture elements directly
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, 'ul[data-date]')
            for el in elements:
                comp_name = el.get_attribute('data-compname') or ''
                if 'fe14' not in comp_name.lower() and 'fé14' not in comp_name.lower():
                    continue

                home = el.get_attribute('data-hometeam') or ''
                away = el.get_attribute('data-awayteam') or ''
                if CLUB_NAME.lower() not in home.lower() and CLUB_NAME.lower() not in away.lower():
                    continue

                # Try to find the competition ID from a nearby link
                # Use JS to find the nearest league link
                try:
                    comp_id = driver.execute_script("""
                        var el = arguments[0];
                        var parent = el.closest('.fixture-group, .competition-fixtures, section, div');
                        if (!parent) parent = el.parentElement;
                        var link = parent ? parent.querySelector('a[href*="/league/"]') : null;
                        if (link) {
                            var match = link.href.match(/\\/league\\/(\\d+)/);
                            return match ? parseInt(match[1]) : null;
                        }
                        return null;
                    """, el)
                    if comp_id and comp_id not in _KNOWN_IDS:
                        # Avoid duplicates
                        if not any(f["competition_id"] == comp_id for f in found):
                            found.append({
                                "name": comp_name,
                                "competition_id": comp_id,
                                "url": f"{REBELOG_BASE_URL}/league/{comp_id}/",
                            })
                except Exception:
                    pass
        except Exception as e:
            print(f"Discovery: element scan failed – {e}")

    except Exception as e:
        print(f"Discovery: error – {e}")

    if found:
        print(f"Discovery: found {len(found)} new Fe14 competition(s)!")
        for f in found:
            print(f"  {f['name']} -> {f['url']}")
    else:
        print("Discovery: no new Fe14 competitions found")

    return found


def notify_new_competitions(new_comps):
    """Send a notification about newly discovered competitions."""
    if not new_comps or not NTFY_COMBINED_TOPIC:
        return

    from competition_monitor.notifier import _send

    lines = []
    for c in new_comps:
        lines.append(f"- {c['name']}")
        lines.append(f"  ID: {c['competition_id']}")
        lines.append(f"  {c['url']}")

    _send(
        topic=NTFY_COMBINED_TOPIC,
        title="New Fe14 Competition Found!",
        message=(
            "New competition(s) with Ballincollig detected:\n\n"
            + "\n".join(lines)
            + "\n\nAdd to competition_monitor/config.py to start tracking."
        ),
        priority="high",
        action_url=new_comps[0]["url"],
    )
