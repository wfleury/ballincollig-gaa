"""
ClubZap Results Sync Tool

Manages syncing of match results to ClubZap by tracking what's already been synced.
Unlike fixtures which can be bulk uploaded, results must be entered individually
through the ClubZap web interface.

Usage:
  python results_sync.py diff      -> show new results that need syncing
  python results_sync.py synced    -> mark current results as synced (update baseline)
  python results_sync.py status    -> show sync status
"""

import json
import os
import sys
from datetime import datetime
from results_scraper import ResultsScraper


# File paths
CURRENT_RESULTS_JSON = "current_results.json"
RESULTS_BASELINE_JSON = "clubzap_results_baseline.json"
NEW_RESULTS_JSON = "new_results_to_sync.json"


def generate_result_key(result):
    """Generate a unique key for a result based on date, teams, and competition."""
    return f"{result['date']}|{result['team']}|{result['opponent']}|{result['competition']}"


def load_results_json(filepath):
    """Load results from JSON file."""
    if not os.path.exists(filepath):
        return {}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Convert results list to dict keyed by result key
            if 'results' in data and isinstance(data['results'], list):
                results_dict = {}
                for result in data['results']:
                    key = generate_result_key(result)
                    results_dict[key] = result
                return results_dict
            return {}
    except (json.JSONDecodeError, KeyError):
        print(f"WARNING: Could not load {filepath}")
        return {}


def save_results_json(results_dict, filepath, description="results"):
    """Save results dict to JSON file."""
    results_list = list(results_dict.values())
    data = {
        'timestamp': datetime.now().isoformat(),
        'count': len(results_list),
        'results': results_list
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Saved {len(results_list)} {description} to {filepath}")


def diff_results():
    """Compare current results against synced baseline and show new results."""
    
    # Get current results from GAA Cork
    scraper = ResultsScraper()
    try:
        current_results_list = scraper.get_results_data()
        scraper.save_results_json(current_results_list, CURRENT_RESULTS_JSON)
    finally:
        scraper.close()
    
    if not current_results_list:
        print("ERROR: No results found from GAA Cork")
        return
    
    # Convert to dict for comparison
    current_results = {}
    for result in current_results_list:
        key = generate_result_key(result)
        current_results[key] = result
    
    # Load baseline (what's already synced to ClubZap)
    baseline_results = load_results_json(RESULTS_BASELINE_JSON)
    
    # Find new results
    new_results = {}
    for key, result in current_results.items():
        if key not in baseline_results:
            new_results[key] = result
    
    # Print summary
    print("=" * 60)
    print("  ClubZap Results Sync - Diff Report")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)
    print(f"  Current results (GAA Cork):      {len(current_results)}")
    print(f"  Baseline (synced to ClubZap):    {len(baseline_results)}")
    print("-" * 60)
    
    if not baseline_results:
        print(f"\n  FIRST RUN - No baseline found.")
        print(f"  All {len(current_results)} results are new.")
        save_results_json(new_results, NEW_RESULTS_JSON, "new results")
        print(f"\n  -> {NEW_RESULTS_JSON}")
        print(f"     These results need to be entered into ClubZap manually")
        print(f"     or via automated sync")
        print(f"\n  After syncing to ClubZap, run:")
        print(f"     python results_sync.py synced")
    else:
        print(f"\n  NEW results (need syncing):      {len(new_results)}")
        
        if new_results:
            save_results_json(new_results, NEW_RESULTS_JSON, "new results")
            print(f"\n  -> {NEW_RESULTS_JSON}")
            print(f"     These {len(new_results)} results need to be synced to ClubZap:")
            
            # Group by team and show details
            teams = {}
            for result in new_results.values():
                team = result['team']
                if team not in teams:
                    teams[team] = []
                teams[team].append(result)
            
            for team, team_results in teams.items():
                print(f"\n     {team} ({len(team_results)} results):")
                for result in sorted(team_results, key=lambda x: x['date']):
                    print(f"       {result['date']} vs {result['opponent']}: {result['our_score']} v {result['opponent_score']} ({result['result']})")
            
            print(f"\n  After syncing these results to ClubZap, run:")
            print(f"     python results_sync.py synced")
        else:
            print(f"\n  All results are already synced to ClubZap!")
    
    print("=" * 60)


def mark_synced():
    """Mark current results as synced to ClubZap (update baseline)."""
    if not os.path.exists(CURRENT_RESULTS_JSON):
        print(f"ERROR: {CURRENT_RESULTS_JSON} not found. Run 'python results_sync.py diff' first.")
        return
    
    # Load current results
    current_results = load_results_json(CURRENT_RESULTS_JSON)
    
    if not current_results:
        print("ERROR: No current results found")
        return
    
    # Save as new baseline
    save_results_json(current_results, RESULTS_BASELINE_JSON, "results baseline")
    
    print(f"Baseline updated: {len(current_results)} results marked as synced to ClubZap.")
    
    # Clean up new results file
    if os.path.exists(NEW_RESULTS_JSON):
        os.remove(NEW_RESULTS_JSON)
        print(f"Cleaned up: {NEW_RESULTS_JSON}")


def show_status():
    """Show current sync status."""
    current_results = load_results_json(CURRENT_RESULTS_JSON)
    baseline_results = load_results_json(RESULTS_BASELINE_JSON)
    
    print(f"Current results (from GAA Cork):     {len(current_results)}")
    print(f"Baseline (synced to ClubZap):        {len(baseline_results)}")
    
    if baseline_results:
        # Quick diff count
        new_count = sum(1 for k in current_results if k not in baseline_results)
        print(f"New (not yet synced):                {new_count}")
        
        if current_results:
            # Show recent results
            recent_results = sorted(current_results.values(), key=lambda x: x['date'])[-5:]
            print(f"\nRecent results:")
            for result in recent_results:
                sync_status = "✓ synced" if generate_result_key(result) in baseline_results else "○ pending"
                print(f"  {result['date']} - {result['team']} {result['our_score']} v {result['opponent_score']} {result['opponent']} ({result['result']}) {sync_status}")
    else:
        print("No baseline exists yet. Run: python results_sync.py synced")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    if command == 'diff':
        diff_results()
    elif command == 'synced':
        mark_synced()
    elif command == 'status':
        show_status()
    else:
        print(f"Unknown command: {command}")
        print("Usage: python results_sync.py [diff|synced|status]")