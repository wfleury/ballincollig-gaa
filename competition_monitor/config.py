"""
Configuration for Competition Results Monitor.

Monitors full competition pages (all teams, fixtures, results, tables)
on rebelog.ie / gaacork.ie rather than a single club's profile page.
"""

import os
import re

# ---- Club identity ----
CLUB_NAME = "Ballincollig"

# ---- Base URLs ----
# Underage (Rebel Og) competitions live on rebelog.ie
REBELOG_BASE_URL = "https://rebelog.ie"
GAACORK_BASE_URL = "https://gaacork.ie"

# ---- Competitions to monitor ----
# Each entry maps a friendly name to its config.
# competition_id: the SportLomo league ID (used in /league/{id}/ URLs)
# base_url: which site hosts this competition
# ntfy_topic: per-competition ntfy topic name
COMPETITIONS = {
    # --- 1st team ---
    "Fe14 Premier 1 Football": {
        "competition_id": 213028,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u14-football",
    },
    "Fe14 Premier 2 Hurling": {
        "competition_id": 213159,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u14-hurling",
    },
    # --- 2nd team ---
    "Fe14 Div 1 Football (2nd team)": {
        "competition_id": 213068,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u14-football-2",
    },
    "Fe14 Div 4A Hurling (2nd team)": {
        "competition_id": 213625,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u14-hurling-2",
    },
    # --- 3rd team ---
    "Fe14 Div 4D Football (3rd team)": {
        "competition_id": 213624,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u14-football-3",
    },
}

# Override via env: comma-separated list of competition names to run
# e.g. COMP_NAMES="Fe14 Premier 1 Football"
COMP_NAMES_OVERRIDE = os.environ.get("COMP_NAMES")

# ---- Notifications ----
NTFY_ICON = "https://sportlomo-userupload.s3.amazonaws.com/clubLogos/1986/ballincollig.gif"
# Combined topic – subscribe to this one to get everything across all competitions
NTFY_COMBINED_TOPIC = "ballincollig-u14-results"

# ---- File paths ----
BASELINE_DIR = "competition_baselines"

# ---- Filters ----
RUGBY_INDICATORS = ["rfc", "rugby", "rugbai", "munster bowl", "boys clubs"]


def competition_url(comp):
    """Return the full URL for a competition page."""
    return f"{comp['base_url']}/league/{comp['competition_id']}/"


def get_active_competitions():
    """Return the competitions dict filtered by COMP_NAMES env override."""
    if COMP_NAMES_OVERRIDE:
        names = [n.strip() for n in COMP_NAMES_OVERRIDE.split(",")]
        return {k: v for k, v in COMPETITIONS.items() if k in names}
    return dict(COMPETITIONS)
