"""
Main orchestrator for the Competition Results Monitor.

For each configured competition:
  1. Scrape the competition page (fixtures, results, table)
  2. Load baseline and compute diff
  3. Send appropriate ntfy notifications
  4. Save updated baseline
"""

from competition_monitor.config import (
    get_active_competitions, competition_url, CLUB_NAME,
)
from competition_monitor.scraper import CompetitionScraper
from competition_monitor.results_tracker import (
    compute_diff, save_baseline, has_changes,
)
from competition_monitor import notifier
from competition_monitor.discovery import discover_new_competitions, notify_new_competitions


def run(competition_filter=None):
    """Run the monitor for all (or filtered) competitions.

    Args:
        competition_filter: optional competition name to run only one.
    """
    competitions = get_active_competitions()
    if competition_filter:
        competitions = {
            k: v for k, v in competitions.items()
            if k == competition_filter
        }
        if not competitions:
            print(f"No competition matching '{competition_filter}'")
            print("Available:", ", ".join(get_active_competitions()))
            return

    scraper = CompetitionScraper()
    try:
        for comp_name, comp_config in competitions.items():
            _process_competition(scraper, comp_name, comp_config)

        # Check for new competitions across all age groups
        if scraper.driver:
            new_comps = discover_new_competitions(scraper.driver)
            if new_comps:
                notify_new_competitions(new_comps)
    finally:
        scraper.close()


def _process_competition(scraper, comp_name, comp_config):
    """Scrape, diff, notify, and save for one competition."""
    url = competition_url(comp_config)
    print(f"\n{'='*60}")
    print(f"  {comp_name}")
    print(f"  {url}")
    print(f"{'='*60}")

    data = scraper.scrape(url)
    if not data:
        print(f"ERROR: Failed to scrape {comp_name}")
        return

    # Use the scraped competition name if we got one
    if not data.get("competition_name"):
        data["competition_name"] = comp_name

    diff = compute_diff(comp_name, data)

    if diff["first_run"]:
        print(f"First run for {comp_name} — saving baseline")
        notifier.notify_first_run(comp_config, diff, comp_name)
        save_baseline(comp_name, data)
        return

    if has_changes(diff):
        _report_changes(diff, comp_name)

        # Our results — high priority
        if diff["our_new_results"]:
            notifier.notify_our_result(comp_config, diff, comp_name)

        # Other results in the group
        if diff["new_results"]:
            notifier.notify_other_results(comp_config, diff, comp_name)

        # Fixture updates (time/venue changes, new, removed)
        if diff["fixture_changes"] or diff["new_fixtures"] or diff["removed_fixtures"]:
            notifier.notify_fixture_changes(comp_config, diff, comp_name)
    else:
        print(f"No changes for {comp_name}")
        notifier.notify_all_clear(comp_config, diff, comp_name)

    save_baseline(comp_name, data)


def _report_changes(diff, comp_name):
    """Print a summary of changes to stdout."""
    print(f"\nChanges detected for {comp_name}:")

    if diff["our_new_results"]:
        print(f"  {CLUB_NAME} results: {len(diff['our_new_results'])}")
        for r in diff["our_new_results"]:
            print(f"    {r['home']} {r['home_score']} v "
                  f"{r['away_score']} {r['away']}")

    others = [r for r in diff["new_results"]
              if r not in diff["our_new_results"]]
    if others:
        print(f"  Other results: {len(others)}")
        for r in others:
            print(f"    {r['home']} {r['home_score']} v "
                  f"{r['away_score']} {r['away']}")

    if diff["fixture_changes"]:
        print(f"  Fixture changes: {len(diff['fixture_changes'])}")
        for f, changes in diff["fixture_changes"]:
            print(f"    {f['date']} {f['home']} vs {f['away']}: "
                  f"{', '.join(changes)}")

    if diff["new_fixtures"]:
        print(f"  New fixtures: {len(diff['new_fixtures'])}")

    if diff["removed_fixtures"]:
        print(f"  Removed fixtures: {len(diff['removed_fixtures'])}")

    if diff["table_changed"]:
        print("  League table updated")
        if diff["our_standing"]:
            s = diff["our_standing"]
            print(f"    {CLUB_NAME}: {s['position']}th "
                  f"({s['pts']} pts, {s['played']} pld)")
