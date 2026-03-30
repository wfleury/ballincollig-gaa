"""
Baseline persistence and change detection for competition results.

Stores a JSON file per competition in BASELINE_DIR with the last-known
fixtures, results, and table hash.  On each run, computes a diff of
new results, fixture changes, and table movements.
"""

import hashlib
import json
import os
from datetime import datetime

from competition_monitor.config import BASELINE_DIR, CLUB_NAME


def _match_key(m):
    """Stable key for a match: date|home|away (lowercased)."""
    return f"{m['date']}|{m['home'].lower()}|{m['away'].lower()}"


def _table_hash(table):
    """SHA-256 of the serialised table for quick equality check."""
    raw = json.dumps(table, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def _is_our_match(m):
    """True if CLUB_NAME is one of the teams."""
    name = CLUB_NAME.lower()
    return name in m.get("home", "").lower() or name in m.get("away", "").lower()


def _our_position(table):
    """Return our position and points from the table, or None."""
    for row in table:
        if CLUB_NAME.lower() in row.get("team", "").lower():
            return row
    return None


# ------------------------------------------------------------------
# Baseline I/O
# ------------------------------------------------------------------

def _baseline_path(comp_name):
    os.makedirs(BASELINE_DIR, exist_ok=True)
    safe = comp_name.lower().replace(" ", "_").replace("/", "_")
    return os.path.join(BASELINE_DIR, f"{safe}.json")


def load_baseline(comp_name):
    """Load the previous baseline for a competition.  Returns dict or None."""
    path = _baseline_path(comp_name)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return None


def save_baseline(comp_name, data):
    """Persist the current scrape as the new baseline."""
    path = _baseline_path(comp_name)
    baseline = {
        "last_run": datetime.now().isoformat(),
        "results": {_match_key(r): r for r in data.get("results", [])},
        "fixtures": {_match_key(f): f for f in data.get("fixtures", [])},
        "table": data.get("table", []),
        "table_hash": _table_hash(data.get("table", [])),
        "competition_name": data.get("competition_name", ""),
    }
    with open(path, "w") as f:
        json.dump(baseline, f, indent=2)


# ------------------------------------------------------------------
# Diff logic
# ------------------------------------------------------------------

def compute_diff(comp_name, current_data):
    """Compare current scrape against saved baseline.

    Returns a dict:
        first_run         – True if no baseline existed
        new_results       – list of matches that now have scores
        our_new_results   – subset involving CLUB_NAME
        fixture_changes   – list of (match, changes_description)
        new_fixtures      – matches in current but not baseline
        removed_fixtures  – matches in baseline but not current
        table_changed     – bool
        our_standing      – dict with position/team/pts or None
        table             – full table list
        result_count      – total results
        fixture_count     – total upcoming fixtures
    """
    baseline = load_baseline(comp_name)

    diff = {
        "first_run": baseline is None,
        "new_results": [],
        "our_new_results": [],
        "fixture_changes": [],
        "new_fixtures": [],
        "removed_fixtures": [],
        "table_changed": False,
        "our_standing": _our_position(current_data.get("table", [])),
        "table": current_data.get("table", []),
        "result_count": len(current_data.get("results", [])),
        "fixture_count": len(current_data.get("fixtures", [])),
    }

    if baseline is None:
        return diff

    old_results = baseline.get("results", {})
    old_fixtures = baseline.get("fixtures", {})

    # ---- New results (match key present in current results but not old) ----
    for r in current_data.get("results", []):
        key = _match_key(r)
        if key not in old_results:
            diff["new_results"].append(r)
            if _is_our_match(r):
                diff["our_new_results"].append(r)

    # ---- Fixture changes ----
    cur_fixtures = {_match_key(f): f for f in current_data.get("fixtures", [])}

    for key, cur in cur_fixtures.items():
        if key in old_fixtures:
            old = old_fixtures[key]
            changes = []
            for col in ("time", "venue", "date"):
                old_val = old.get(col, "").strip()
                new_val = cur.get(col, "").strip()
                if old_val != new_val:
                    changes.append(f"{col.title()}: {old_val} -> {new_val}")
            if cur.get("postponed") and not old.get("postponed"):
                changes.append("POSTPONED")
            if changes:
                diff["fixture_changes"].append((cur, changes))
        elif key not in old_results:
            # Genuinely new fixture (not one that just got a result)
            diff["new_fixtures"].append(cur)

    for key, old in old_fixtures.items():
        rk = _match_key(old)
        if rk not in cur_fixtures and rk not in {
            _match_key(r) for r in current_data.get("results", [])
        }:
            diff["removed_fixtures"].append(old)

    # ---- Table ----
    old_hash = baseline.get("table_hash", "")
    new_hash = _table_hash(current_data.get("table", []))
    diff["table_changed"] = old_hash != new_hash

    return diff


def has_changes(diff):
    """Return True if the diff contains any actionable changes."""
    if diff.get("first_run"):
        return True
    return bool(
        diff.get("new_results")
        or diff.get("fixture_changes")
        or diff.get("new_fixtures")
        or diff.get("removed_fixtures")
        or diff.get("table_changed")
    )
