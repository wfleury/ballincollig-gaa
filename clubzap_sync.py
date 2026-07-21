"""
ClubZap Fixture Sync Tool

Manages differential uploads to ClubZap by tracking what's already been uploaded.
Generates:
  - new_fixtures.csv      -> bulk import these into ClubZap
  - changed_fixtures.csv  -> review and manually update in ClubZap
  - removed_fixtures.csv  -> manually delete from ClubZap

Usage:
  py clubzap_sync.py diff      -> generate diff files (new/changed/removed)
  py clubzap_sync.py uploaded  -> mark current fixtures as uploaded (update baseline)
  py clubzap_sync.py status    -> show sync status
"""

import csv
import os
import sys
import shutil
from datetime import datetime
from config import (
    FIXTURES_CSV as FULL_CSV, BASELINE_CSV, NEW_CSV, CHANGED_CSV, REMOVED_CSV,
    FIXTURE_HEADER as HEADER, KEY_COLS, CHANGE_COLS,
)


def fixture_key(row):
    """Generate a unique key for a fixture based on date, team, opponent, competition."""
    return tuple(row.get(c, '').strip() for c in KEY_COLS)


def read_csv_fixtures(filepath):
    """Read fixtures from CSV into a dict keyed by fixture_key."""
    fixtures = {}
    if not os.path.exists(filepath):
        return fixtures
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = fixture_key(row)
            fixtures[key] = row
    return fixtures


def _csv_row(fields):
    """Format a list of field values as a CSV row string.

    Only quotes fields that contain a comma.  This avoids the standard
    csv module's double-quote escaping (``""``), which ClubZap's CSV
    importer cannot parse — breaking team names like GAA U21 "A" Football.
    """
    parts = []
    for v in fields:
        v = str(v)
        if ',' in v:
            parts.append(f'"{v}"')
        else:
            parts.append(v)
    return ','.join(parts)


def write_csv(filepath, rows):
    """Write fixtures to CSV (ClubZap-compatible quoting)."""
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        f.write(_csv_row(HEADER) + '\n')
        for row in rows:
            f.write(_csv_row([row.get(col, '') for col in HEADER]) + '\n')


def diff_fixtures():
    """Compare current fixtures against uploaded baseline and generate diff files."""
    
    current = read_csv_fixtures(FULL_CSV)
    baseline = read_csv_fixtures(BASELINE_CSV)
    
    if not current:
        print(f"ERROR: No fixtures found in {FULL_CSV}")
        return
    
    new_fixtures = []
    changed_fixtures = []
    removed_fixtures = []
    unchanged = 0
    
    postponed_fixtures = []
    
    # Find new, changed, and postponed fixtures
    for key, row in current.items():
        if key not in baseline:
            # Skip postponed fixtures from new imports (delete from ClubZap instead)
            if row.get('Time', '') == 'Postponed':
                postponed_fixtures.append(row)
            else:
                new_fixtures.append(row)
        else:
            # If fixture is now postponed, flag for deletion from ClubZap
            if row.get('Time', '') == 'Postponed':
                postponed_fixtures.append(row)
                continue
            
            # Check if any important fields changed
            old_row = baseline[key]
            changes = []
            for col in CHANGE_COLS:
                old_val = old_row.get(col, '').strip()
                new_val = row.get(col, '').strip()
                if old_val != new_val:
                    changes.append(f"{col}: '{old_val}' -> '{new_val}'")
            
            if changes:
                changed_fixtures.append((row, changes))
            else:
                unchanged += 1
    
    # Find removed fixtures
    for key, row in baseline.items():
        if key not in current:
            removed_fixtures.append(row)
    
    # Safety guard: if >50% of baseline fixtures appear "removed", likely a scraper failure
    if baseline and removed_fixtures:
        removal_pct = len(removed_fixtures) / len(baseline) * 100
        if removal_pct > 50 and len(removed_fixtures) > 20:
            print(f"\n  SAFETY: {len(removed_fixtures)} fixtures ({removal_pct:.0f}%) appear removed — likely scraper failure.")
            print(f"  Refusing to generate {REMOVED_CSV} to prevent mass deletions.")
            print(f"  If these removals are genuine, delete the baseline and re-run.")
            removed_fixtures = []
    
    # Write diff files
    if new_fixtures:
        write_csv(NEW_CSV, new_fixtures)
    elif os.path.exists(NEW_CSV):
        os.remove(NEW_CSV)
    
    if changed_fixtures:
        # Include a Changes column describing what changed
        changed_rows = []
        for row, changes in changed_fixtures:
            row_copy = dict(row)
            row_copy['Changes'] = '; '.join(changes)
            changed_rows.append(row_copy)
        changed_header = HEADER + ['Changes']
        with open(CHANGED_CSV, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=changed_header)
            writer.writeheader()
            for row in changed_rows:
                writer.writerow(row)
    elif os.path.exists(CHANGED_CSV):
        os.remove(CHANGED_CSV)
    
    if removed_fixtures:
        write_csv(REMOVED_CSV, removed_fixtures)
    elif os.path.exists(REMOVED_CSV):
        os.remove(REMOVED_CSV)
    
    # Print summary
    print("=" * 60)
    print("  ClubZap Sync - Fixture Diff Report")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)
    print(f"  Current fixtures (website):  {len(current)}")
    print(f"  Baseline (uploaded):         {len(baseline)}")
    print("-" * 60)
    
    if not baseline:
        print(f"\n  FIRST RUN - No baseline found.")
        print(f"  All {len(current)} fixtures are new.")
        print(f"\n  -> {NEW_CSV}")
        print(f"     Upload this file to ClubZap, then run:")
        print(f"     py clubzap_sync.py uploaded")
    else:
        print(f"\n  NEW fixtures (bulk import):   {len(new_fixtures)}")
        print(f"  CHANGED fixtures (edit):      {len(changed_fixtures)}")
        print(f"  POSTPONED (delete):           {len(postponed_fixtures)}")
        print(f"  REMOVED fixtures (delete):    {len(removed_fixtures)}")
        print(f"  Unchanged:                    {unchanged}")
        
        if new_fixtures:
            print(f"\n  -> {NEW_CSV}")
            print(f"     Bulk upload this file to ClubZap")
            print(f"     Contains {len(new_fixtures)} new fixtures:")
            for row in new_fixtures[:5]:
                print(f"       {row['Date']} {row['Team']} vs {row['Opponent']}")
            if len(new_fixtures) > 5:
                print(f"       ... and {len(new_fixtures) - 5} more")
        
        if changed_fixtures:
            print(f"\n  -> {CHANGED_CSV}")
            print(f"     Manually update these {len(changed_fixtures)} fixtures in ClubZap:")
            for row, changes in changed_fixtures:
                print(f"       {row['Date']} {row['Team']} vs {row['Opponent']}")
                for c in changes:
                    print(f"         {c}")
        
        if postponed_fixtures:
            print(f"\n  POSTPONED - Delete these from ClubZap:")
            for row in postponed_fixtures:
                print(f"       {row['Date']} {row['Team']} vs {row['Opponent']} (cancelled/postponed)")
        
        if removed_fixtures:
            print(f"\n  -> {REMOVED_CSV}")
            print(f"     Manually delete these {len(removed_fixtures)} fixtures from ClubZap:")
            for row in removed_fixtures:
                print(f"       {row['Date']} {row['Team']} vs {row['Opponent']}")
    
    if new_fixtures or changed_fixtures or removed_fixtures or postponed_fixtures:
        print(f"\n  After making changes in ClubZap, run:")
        print(f"  py clubzap_sync.py uploaded")
    else:
        print(f"\n  Everything is in sync!")
    
    print("=" * 60)


def mark_uploaded():
    """Copy current full CSV as the new baseline (marks all as uploaded)."""
    if not os.path.exists(FULL_CSV):
        print(f"ERROR: {FULL_CSV} not found. Run the monitor first.")
        return
    
    shutil.copy2(FULL_CSV, BASELINE_CSV)
    
    current = read_csv_fixtures(FULL_CSV)
    print(f"Baseline updated: {len(current)} fixtures marked as uploaded to ClubZap.")
    print(f"Saved to: {BASELINE_CSV}")
    
    # Clean up diff files
    for f in [NEW_CSV, CHANGED_CSV, REMOVED_CSV]:
        if os.path.exists(f):
            os.remove(f)
            print(f"Cleaned up: {f}")


def show_status():
    """Show current sync status."""
    current = read_csv_fixtures(FULL_CSV)
    baseline = read_csv_fixtures(BASELINE_CSV)
    
    print(f"Current fixtures (from website): {len(current)}")
    print(f"Baseline (uploaded to ClubZap):  {len(baseline)}")
    
    if baseline:
        # Quick diff count
        new_count = sum(1 for k in current if k not in baseline)
        removed_count = sum(1 for k in baseline if k not in current)
        print(f"New (not yet uploaded):          {new_count}")
        print(f"Removed (need deletion):         {removed_count}")
    else:
        print("No baseline exists yet. Run: py clubzap_sync.py uploaded")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    if command == 'diff':
        diff_fixtures()
    elif command == 'uploaded':
        mark_uploaded()
    elif command == 'status':
        show_status()
    else:
        print(f"Unknown command: {command}")
        print("Usage: py clubzap_sync.py [diff|uploaded|status]")
