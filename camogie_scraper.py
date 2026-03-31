"""
Scraper for Cork Camogie league fixtures from corkcamogie.com.

The site embeds Foireann (GAA management system) widgets as static HTML
inside WordPress pages.  Each fixture is an <article class="foireann-card">
containing round, date/time, team names, scores, division, and venue.

No Selenium is needed — plain HTTP requests + regex extraction.
"""

import re
import warnings
from datetime import datetime
from html import unescape

import requests

from config import CAMOGIE_LEAGUES, CLUB_NAME

# Suppress only the InsecureRequestWarning from urllib3 (corkcamogie.com cert)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# ── HTML parsing helpers ────────────────────────────────────────────────


def _extract_text(pattern, html, default=""):
    """Return first regex capture group, stripped & unescaped, or *default*."""
    m = re.search(pattern, html, re.DOTALL)
    return unescape(m.group(1).strip()) if m else default


def _parse_datetime(raw):
    """Parse a Foireann date string like 'Mon 30 Mar 2026 6:00 pm'.

    Returns (date_str, time_str) in the formats used by the GAA Cork
    scraper: date = '30 Mar 2026', time = '18:00'.
    """
    raw = raw.strip()
    # Try the standard Foireann format: "Day DD Mon YYYY H:MM am/pm"
    for fmt in (
        "%a %d %b %Y %I:%M %p",   # Mon 30 Mar 2026 6:00 pm
        "%a %d %b %Y %I:%M%p",    # Mon 30 Mar 2026 6:00pm
        "%d %b %Y %I:%M %p",      # 30 Mar 2026 6:00 pm
    ):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%d %b %Y"), dt.strftime("%H:%M")
        except ValueError:
            continue
    # Fallback: return the raw string as date, empty time
    return raw, ""


def parse_fixture_cards(html, club_name):
    """Parse all Foireann fixture cards from *html*.

    Returns a list of fixture dicts for matches involving *club_name*.
    Each dict has the same keys as the GAA Cork selenium scraper output:
        home, away, date, time, venue, competition, referee
    """
    fixtures = []
    cards = re.split(r"<article\s+class=\"foireann-card\">", html)
    for card in cards[1:]:  # first chunk is before the first card
        date_raw = _extract_text(r'foireann-card-date[^>]*>([^<]*)<', card)
        if not date_raw:
            continue
        date_str, time_str = _parse_datetime(date_raw)

        teams = re.findall(r'foireann-team-name[^>]*>([^<]*)<', card)
        home = teams[0].strip() if len(teams) > 0 else ""
        away = teams[1].strip() if len(teams) > 1 else ""

        # Only keep fixtures involving our club
        if club_name.lower() not in home.lower() and club_name.lower() not in away.lower():
            continue

        division = _extract_text(r"Division:</strong>\s*([^<]*)<", card)
        venue = _extract_text(r"Venue:</strong>\s*([^<]*)<", card)

        # Skip duplicate results cards (same fixture appears once as upcoming,
        # once with scores when played).  We detect results by score badges.
        scores = re.findall(r'foireann-score-badge[^>]*>([^<]*)<', card)
        has_score = any(s.strip() for s in scores)

        fixtures.append({
            "home": home,
            "away": away,
            "date": date_str,
            "time": time_str,
            "venue": venue,
            "competition": division,
            "referee": "",
            "_has_score": has_score,
        })

    return fixtures


def scrape_camogie_fixtures(leagues=None):
    """Scrape all configured camogie league pages and return fixture dicts.

    Each returned dict has the standard keys (home, away, date, time, venue,
    competition, referee) plus 'team' (the pre-mapped ClubZap team name).

    Parameters
    ----------
    leagues : list[dict] | None
        Override the league list from config (useful for testing).
    """
    if leagues is None:
        leagues = CAMOGIE_LEAGUES

    all_fixtures = []
    seen = set()  # de-duplicate across fixture/result cards

    for league in leagues:
        url = league["url"]
        team_name = league["team"]
        club_name = league["club_name"]
        competition = league.get("competition", "")

        try:
            resp = requests.get(url, headers=_HEADERS, timeout=20, verify=False)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"WARNING: Could not fetch {url}: {e}")
            continue

        cards = parse_fixture_cards(resp.text, club_name)
        print(f"Camogie: {len(cards)} fixtures for {club_name} from {url}")

        for fx in cards:
            # De-duplicate: fixture cards sometimes appear twice (once as
            # upcoming, once with scores).  Keep the most informative one.
            key = (fx["date"], fx["home"].lower(), fx["away"].lower())
            if key in seen:
                continue
            seen.add(key)

            # Use the friendly competition name from config if available
            if competition:
                fx["competition"] = competition

            fx["team"] = team_name
            all_fixtures.append(fx)

    # Strip internal helper keys
    for fx in all_fixtures:
        fx.pop("_has_score", None)

    print(f"Camogie: {len(all_fixtures)} total fixtures across {len(leagues)} leagues")
    return all_fixtures


# ── Standalone test ─────────────────────────────────────────────────────

if __name__ == "__main__":
    fixtures = scrape_camogie_fixtures()
    for fx in fixtures:
        print(
            f"  {fx['date']} {fx['time']} | "
            f"{fx['home']} vs {fx['away']} | "
            f"{fx.get('team', '?')} | {fx['competition']}"
        )
