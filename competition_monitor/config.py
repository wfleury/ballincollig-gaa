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

# ---- Age groups ----
# Each age group has a combined ntfy topic and a pattern used by discovery.
AGE_GROUPS = {
    "u13": {
        "ntfy_combined_topic": "ballincollig-u13-results",
        "discovery_pattern": "fe13",
    },
    "u14": {
        "ntfy_combined_topic": "ballincollig-u14-results",
        "discovery_pattern": "fe14",
    },
    "u15": {
        "ntfy_combined_topic": "ballincollig-u15-results",
        "discovery_pattern": "fe15",
    },
    "u16": {
        "ntfy_combined_topic": "ballincollig-u16-results",
        "discovery_pattern": "fe16",
    },
    "minor": {
        "ntfy_combined_topic": "ballincollig-minor-results",
        "discovery_pattern": "fe18",
    },
}

# ---- Competitions to monitor ----
# Each entry maps a friendly name to its config.
# competition_id: the SportLomo league ID (used in /league/{id}/ URLs)
# base_url: which site hosts this competition
# ntfy_topic: per-competition ntfy topic name
# age_group: key into AGE_GROUPS (determines combined topic + discovery)
COMPETITIONS = {
    # ===== U13 (Fe13) =====
    # --- 1st team ---
    "Fe13 Football Grp 1B": {
        "competition_id": 214370,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u13-football",
        "age_group": "u13",
    },
    "Fe13 Hurling Grp 1B": {
        "competition_id": 214382,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u13-hurling",
        "age_group": "u13",
    },
    # --- 2nd team ---
    "Fe13 Football Grp 4B (2nd team)": {
        "competition_id": 214379,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u13-football-2",
        "age_group": "u13",
    },
    "Fe13 Hurling Grp 4A (2nd team)": {
        "competition_id": 214447,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u13-hurling-2",
        "age_group": "u13",
    },
    # --- 3rd team ---
    "Fe13 Football Grp 4C (3rd team)": {
        "competition_id": 214380,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u13-football-3",
        "age_group": "u13",
    },

    # ===== U14 (Fe14) =====
    # --- 1st team ---
    "Fe14 Premier 1 Football": {
        "competition_id": 213028,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u14-football",
        "age_group": "u14",
    },
    "Fe14 Premier 2 Hurling": {
        "competition_id": 213159,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u14-hurling",
        "age_group": "u14",
    },
    # --- 1st team championship ---
    "Fe14 Premier 1 S1 Football Championship": {
        "competition_id": 214876,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u14-football",
        "age_group": "u14",
    },
    "Fe14 Premier 2 S1 Hurling Championship": {
        "competition_id": 214883,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u14-hurling",
        "age_group": "u14",
    },
    # --- 2nd team ---
    "Fe14 Div 1 Football (2nd team)": {
        "competition_id": 213068,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u14-football-2",
        "age_group": "u14",
    },
    "Fe14 Div 4A Hurling (2nd team)": {
        "competition_id": 213625,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u14-hurling-2",
        "age_group": "u14",
    },
    # --- 2nd team championship ---
    "Fe14 Div 1 S-A S2 Football Championship (2nd team)": {
        "competition_id": 214897,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u14-football-2",
        "age_group": "u14",
    },
    # --- 3rd team ---
    "Fe14 Div 4D Football (3rd team)": {
        "competition_id": 213624,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u14-football-3",
        "age_group": "u14",
    },

    # ===== U15 (Fe15) =====
    "Fe15 Football Grp 1": {
        "competition_id": 214358,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u15-football",
        "age_group": "u15",
    },
    "Fe15 Hurling Grp 1": {
        "competition_id": 214364,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u15-hurling",
        "age_group": "u15",
    },

    # ===== U16 (Fe16) =====
    # --- 1st team ---
    "Fe16 Premier 1 Football": {
        "competition_id": 213023,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u16-football",
        "age_group": "u16",
    },
    "Fe16 Premier 1 Hurling": {
        "competition_id": 213154,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u16-hurling",
        "age_group": "u16",
    },
    # --- 2nd team ---
    "Fe16 Div 1 S2 Football (2nd team)": {
        "competition_id": 213064,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u16-football-2",
        "age_group": "u16",
    },
    "Fe16 Div 1 S2 Hurling (2nd team)": {
        "competition_id": 213165,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-u16-hurling-2",
        "age_group": "u16",
    },

    # ===== Minor (Fe18) =====
    # --- 1st team ---
    "Fe18 Premier 1 Football": {
        "competition_id": 213019,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-minor-football",
        "age_group": "minor",
    },
    "Fe18 Premier 1 Hurling": {
        "competition_id": 213151,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-minor-hurling",
        "age_group": "minor",
    },
    # --- 2nd team ---
    "Fe18 Div 4A Hurling (2nd team)": {
        "competition_id": 213611,
        "base_url": REBELOG_BASE_URL,
        "ntfy_topic": "ballincollig-minor-hurling-2",
        "age_group": "minor",
    },
}

# Override via env: comma-separated list of competition names to run
# e.g. COMP_NAMES="Fe14 Premier 1 Football"
COMP_NAMES_OVERRIDE = os.environ.get("COMP_NAMES")

# Override via env: comma-separated list of age groups to run
# e.g. COMP_AGE_GROUPS="u14,u16"
COMP_AGE_GROUPS_OVERRIDE = os.environ.get("COMP_AGE_GROUPS")

# ---- Notifications ----
NTFY_ICON = "https://sportlomo-userupload.s3.amazonaws.com/clubLogos/1986/ballincollig.gif"
# Legacy combined topic (kept for backwards compat, U14 only)
NTFY_COMBINED_TOPIC = "ballincollig-u14-results"

# ---- Dashboard ----
DASHBOARD_BASE_URL = "https://wfleury.github.io/ballincollig-gaa"

# ---- File paths ----
BASELINE_DIR = "competition_baselines"

# ---- Filters ----
RUGBY_INDICATORS = ["rfc", "rugby", "rugbai", "munster bowl", "boys clubs"]


def competition_url(comp):
    """Return the full URL for a competition page."""
    return f"{comp['base_url']}/league/{comp['competition_id']}/"


def dashboard_url(comp):
    """Return the GitHub Pages dashboard URL for this competition's age group, or None."""
    ag = comp.get("age_group", "")
    if ag and DASHBOARD_BASE_URL:
        return f"{DASHBOARD_BASE_URL}/{ag}/"
    return None


def combined_topic_for(comp):
    """Return the age-group combined ntfy topic for a competition."""
    ag = comp.get("age_group", "")
    group = AGE_GROUPS.get(ag)
    if group:
        return group["ntfy_combined_topic"]
    return NTFY_COMBINED_TOPIC


def get_active_competitions():
    """Return the competitions dict filtered by COMP_NAMES or COMP_AGE_GROUPS env overrides."""
    result = dict(COMPETITIONS)
    if COMP_NAMES_OVERRIDE:
        names = [n.strip() for n in COMP_NAMES_OVERRIDE.split(",")]
        result = {k: v for k, v in result.items() if k in names}
    if COMP_AGE_GROUPS_OVERRIDE:
        groups = [g.strip() for g in COMP_AGE_GROUPS_OVERRIDE.split(",")]
        result = {k: v for k, v in result.items() if v.get("age_group") in groups}
    return result


def get_active_age_groups():
    """Return the AGE_GROUPS dict filtered by COMP_AGE_GROUPS env override."""
    if COMP_AGE_GROUPS_OVERRIDE:
        groups = [g.strip() for g in COMP_AGE_GROUPS_OVERRIDE.split(",")]
        return {k: v for k, v in AGE_GROUPS.items() if k in groups}
    return dict(AGE_GROUPS)
