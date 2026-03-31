# GAA Scraper - Project Guide

## Commands

- **Run tests:** `python3 -m pytest tests/ -q`
- **Competition monitor:** `python -m competition_monitor` (all) or `--comp "Fe14 Premier 1 Football"` (one) or `--list`
- **Fixture monitor:** `python enhanced_monitor.py`
- **ClubZap sync:** `python clubzap_sync.py diff` then `python clubzap_automate.py`
- **Dashboard:** `python generate_dashboard.py`
- **Deps:** `pip install -r requirements.txt`

## Overview

Automated fixture management for **Ballincollig GAA Club** (Cork). Two independent systems, both on GitHub Actions:

### System 1: Fixture Monitor + ClubZap Sync (root-level files)
Scrapes gaacork.ie club profile daily + corkcamogie.com league pages, detects fixture changes via SHA-256 hash, syncs to ClubZap via Playwright, sends ntfy.sh notifications.

**Flow:** `enhanced_monitor.py` -> `selenium_scraper.py` + `camogie_scraper.py` -> `team_mapping.py` -> `clubzap_sync.py` -> `clubzap_automate.py`

**Config:** `config.py` (root) - `CLUB_ID=1986`, gaacork.ie URLs, `CAMOGIE_LEAGUES` (corkcamogie.com URLs + team mappings), ClubZap IDs, ntfy topics, CSV schema.

### System 2: Competition Results Monitor (`competition_monitor/` package)
Scrapes rebelog.ie competition pages 3x daily, tracks results + league tables via JSON baselines, sends ntfy.sh notifications, generates static HTML dashboard on GitHub Pages.

**Flow:** `competition_monitor/monitor.py` -> `scraper.py` -> `results_tracker.py` -> `notifier.py` + `discovery.py`

**Config:** `competition_monitor/config.py` (separate from root) - 17 competitions on rebelog.ie, 5 age groups (u13-minor), ntfy topics. Env vars: `COMP_AGE_GROUPS`, `COMP_NAMES`.

## File Map

### System 1 files (root level)
| File | Purpose |
|---|---|
| `config.py` | Root config: CLUB_NAME, CLUB_ID, BASE_URL (gaacork.ie), ClubZap IDs, CSV KEY_COLS/CHANGE_COLS |
| `enhanced_monitor.py` | Main orchestrator: scrape -> hash compare -> diff -> notify. Class `EnhancedFixtureMonitor` |
| `selenium_scraper.py` | Selenium scraper for gaacork.ie/clubprofile/ pages. Class `SeleniumScraper` |
| `scraper.py` | BeautifulSoup scraper (legacy fallback). Class `GAAClubScraper` |
| `clubzap_sync.py` | Diff engine: compares current CSV vs baseline -> new/changed/removed CSVs. CLI: `diff\|uploaded\|status` |
| `clubzap_automate.py` | Playwright browser automation for ClubZap CRUD. CLI: `upload\|edit\|delete\|all` |
| `team_mapping.py` | Maps GAA Cork competition names -> ClubZap team names (e.g., "Fe14..." -> "U14 GAA") |
| `camogie_scraper.py` | HTTP scraper for corkcamogie.com Foireann widgets. No Selenium needed. Function `scrape_camogie_fixtures()` |

### System 2 files (`competition_monitor/`)
| File | Purpose |
|---|---|
| `config.py` | Competition definitions (17 comps), age groups, rebelog.ie URLs, ntfy topics |
| `monitor.py` | Orchestrator: scrape -> diff -> notify -> save baseline. Entry: `run()` |
| `scraper.py` | Selenium scraper for SportLomo league pages. Class `CompetitionScraper` |
| `results_tracker.py` | JSON baselines in `competition_baselines/`. Functions: `compute_diff()`, `has_changes()`, `save_baseline()` |
| `notifier.py` | ntfy.sh sender. Functions: `notify_our_result()` (high), `notify_other_results()`, `notify_fixture_changes()`, `notify_first_run()` (low), `notify_all_clear()` (exists but NOT called) |
| `discovery.py` | Auto-discovers new competitions on rebelog.ie by scanning league links |
| `__main__.py` | CLI entry point with `--comp` and `--list` args |

### Shared / Other
| File | Purpose |
|---|---|
| `gaa_utils.py` | `gaa_total("2-10")` -> 16 (goals*3 + points) |
| `generate_dashboard.py` | Reads baselines -> static HTML in `dashboard/` -> GitHub Pages |
| `static/img/crest.gif` | Club crest (tracked, copied to dashboard) |
| `competition_baselines/` | Runtime JSON baselines (gitignored, cached in CI) |

### Tests
| File | Tests |
|---|---|
| `test_results_tracker.py` | ~25 tests: compute_diff, has_changes, baselines |
| `test_clubzap_sync.py` | ~13 tests: fixture diff engine |
| `test_team_mapping.py` | ~40 tests: competition name -> team name mapping |
| `test_camogie_scraper.py` | ~22 tests: Foireann HTML parsing, date parsing, HTTP mocking |

### CI/CD (`.github/workflows/`)
| Workflow | Schedule | What it runs |
|---|---|---|
| `check_fixtures.yml` | Daily 06:00 UTC | `enhanced_monitor.py` -> `clubzap_sync.py` -> `clubzap_automate.py` |
| `check_results.yml` | 05:00, 12:00, 21:00 UTC | `python -m competition_monitor` -> `generate_dashboard.py` -> deploy to GitHub Pages. Currently filtered: `COMP_AGE_GROUPS=u14` |
| `test_clubzap.yml` | Manual only | Test ClubZap CRUD with fake fixture |

## Key Data Structures

**competition_monitor diff** (from `compute_diff()`):
```python
{"first_run", "new_results", "our_new_results", "fixture_changes",
 "new_fixtures", "removed_fixtures", "table_changed", "table",
 "our_standing", "result_count", "fixture_count"}
```

**Baseline match key:** `"date|home|away"` (lowercased). Fixtures becoming results are NOT counted as removed.

## Important Patterns

- **Two separate config.py files** - root (fixture monitor, gaacork.ie) vs `competition_monitor/config.py` (competition monitor, rebelog.ie). Don't confuse them.
- **CLUB_NAME = "Ballincollig"** everywhere to identify "our" results/fixtures.
- **Notifications:** ntfy.sh HTTP POST. Two tiers: per-competition/team topics + combined age-group topics. `COMP_NTFY_QUIET` / `NTFY_QUIET` env vars force low priority in CI.
- **GAA scores:** "goals-points" format (e.g., "2-10" = 2*3+10 = 16 total).
- **Postponed:** time "0:00" or "00:00".
- **Safety:** ClubZap won't bulk-upload >20 fixtures without existing baseline.
- **Baselines gitignored**, persisted via GitHub Actions cache.
