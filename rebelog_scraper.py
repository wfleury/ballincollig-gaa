"""
Scraper for Rebel Og (rebelog.ie) competition fixtures.

Fetches fixtures from rebelog.ie league pages for competitions defined in
competition_monitor/config.py.  Only returns Ballincollig fixtures that
are NOT already present in the main gaacork.ie scrape (to avoid duplicates).

No Selenium needed — rebelog.ie embeds fixture data in the initial HTML
via SportLomo data-* attributes on <ul class="table-body"> elements.
"""

import re
import warnings

import requests
from bs4 import BeautifulSoup

from config import CLUB_NAME
from competition_monitor.config import COMPETITIONS, REBELOG_BASE_URL

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
}

SCORE_RE = re.compile(r'\d+-\d+\s*v\s*\d+-\d+')


def _fetch_league_page(competition_id):
    """Fetch a rebelog.ie league page and return parsed BeautifulSoup."""
    url = f"{REBELOG_BASE_URL}/league/{competition_id}/"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=30, verify=False)
        if resp.status_code != 200:
            return None
        return BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        print(f"  Rebelog: error fetching {url}: {e}")
        return None


def _parse_fixtures(soup, club_name):
    """Extract fixtures (not results) involving club_name from a parsed page.

    Returns list of fixture dicts matching the format used by
    selenium_scraper.py: {home, away, date, time, venue, competition, referee}.
    """
    fixtures = []
    for ul in soup.select('ul.table-body'):
        home = ul.get('data-hometeam', '')
        away = ul.get('data-awayteam', '')

        # Only include fixtures involving our club
        if club_name not in home and club_name not in away:
            continue

        # Skip results (have scores)
        home_score = ul.get('data-homescore', '').strip()
        away_score = ul.get('data-awayscore', '').strip()
        if home_score and away_score:
            continue

        # Also check text for scores (some results have scores in text only)
        text = ul.get_text(' ', strip=True)
        if SCORE_RE.search(text):
            continue

        date_str = ul.get('data-date', '')
        time_str = ul.get('data-time', '')

        # Skip postponed/cancelled (time 0:00 or 00:00)
        # These are kept as-is — enhanced_monitor.py handles postponed logic

        venue = ul.get('data-venue', '')
        comp = ul.get('data-compname', '')
        referee = ul.get('data-referee', '').strip()

        fixtures.append({
            'home': home,
            'away': away,
            'date': date_str,
            'time': time_str,
            'venue': venue,
            'competition': comp,
            'referee': referee,
        })

    return fixtures


def scrape_rebelog_fixtures():
    """Fetch fixtures from all tracked rebelog.ie competitions.

    Only returns Ballincollig fixtures that haven't been played yet
    (no score data).  The caller should deduplicate against fixtures
    already scraped from gaacork.ie.

    Returns list of fixture dicts.
    """
    all_fixtures = []
    comps_checked = 0

    for name, comp in COMPETITIONS.items():
        if comp.get('base_url') != REBELOG_BASE_URL:
            continue

        comp_id = comp['competition_id']
        soup = _fetch_league_page(comp_id)
        if not soup:
            continue

        comps_checked += 1
        fixtures = _parse_fixtures(soup, CLUB_NAME)
        if fixtures:
            for f in fixtures:
                print(f"  Rebelog: {f['date']} {f['home']} vs {f['away']} "
                      f"({name})")
            all_fixtures.extend(fixtures)

    print(f"Rebelog: checked {comps_checked} competitions, "
          f"found {len(all_fixtures)} fixtures")
    return all_fixtures


def deduplicate_fixtures(gaacork_fixtures, rebelog_fixtures):
    """Remove rebelog fixtures that already exist in the gaacork set.

    Matches on date + home/away teams (case-insensitive, stripped).
    Returns only the rebelog fixtures that are genuinely new.
    """
    if not rebelog_fixtures:
        return []

    # Build a set of keys from gaacork fixtures
    existing = set()
    for f in gaacork_fixtures:
        date = f.get('date', '').strip().lower()
        home = f.get('home', '').strip().lower()
        away = f.get('away', '').strip().lower()
        existing.add((date, home, away))
        # Also add with teams swapped (in case home/away is reversed)
        existing.add((date, away, home))

    new = []
    for f in rebelog_fixtures:
        date = f.get('date', '').strip().lower()
        home = f.get('home', '').strip().lower()
        away = f.get('away', '').strip().lower()
        key = (date, home, away)
        if key not in existing:
            new.append(f)
        else:
            print(f"  Rebelog: dedup - skipping {f['date']} "
                  f"{f['home']} vs {f['away']} (already in gaacork)")

    print(f"Rebelog: {len(new)} new fixtures after deduplication "
          f"({len(rebelog_fixtures) - len(new)} duplicates removed)")
    return new


if __name__ == "__main__":
    fixtures = scrape_rebelog_fixtures()
    print(f"\nTotal: {len(fixtures)} Ballincollig fixtures from rebelog.ie")
    for f in fixtures:
        print(f"  {f['date']} {f['time']} - {f['home']} vs {f['away']}")
        print(f"    Venue: {f['venue']}")
        print(f"    Comp: {f['competition']}")
