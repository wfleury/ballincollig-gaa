"""
Unit tests for competition_monitor/results_tracker.py — baseline persistence
and change detection for competition results.
"""

import json
import os

import pytest

from competition_monitor.results_tracker import (
    _match_key,
    _table_hash,
    _is_our_match,
    _our_position,
    compute_diff,
    save_baseline,
    load_baseline,
    has_changes,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fixture(**overrides):
    """Return a fixture dict with sensible defaults."""
    defaults = {
        "home": "Ballincollig",
        "away": "Nemo Rangers",
        "date": "12/04/2026",
        "time": "14:00",
        "venue": "Ballincollig GAA Grounds",
        "competition": "Fe14 Premier 1 Football",
        "referee": "",
    }
    defaults.update(overrides)
    return defaults


def _result(**overrides):
    """Return a result dict with sensible defaults."""
    defaults = {
        "home": "Ballincollig",
        "away": "Nemo Rangers",
        "date": "05/04/2026",
        "time": "14:00",
        "venue": "Ballincollig GAA Grounds",
        "competition": "Fe14 Premier 1 Football",
        "referee": "",
        "home_score": "2-10",
        "away_score": "1-8",
    }
    defaults.update(overrides)
    return defaults


def _table_row(**overrides):
    """Return a league table row with sensible defaults."""
    defaults = {
        "position": 1,
        "team": "Ballincollig",
        "played": 5,
        "won": 4,
        "drawn": 0,
        "lost": 1,
        "pf": 50,
        "pa": 30,
        "pd": 20,
        "pts": 8,
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# _match_key
# ---------------------------------------------------------------------------

class TestMatchKey:
    def test_basic(self):
        m = _fixture()
        key = _match_key(m)
        assert key == "12/04/2026|ballincollig|nemo rangers"

    def test_case_insensitive(self):
        m1 = _fixture(home="BALLINCOLLIG", away="NEMO RANGERS")
        m2 = _fixture(home="ballincollig", away="nemo rangers")
        assert _match_key(m1) == _match_key(m2)

    def test_different_dates_different_keys(self):
        m1 = _fixture(date="12/04/2026")
        m2 = _fixture(date="19/04/2026")
        assert _match_key(m1) != _match_key(m2)

    def test_different_opponents_different_keys(self):
        m1 = _fixture(away="Nemo Rangers")
        m2 = _fixture(away="Mallow")
        assert _match_key(m1) != _match_key(m2)

    def test_time_venue_dont_affect_key(self):
        m1 = _fixture(time="14:00", venue="Venue A")
        m2 = _fixture(time="19:30", venue="Venue B")
        assert _match_key(m1) == _match_key(m2)


# ---------------------------------------------------------------------------
# _table_hash
# ---------------------------------------------------------------------------

class TestTableHash:
    def test_same_table_same_hash(self):
        t = [_table_row()]
        assert _table_hash(t) == _table_hash(t)

    def test_different_table_different_hash(self):
        t1 = [_table_row(pts=8)]
        t2 = [_table_row(pts=10)]
        assert _table_hash(t1) != _table_hash(t2)

    def test_empty_table(self):
        assert _table_hash([]) == _table_hash([])


# ---------------------------------------------------------------------------
# _is_our_match
# ---------------------------------------------------------------------------

class TestIsOurMatch:
    def test_home(self):
        assert _is_our_match(_fixture(home="Ballincollig", away="Nemo")) is True

    def test_away(self):
        assert _is_our_match(_fixture(home="Nemo", away="Ballincollig")) is True

    def test_not_ours(self):
        assert _is_our_match(_fixture(home="Nemo", away="Mallow")) is False

    def test_case_insensitive(self):
        assert _is_our_match(_fixture(home="BALLINCOLLIG", away="Nemo")) is True

    def test_substring_match(self):
        assert _is_our_match(_fixture(home="Ballincollig 2nd", away="Nemo")) is True


# ---------------------------------------------------------------------------
# _our_position
# ---------------------------------------------------------------------------

class TestOurPosition:
    def test_found(self):
        table = [
            _table_row(position=1, team="Nemo Rangers", pts=10),
            _table_row(position=2, team="Ballincollig", pts=8),
        ]
        result = _our_position(table)
        assert result is not None
        assert result["position"] == 2
        assert result["pts"] == 8

    def test_not_found(self):
        table = [
            _table_row(position=1, team="Nemo Rangers", pts=10),
        ]
        assert _our_position(table) is None

    def test_empty_table(self):
        assert _our_position([]) is None


# ---------------------------------------------------------------------------
# save_baseline / load_baseline
# ---------------------------------------------------------------------------

class TestBaselineIO:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        import competition_monitor.results_tracker as rt
        monkeypatch.setattr(rt, "BASELINE_DIR", str(tmp_path))

    def test_round_trip(self):
        data = {
            "competition_name": "Fe14 Premier 1 Football",
            "fixtures": [_fixture()],
            "results": [_result()],
            "table": [_table_row()],
        }
        save_baseline("Fe14 Premier 1 Football", data)
        loaded = load_baseline("Fe14 Premier 1 Football")
        assert loaded is not None
        assert loaded["competition_name"] == "Fe14 Premier 1 Football"
        assert len(loaded["results"]) == 1
        assert len(loaded["fixtures"]) == 1

    def test_load_missing_returns_none(self):
        assert load_baseline("Nonexistent Competition") is None

    def test_load_corrupt_returns_none(self, tmp_path):
        path = tmp_path / "corrupt.json"
        path.write_text("{bad json")
        import competition_monitor.results_tracker as rt
        rt.BASELINE_DIR = str(tmp_path)
        # Use same safe name format as the module
        safe = "corrupt"
        path2 = tmp_path / f"{safe}.json"
        path2.write_text("{bad json")
        assert load_baseline("corrupt") is None


# ---------------------------------------------------------------------------
# compute_diff
# ---------------------------------------------------------------------------

class TestComputeDiff:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        import competition_monitor.results_tracker as rt
        monkeypatch.setattr(rt, "BASELINE_DIR", str(tmp_path))
        self.tmp = tmp_path

    def test_first_run(self):
        data = {
            "fixtures": [_fixture()],
            "results": [],
            "table": [],
        }
        diff = compute_diff("Test Comp", data)
        assert diff["first_run"] is True
        assert diff["fixture_count"] == 1

    def test_no_changes(self):
        data = {
            "fixtures": [_fixture()],
            "results": [_result()],
            "table": [_table_row()],
        }
        save_baseline("Test Comp", data)
        diff = compute_diff("Test Comp", data)
        assert diff["first_run"] is False
        assert diff["new_results"] == []
        assert diff["fixture_changes"] == []
        assert diff["new_fixtures"] == []
        assert diff["removed_fixtures"] == []
        assert diff["table_changed"] is False

    def test_new_result_detected(self):
        old_data = {
            "fixtures": [_fixture()],
            "results": [],
            "table": [],
        }
        save_baseline("Test Comp", old_data)

        new_data = {
            "fixtures": [],
            "results": [_result()],
            "table": [],
        }
        diff = compute_diff("Test Comp", new_data)
        assert len(diff["new_results"]) == 1
        assert len(diff["our_new_results"]) == 1

    def test_new_result_not_ours(self):
        old_data = {"fixtures": [], "results": [], "table": []}
        save_baseline("Test Comp", old_data)

        new_data = {
            "fixtures": [],
            "results": [_result(home="Nemo Rangers", away="Mallow",
                                home_score="1-5", away_score="0-8")],
            "table": [],
        }
        diff = compute_diff("Test Comp", new_data)
        assert len(diff["new_results"]) == 1
        assert len(diff["our_new_results"]) == 0

    def test_fixture_time_change(self):
        old_data = {
            "fixtures": [_fixture(time="14:00")],
            "results": [],
            "table": [],
        }
        save_baseline("Test Comp", old_data)

        new_data = {
            "fixtures": [_fixture(time="19:30")],
            "results": [],
            "table": [],
        }
        diff = compute_diff("Test Comp", new_data)
        assert len(diff["fixture_changes"]) == 1
        fixture, changes = diff["fixture_changes"][0]
        assert any("Time" in c for c in changes)

    def test_fixture_venue_change(self):
        old_data = {
            "fixtures": [_fixture(venue="Ballincollig GAA Grounds")],
            "results": [],
            "table": [],
        }
        save_baseline("Test Comp", old_data)

        new_data = {
            "fixtures": [_fixture(venue="Pairc Ui Chaoimh")],
            "results": [],
            "table": [],
        }
        diff = compute_diff("Test Comp", new_data)
        assert len(diff["fixture_changes"]) == 1

    def test_fixture_postponed(self):
        old_data = {
            "fixtures": [_fixture(time="14:00")],
            "results": [],
            "table": [],
        }
        save_baseline("Test Comp", old_data)

        new_data = {
            "fixtures": [_fixture(time="00:00", postponed=True)],
            "results": [],
            "table": [],
        }
        diff = compute_diff("Test Comp", new_data)
        assert len(diff["fixture_changes"]) == 1
        _, changes = diff["fixture_changes"][0]
        assert "POSTPONED" in changes

    def test_new_fixture_detected(self):
        old_data = {
            "fixtures": [_fixture()],
            "results": [],
            "table": [],
        }
        save_baseline("Test Comp", old_data)

        new_fixture = _fixture(date="26/04/2026", away="Mallow")
        new_data = {
            "fixtures": [_fixture(), new_fixture],
            "results": [],
            "table": [],
        }
        diff = compute_diff("Test Comp", new_data)
        assert len(diff["new_fixtures"]) == 1
        assert diff["new_fixtures"][0]["away"] == "Mallow"

    def test_removed_fixture_detected(self):
        old_data = {
            "fixtures": [_fixture(), _fixture(date="26/04/2026", away="Mallow")],
            "results": [],
            "table": [],
        }
        save_baseline("Test Comp", old_data)

        new_data = {
            "fixtures": [_fixture()],
            "results": [],
            "table": [],
        }
        diff = compute_diff("Test Comp", new_data)
        assert len(diff["removed_fixtures"]) == 1

    def test_fixture_that_got_result_not_removed(self):
        """A fixture that moves to results should NOT count as removed."""
        f = _fixture(date="05/04/2026")
        old_data = {
            "fixtures": [f],
            "results": [],
            "table": [],
        }
        save_baseline("Test Comp", old_data)

        r = _result(date="05/04/2026")
        new_data = {
            "fixtures": [],
            "results": [r],
            "table": [],
        }
        diff = compute_diff("Test Comp", new_data)
        assert len(diff["removed_fixtures"]) == 0
        assert len(diff["new_results"]) == 1

    def test_table_changed(self):
        old_data = {
            "fixtures": [],
            "results": [],
            "table": [_table_row(pts=8)],
        }
        save_baseline("Test Comp", old_data)

        new_data = {
            "fixtures": [],
            "results": [],
            "table": [_table_row(pts=10)],
        }
        diff = compute_diff("Test Comp", new_data)
        assert diff["table_changed"] is True

    def test_our_standing_populated(self):
        data = {
            "fixtures": [],
            "results": [],
            "table": [
                _table_row(position=1, team="Nemo Rangers", pts=10),
                _table_row(position=2, team="Ballincollig", pts=8),
            ],
        }
        diff = compute_diff("Test Comp", data)
        assert diff["our_standing"] is not None
        assert diff["our_standing"]["position"] == 2


# ---------------------------------------------------------------------------
# has_changes
# ---------------------------------------------------------------------------

class TestHasChanges:
    def test_first_run(self):
        assert has_changes({"first_run": True}) is True

    def test_new_results(self):
        assert has_changes({"new_results": [_result()]}) is True

    def test_fixture_changes(self):
        assert has_changes({"fixture_changes": [(_fixture(), ["Time"])]}) is True

    def test_new_fixtures(self):
        assert has_changes({"new_fixtures": [_fixture()]}) is True

    def test_removed_fixtures(self):
        assert has_changes({"removed_fixtures": [_fixture()]}) is True

    def test_no_changes(self):
        diff = {
            "first_run": False,
            "new_results": [],
            "fixture_changes": [],
            "new_fixtures": [],
            "removed_fixtures": [],
            "table_changed": True,
        }
        # table_changed alone should now trigger (after our fix)
        assert has_changes(diff) is True

    def test_truly_empty(self):
        diff = {
            "first_run": False,
            "new_results": [],
            "fixture_changes": [],
            "new_fixtures": [],
            "removed_fixtures": [],
            "table_changed": False,
        }
        assert has_changes(diff) is False


# ---------------------------------------------------------------------------
# Schema validation & rollback (save_baseline safety features)
# ---------------------------------------------------------------------------

from competition_monitor.results_tracker import (
    validate_baseline,
    BaselineValidationError,
    rollback_baseline,
)


class TestValidateBaseline:
    def test_valid_baseline_has_no_errors(self):
        bl = {
            "last_run": "2026-04-20T12:00:00",
            "results": {"k": _result(home_score="2-10", away_score="1-8")},
            "fixtures": {"k": _fixture()},
            "table": [_table_row()],
            "table_hash": "abc",
        }
        assert validate_baseline(bl) == []

    def test_missing_top_level_key(self):
        bl = {
            "last_run": "2026-04-20T12:00:00",
            "fixtures": {},
            "table": [],
            "table_hash": "",
        }
        errors = validate_baseline(bl)
        assert any("results" in e for e in errors)

    def test_result_without_score_fails(self):
        bad_result = {"home": "A", "away": "B", "date": "01/01/2026"}
        bl = {
            "last_run": "x", "results": {"k": bad_result},
            "fixtures": {}, "table": [], "table_hash": "",
        }
        errors = validate_baseline(bl)
        assert any("home_score" in e or "away_score" in e for e in errors)

    def test_fixture_without_teams_fails(self):
        bad_fix = {"date": "01/01/2026"}
        bl = {
            "last_run": "x", "results": {},
            "fixtures": {"k": bad_fix}, "table": [], "table_hash": "",
        }
        errors = validate_baseline(bl)
        assert any("home" in e or "away" in e for e in errors)


class TestSaveBaselineSafety:
    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        import competition_monitor.results_tracker as rt
        monkeypatch.setattr(rt, "BASELINE_DIR", str(tmp_path))
        self.tmp = tmp_path

    def test_save_creates_prev_backup(self):
        data = {
            "competition_name": "X",
            "fixtures": [_fixture()],
            "results": [_result()],
            "table": [_table_row()],
        }
        assert save_baseline("X", data) is True
        # Second save should create .prev
        data2 = {
            "competition_name": "X",
            "fixtures": [_fixture(date="19/04/2026")],
            "results": [_result()],
            "table": [_table_row()],
        }
        save_baseline("X", data2)
        prev = self.tmp / "x.json.prev"
        assert prev.exists()

    def test_rollback_restores_prev(self):
        data = {
            "competition_name": "X",
            "fixtures": [_fixture()],
            "results": [_result(home_score="2-10", away_score="0-5")],
            "table": [_table_row()],
        }
        save_baseline("X", data)
        # Second save — creates a .prev of the first one
        data2 = {
            "competition_name": "X",
            "fixtures": [],
            "results": [_result(home_score="3-3", away_score="1-1")],
            "table": [_table_row()],
        }
        save_baseline("X", data2)
        # Now rollback — should restore the first baseline
        assert rollback_baseline("X") is True
        loaded = load_baseline("X")
        # The first baseline had one fixture; data2 had none
        assert len(loaded["fixtures"]) == 1

    def test_rollback_without_prev_returns_false(self):
        assert rollback_baseline("Never Saved") is False

    def test_regression_guard_blocks_huge_drop(self):
        # Establish a healthy baseline with many results/table rows
        many_results = [
            _result(home=f"Team{i}", away=f"Opp{i}", date=f"{i:02d}/01/2026",
                    home_score="2-5", away_score="1-4")
            for i in range(10)
        ]
        many_table = [_table_row(team=f"Team{i}", position=i + 1)
                      for i in range(10)]
        save_baseline("X", {
            "competition_name": "X",
            "fixtures": [],
            "results": many_results,
            "table": many_table,
        })
        # Now try to save a near-empty scrape (regression)
        saved = save_baseline("X", {
            "competition_name": "X",
            "fixtures": [],
            "results": [],
            "table": [],
        })
        assert saved is False
        # Previous data should still be intact
        loaded = load_baseline("X")
        assert len(loaded["results"]) == 10

    def test_invalid_baseline_skipped_not_strict(self):
        bad = {
            "competition_name": "X",
            "fixtures": [],
            # Result missing scores will fail validation
            "results": [{"home": "A", "away": "B", "date": "01/01/26"}],
            "table": [],
        }
        assert save_baseline("X", bad) is False

    def test_invalid_baseline_raises_strict(self):
        bad = {
            "competition_name": "X",
            "fixtures": [],
            "results": [{"home": "A", "away": "B", "date": "01/01/26"}],
            "table": [],
        }
        with pytest.raises(BaselineValidationError):
            save_baseline("X", bad, strict=True)
