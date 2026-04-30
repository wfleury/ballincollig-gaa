"""
Baseline persistence and change detection for competition results.

Stores a JSON file per competition in BASELINE_DIR with the last-known
fixtures, results, and table hash.  On each run, computes a diff of
new results, fixture changes, and table movements.
"""

import hashlib
import json
import os
import shutil
from datetime import datetime

from competition_monitor.config import BASELINE_DIR, CLUB_NAME


# ------------------------------------------------------------------
# Schema validation
# ------------------------------------------------------------------

# Required top-level keys for a saved baseline.
_REQUIRED_BASELINE_KEYS = {
    "last_run", "results", "fixtures", "table", "table_hash",
}

# Required keys for a match (fixture or result).
_REQUIRED_MATCH_KEYS = {"home", "away", "date"}


class BaselineValidationError(ValueError):
    """Raised when a baseline fails schema validation."""


def _validate_match(m, kind):
    """Validate a single match dict. Returns list of error strings."""
    errors = []
    if not isinstance(m, dict):
        return [f"{kind}: not a dict ({type(m).__name__})"]
    for key in _REQUIRED_MATCH_KEYS:
        if not m.get(key):
            errors.append(f"{kind} missing '{key}'")
    if kind == "result":
        # Results must have scores in the GAA format "X-Y" OR be conceded
        is_conceded = m.get("conceded", False)
        if not is_conceded:
            for k in ("home_score", "away_score"):
                v = m.get(k, "")
                if not isinstance(v, str) or "-" not in v:
                    errors.append(f"result bad {k}: {v!r}")
    return errors


def _validate_table(table):
    errors = []
    if not isinstance(table, list):
        return [f"table: not a list ({type(table).__name__})"]
    for row in table:
        if not isinstance(row, dict):
            errors.append("table row not a dict")
            continue
        if "team" not in row:
            errors.append("table row missing 'team'")
    return errors


def validate_baseline(baseline):
    """Validate a baseline dict and return a list of error strings.

    An empty list means the baseline is valid.
    """
    errors = []
    if not isinstance(baseline, dict):
        return [f"baseline not a dict ({type(baseline).__name__})"]

    for key in _REQUIRED_BASELINE_KEYS:
        if key not in baseline:
            errors.append(f"missing top-level key '{key}'")

    for key in ("results", "fixtures"):
        section = baseline.get(key, {})
        if not isinstance(section, dict):
            errors.append(f"{key}: not a dict")
            continue
        for mkey, m in section.items():
            errors.extend(_validate_match(
                m, "result" if key == "results" else "fixture"))

    errors.extend(_validate_table(baseline.get("table", [])))
    return errors


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


def save_baseline(comp_name, data, strict=False):
    """Persist the current scrape as the new baseline.

    Before overwriting, the existing baseline (if any) is backed up to
    ``<name>.prev.json`` so a corrupt scrape can be rolled back.

    Args:
        comp_name: competition name.
        data: scraped payload with keys results/fixtures/table.
        strict: if True, raise BaselineValidationError when the new
            baseline fails validation; otherwise log & skip save.

    Returns:
        True if saved, False if skipped due to validation failure.
    """
    path = _baseline_path(comp_name)
    baseline = {
        "last_run": datetime.now().isoformat(),
        "results": {_match_key(r): r for r in data.get("results", [])},
        "fixtures": {_match_key(f): f for f in data.get("fixtures", [])},
        "table": data.get("table", []),
        "table_hash": _table_hash(data.get("table", [])),
        "competition_name": data.get("competition_name", ""),
    }

    errors = validate_baseline(baseline)
    if errors:
        msg = f"Baseline validation failed for {comp_name}: {'; '.join(errors[:5])}"
        if strict:
            raise BaselineValidationError(msg)
        print(f"WARN: {msg} — skipping save")
        return False

    # Safety: refuse to wipe a healthy baseline with a drastically
    # smaller one (likely a scrape failure). A 50% drop in results
    # or table rows triggers the guard.
    prev = load_baseline(comp_name)
    if prev and _looks_like_regression(prev, baseline):
        print(f"WARN: {comp_name} new baseline looks like regression — "
              f"keeping previous. "
              f"prev results={len(prev.get('results', {}))} "
              f"new={len(baseline['results'])}, "
              f"prev table={len(prev.get('table', []))} "
              f"new={len(baseline['table'])}")
        return False

    # Rollback copy of the current baseline before overwriting.
    if os.path.exists(path):
        try:
            shutil.copy2(path, path + ".prev")
        except OSError:
            pass

    with open(path, "w") as f:
        json.dump(baseline, f, indent=2)
    return True


def _looks_like_regression(prev, new):
    """Detect a scrape regression that would wipe out data."""
    prev_res = len(prev.get("results", {}))
    new_res = len(new.get("results", {}))
    if prev_res >= 4 and new_res < prev_res // 2:
        return True
    prev_tbl = len(prev.get("table", []))
    new_tbl = len(new.get("table", []))
    if prev_tbl >= 4 and new_tbl < prev_tbl // 2:
        return True
    return False


def rollback_baseline(comp_name):
    """Restore the previous baseline from <name>.prev if available."""
    path = _baseline_path(comp_name)
    prev_path = path + ".prev"
    if not os.path.exists(prev_path):
        return False
    shutil.copy2(prev_path, path)
    return True


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
