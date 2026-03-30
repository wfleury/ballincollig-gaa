"""
Unit tests for clubzap_sync.py — fixture diffing engine.
"""

import csv
import os
import tempfile
import shutil

import pytest

from clubzap_sync import fixture_key, read_csv_fixtures, write_csv, diff_fixtures, mark_uploaded
from config import FIXTURE_HEADER as HEADER, KEY_COLS, CHANGE_COLS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_row(**overrides):
    """Return a fixture row dict with sensible defaults."""
    defaults = {
        "Date": "01/04/2026",
        "Time": "19:30",
        "Venue": "Ballincollig GAA Grounds",
        "Ground": "Home",
        "Referee": "John Smith",
        "Team": "Senior Football",
        "Competition Name": "McCarthy Insurance Premier SFC",
        "Your Club Name": "Ballincollig",
        "Opponent": "Nemo Rangers",
        "Event Type": "League",
    }
    defaults.update(overrides)
    return defaults


def _write_csv_file(filepath, rows):
    """Write a list of row dicts to a CSV file with the standard header."""
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ---------------------------------------------------------------------------
# fixture_key
# ---------------------------------------------------------------------------

class TestFixtureKey:
    def test_basic_key(self):
        row = _make_row()
        key = fixture_key(row)
        assert key == ("01/04/2026", "Senior Football", "Nemo Rangers",
                       "McCarthy Insurance Premier SFC")

    def test_strips_whitespace(self):
        row = _make_row(Date="  01/04/2026 ", Opponent=" Nemo Rangers  ")
        key = fixture_key(row)
        assert key == ("01/04/2026", "Senior Football", "Nemo Rangers",
                       "McCarthy Insurance Premier SFC")

    def test_missing_column_defaults_empty(self):
        row = {"Date": "01/04/2026", "Team": "Senior Football"}
        key = fixture_key(row)
        assert key == ("01/04/2026", "Senior Football", "", "")

    def test_different_fixtures_have_different_keys(self):
        row_a = _make_row(Opponent="Nemo Rangers")
        row_b = _make_row(Opponent="Carbery Rangers")
        assert fixture_key(row_a) != fixture_key(row_b)

    def test_same_fixture_same_key(self):
        row_a = _make_row()
        row_b = _make_row(Time="14:00", Venue="Pairc Ui Rinn")  # time/venue differ
        assert fixture_key(row_a) == fixture_key(row_b)


# ---------------------------------------------------------------------------
# read_csv_fixtures
# ---------------------------------------------------------------------------

class TestReadCsvFixtures:
    def test_reads_valid_csv(self, tmp_path):
        path = str(tmp_path / "fixtures.csv")
        rows = [_make_row(), _make_row(Opponent="Carbery Rangers")]
        _write_csv_file(path, rows)

        result = read_csv_fixtures(path)
        assert len(result) == 2

    def test_returns_empty_for_missing_file(self, tmp_path):
        result = read_csv_fixtures(str(tmp_path / "nonexistent.csv"))
        assert result == {}

    def test_keyed_by_fixture_key(self, tmp_path):
        path = str(tmp_path / "fixtures.csv")
        row = _make_row()
        _write_csv_file(path, [row])

        result = read_csv_fixtures(path)
        expected_key = ("01/04/2026", "Senior Football", "Nemo Rangers",
                        "McCarthy Insurance Premier SFC")
        assert expected_key in result

    def test_duplicate_keys_last_wins(self, tmp_path):
        path = str(tmp_path / "fixtures.csv")
        row1 = _make_row(Time="14:00")
        row2 = _make_row(Time="19:30")  # same key, different time
        _write_csv_file(path, [row1, row2])

        result = read_csv_fixtures(path)
        assert len(result) == 1
        key = fixture_key(row1)
        assert result[key]["Time"] == "19:30"


# ---------------------------------------------------------------------------
# write_csv
# ---------------------------------------------------------------------------

class TestWriteCsv:
    def test_round_trip(self, tmp_path):
        path = str(tmp_path / "out.csv")
        rows = [_make_row(), _make_row(Opponent="Carbery Rangers")]
        write_csv(path, rows)

        result = read_csv_fixtures(path)
        assert len(result) == 2

    def test_header_is_correct(self, tmp_path):
        path = str(tmp_path / "out.csv")
        write_csv(path, [_make_row()])

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
        assert header == HEADER


# ---------------------------------------------------------------------------
# diff_fixtures (integration-style test with temp files)
# ---------------------------------------------------------------------------

class TestDiffFixtures:
    """Test the diff engine by writing temp CSV files and running diff_fixtures."""

    @pytest.fixture(autouse=True)
    def _setup_temp_dir(self, tmp_path, monkeypatch):
        """Redirect all file paths used by clubzap_sync to a temp directory."""
        self.tmp = tmp_path
        self.full_csv = str(tmp_path / "full.csv")
        self.baseline_csv = str(tmp_path / "baseline.csv")
        self.new_csv = str(tmp_path / "new.csv")
        self.changed_csv = str(tmp_path / "changed.csv")
        self.removed_csv = str(tmp_path / "removed.csv")

        import clubzap_sync
        monkeypatch.setattr(clubzap_sync, "FULL_CSV", self.full_csv)
        monkeypatch.setattr(clubzap_sync, "BASELINE_CSV", self.baseline_csv)
        monkeypatch.setattr(clubzap_sync, "NEW_CSV", self.new_csv)
        monkeypatch.setattr(clubzap_sync, "CHANGED_CSV", self.changed_csv)
        monkeypatch.setattr(clubzap_sync, "REMOVED_CSV", self.removed_csv)

    def test_first_run_all_new(self):
        """With no baseline, every fixture is new."""
        rows = [_make_row(), _make_row(Opponent="Carbery Rangers")]
        _write_csv_file(self.full_csv, rows)

        diff_fixtures()

        assert os.path.exists(self.new_csv)
        new = read_csv_fixtures(self.new_csv)
        assert len(new) == 2
        assert not os.path.exists(self.changed_csv)
        assert not os.path.exists(self.removed_csv)

    def test_no_changes(self):
        """Identical current and baseline produces no diff files."""
        rows = [_make_row()]
        _write_csv_file(self.full_csv, rows)
        _write_csv_file(self.baseline_csv, rows)

        diff_fixtures()

        assert not os.path.exists(self.new_csv)
        assert not os.path.exists(self.changed_csv)
        assert not os.path.exists(self.removed_csv)

    def test_detects_new_fixture(self):
        """A fixture in current but not in baseline is new."""
        baseline_rows = [_make_row()]
        current_rows = [_make_row(), _make_row(Opponent="Carbery Rangers")]
        _write_csv_file(self.baseline_csv, baseline_rows)
        _write_csv_file(self.full_csv, current_rows)

        diff_fixtures()

        assert os.path.exists(self.new_csv)
        new = read_csv_fixtures(self.new_csv)
        assert len(new) == 1
        key = list(new.keys())[0]
        assert "Carbery Rangers" in key

    def test_detects_removed_fixture(self):
        """A fixture in baseline but not in current is removed."""
        baseline_rows = [_make_row(), _make_row(Opponent="Carbery Rangers")]
        current_rows = [_make_row()]
        _write_csv_file(self.baseline_csv, baseline_rows)
        _write_csv_file(self.full_csv, current_rows)

        diff_fixtures()

        assert os.path.exists(self.removed_csv)
        removed = read_csv_fixtures(self.removed_csv)
        assert len(removed) == 1

    def test_detects_changed_time(self):
        """A time change is detected as a changed fixture."""
        baseline_rows = [_make_row(Time="14:00")]
        current_rows = [_make_row(Time="19:30")]
        _write_csv_file(self.baseline_csv, baseline_rows)
        _write_csv_file(self.full_csv, current_rows)

        diff_fixtures()

        assert os.path.exists(self.changed_csv)
        # Read the changed CSV manually since it has an extra Changes column
        with open(self.changed_csv, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert "Time" in rows[0].get("Changes", "")

    def test_detects_changed_venue(self):
        """A venue change is detected."""
        baseline_rows = [_make_row(Venue="Ballincollig GAA Grounds")]
        current_rows = [_make_row(Venue="Pairc Ui Rinn")]
        _write_csv_file(self.baseline_csv, baseline_rows)
        _write_csv_file(self.full_csv, current_rows)

        diff_fixtures()

        assert os.path.exists(self.changed_csv)

    def test_detects_changed_referee(self):
        """A referee assignment is detected."""
        baseline_rows = [_make_row(Referee="TBC (Pending)")]
        current_rows = [_make_row(Referee="John Murphy")]
        _write_csv_file(self.baseline_csv, baseline_rows)
        _write_csv_file(self.full_csv, current_rows)

        diff_fixtures()

        assert os.path.exists(self.changed_csv)

    def test_postponed_fixture_not_in_new(self):
        """Postponed fixtures should not appear in new_fixtures.csv."""
        current_rows = [_make_row(Time="Postponed")]
        _write_csv_file(self.full_csv, current_rows)

        diff_fixtures()

        # Postponed fixture should NOT be in new CSV
        assert not os.path.exists(self.new_csv)

    def test_postponed_existing_fixture_not_unchanged(self):
        """A fixture that becomes postponed should not count as unchanged."""
        baseline_rows = [_make_row(Time="14:00")]
        current_rows = [_make_row(Time="Postponed")]
        _write_csv_file(self.baseline_csv, baseline_rows)
        _write_csv_file(self.full_csv, current_rows)

        diff_fixtures()

        # Should not produce a changed CSV (postponed is handled separately)
        assert not os.path.exists(self.changed_csv)


# ---------------------------------------------------------------------------
# mark_uploaded
# ---------------------------------------------------------------------------

class TestMarkUploaded:
    @pytest.fixture(autouse=True)
    def _setup_temp_dir(self, tmp_path, monkeypatch):
        self.tmp = tmp_path
        self.full_csv = str(tmp_path / "full.csv")
        self.baseline_csv = str(tmp_path / "baseline.csv")
        self.new_csv = str(tmp_path / "new.csv")
        self.changed_csv = str(tmp_path / "changed.csv")
        self.removed_csv = str(tmp_path / "removed.csv")

        import clubzap_sync
        monkeypatch.setattr(clubzap_sync, "FULL_CSV", self.full_csv)
        monkeypatch.setattr(clubzap_sync, "BASELINE_CSV", self.baseline_csv)
        monkeypatch.setattr(clubzap_sync, "NEW_CSV", self.new_csv)
        monkeypatch.setattr(clubzap_sync, "CHANGED_CSV", self.changed_csv)
        monkeypatch.setattr(clubzap_sync, "REMOVED_CSV", self.removed_csv)

    def test_creates_baseline(self):
        rows = [_make_row(), _make_row(Opponent="Carbery Rangers")]
        _write_csv_file(self.full_csv, rows)

        mark_uploaded()

        assert os.path.exists(self.baseline_csv)
        baseline = read_csv_fixtures(self.baseline_csv)
        assert len(baseline) == 2

    def test_cleans_up_diff_files(self):
        rows = [_make_row()]
        _write_csv_file(self.full_csv, rows)
        # Create dummy diff files
        for path in [self.new_csv, self.changed_csv, self.removed_csv]:
            with open(path, "w") as f:
                f.write("dummy")

        mark_uploaded()

        for path in [self.new_csv, self.changed_csv, self.removed_csv]:
            assert not os.path.exists(path)
