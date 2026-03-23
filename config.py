"""
Configuration for GAA Club Scraper
"""

import os
import re

# ---- Club identity ----
CLUB_NAME = "Ballincollig"
CLUB_ID = 1986
TEAM_ID = 327535
COMPETITION_ID = 211620
CLUBZAP_CLUB_ID = os.environ.get("CLUBZAP_CLUB_ID", "4975")

# ---- URLs ----
BASE_URL = "https://gaacork.ie/clubprofile/"
CLUBZAP_BASE_URL = "https://dashboard.clubzap.com"
CLUBZAP_FIXTURES_URL = f"{CLUBZAP_BASE_URL}/clubs/{CLUBZAP_CLUB_ID}/fixtures"

# ---- File paths ----
OUTPUT_DIR = "output"
CSV_FILENAME = "gaa_clubs.csv"
FIXTURES_CSV = "Ballincollig_Fixtures_Final.csv"
HASH_FILE = "fixture_hashes.json"
LOG_FILE = "monitoring_log.txt"
BASELINE_CSV = "clubzap_uploaded_baseline.csv"
NEW_CSV = "clubzap_new_fixtures.csv"
CHANGED_CSV = "clubzap_changed_fixtures.csv"
REMOVED_CSV = "clubzap_removed_fixtures.csv"

# ---- Notifications ----
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "ballincollig-gaa-fixtures")
NTFY_ICON = "https://sportlomo-userupload.s3.amazonaws.com/clubLogos/1986/ballincollig.gif"
NTFY_FIXTURES_URL = "https://ballincolliggaa.ie/fixtures"

# ClubZap website team IDs (for filtered fixture links in notifications)
CLUBZAP_TEAM_IDS = {
    "Senior Football": "20977",
    "Premier Inter Hurling": "21090",
    "Junior A Football": "21293",
    "Junior A Hurling": "21292",
    "Junior B Football": "21295",
    "Junior B Hurling": "21294",
    "Junior C Football": "21428",
    "Minor Football GAA": "20310",
    "Minor Hurling GAA": "20309",
    "U12 GAA": "20304",
    "U13 GAA": "20305",
    "U14 GAA": "20306",
    "U15 GAA": "20307",
    "U16 GAA": "20308",
    'GAA U21 "A" Football': "20191",
    'GAA U21 "A" Hurling': "24007",
    'GAA U21 "B" Football': "20192",
    'GAA U21 "B" Hurling': "24008",
}


def team_fixtures_url(team_name):
    """Return the public fixtures URL filtered to a specific team, or the
    unfiltered URL if the team is not recognised."""
    team_id = CLUBZAP_TEAM_IDS.get(team_name)
    if team_id:
        return f"{NTFY_FIXTURES_URL}?team_id={team_id}"
    return NTFY_FIXTURES_URL


def team_ntfy_topic(team_name):
    """Derive a per-team ntfy topic from the base topic and team name.

    e.g. "Senior Football" -> "ballincollig-gaa-fixtures-senior-football"
         "U14 GAA"         -> "ballincollig-gaa-fixtures-u14"
    """
    slug = re.sub(r'[^a-z0-9]+', '-', team_name.lower()).strip('-')
    # Drop redundant trailing "-gaa" for underage teams (U12–U16)
    slug = re.sub(r'^(u1[2-6])-gaa$', r'\1', slug)
    return f"{NTFY_TOPIC}-{slug}"

# ---- CSV schema ----
FIXTURE_HEADER = [
    "Date", "Time", "Venue", "Ground", "Referee",
    "Team", "Competition Name", "Your Club Name", "Opponent", "Event Type",
]

# Columns that form the unique key for a fixture
KEY_COLS = ["Date", "Team", "Opponent", "Competition Name"]

# Columns where changes matter for updates
CHANGE_COLS = ["Time", "Venue", "Ground", "Referee"]

# ---- Request settings ----
REQUEST_DELAY = 1  # seconds between requests
TIMEOUT = 10  # seconds

# ---- Data fields to extract (general club profile scraping) ----
FIELDS_TO_EXTRACT = [
    "club_name",
    "address",
    "website",
    "email",
    "division",
    "colors",
    "coordinates",
    "profile_url",
    "fixtures",
    "competition_name",
]

# ---- Filters ----
RUGBY_INDICATORS = ["rfc", "rugby", "rugbai", "munster bowl", "boys clubs"]
