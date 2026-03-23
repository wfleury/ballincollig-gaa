# Ballincollig GAA Fixture Manager

An automated system that keeps the club's ClubZap fixtures in sync with the Cork County Board website — no manual data entry required.

## The Problem

Every week, the Cork County Board publishes and updates fixtures on **gaacork.ie** — new games, time changes, venue swaps, postponements. A club volunteer then has to:

1. Manually check the county board website for updates
2. Log into **ClubZap** and type in every new fixture, edit, or cancellation
3. Do this across **every age grade** — Seniors, Juniors, Minors, U14s, U16s, U21s — potentially dozens of fixtures per week

ClubZap supports bulk creation of fixtures via CSV upload, but **does not support bulk editing or bulk deletion**. When the county board changes a time, venue, or referee — which happens constantly — each fixture must be edited individually by hand. This is tedious, error-prone, and things get missed. Players and parents end up with wrong information in the club app.

## The Solution

This system completely automates that process:

1. **Checks the county board website every morning at 6am** — automatically, no human needed
2. **Spots any changes** — new fixtures, time or venue changes, referee assignments, postponements, cancellations
3. **Updates ClubZap automatically** — adds new fixtures via CSV upload, edits changed ones individually (solving the bulk-edit gap), and removes cancelled ones
4. **Sends a phone notification** — whoever is subscribed gets an instant alert with exactly what changed (e.g. "Senior Football vs Nemo Rangers moved from 3pm to 7:30pm, venue changed to Pairc Ui Rinn")
5. **If nothing changed, sends an "all clear"** — so you know it's running and nothing was missed

## What It Means for the Club

- **No more volunteer hours** spent on fixture data entry
- **No more missed updates** — every change the county board makes is caught within 24 hours
- **Players and parents always have accurate info** in the ClubZap app
- **Covers all teams automatically** — it knows which competition maps to which age grade (e.g. "McCarthy Insurance Premier SFC" = Senior Football)
- **Handles edge cases** — postponed games, referee TBC, home vs away, and filters out non-GAA fixtures (rugby etc.)

## How It Works

```
gaacork.ie (Cork County Board)
     |
     v
 [ Scraper ]         Checks the website daily using a headless browser
     |
     v
 [ Change Detector ]  Compares today's fixtures against yesterday's — spots
     |                 new, changed, postponed, and removed fixtures
     v
 [ ClubZap Sync ]     Uploads new fixtures (CSV), edits changed ones
     |                 individually, deletes cancelled ones
     v
 ClubZap Dashboard    Players and parents see accurate fixture info
     |
     v
 [ Notifications ]    Push alerts to phone via ntfy.sh with the club crest
                      Includes "Open ClubZap" button — per-team topics available
```

## How It Runs

The system runs for free on **GitHub Actions** (a cloud service) — no club server or computer needs to be left on. It checks once a day at 6am, and can also be triggered manually at any time. All fixture data is archived for 30 days.

## Notifications

Every notification includes a **"Open ClubZap"** button that links directly to the fixtures dashboard.

### All-Fixtures Notifications

Subscribe to **all** fixture changes across every team:

- **Topic:** `ballincollig-gaa-fixtures`
- **Subscribe:** [ntfy.sh/ballincollig-gaa-fixtures](https://ntfy.sh/ballincollig-gaa-fixtures)

### Per-Team Notifications (for managers)

Team managers can subscribe to notifications for **only their team**. When a fixture changes, only the teams affected receive a notification — no noise from other age grades.

| Team | ntfy Topic | Subscribe Link |
|------|-----------|----------------|
| Senior Football | `ballincollig-gaa-fixtures-senior-football` | [Subscribe](https://ntfy.sh/ballincollig-gaa-fixtures-senior-football) |
| Premier Inter Hurling | `ballincollig-gaa-fixtures-premier-inter-hurling` | [Subscribe](https://ntfy.sh/ballincollig-gaa-fixtures-premier-inter-hurling) |
| Junior A Football | `ballincollig-gaa-fixtures-junior-a-football` | [Subscribe](https://ntfy.sh/ballincollig-gaa-fixtures-junior-a-football) |
| Junior A Hurling | `ballincollig-gaa-fixtures-junior-a-hurling` | [Subscribe](https://ntfy.sh/ballincollig-gaa-fixtures-junior-a-hurling) |
| Junior B Football | `ballincollig-gaa-fixtures-junior-b-football` | [Subscribe](https://ntfy.sh/ballincollig-gaa-fixtures-junior-b-football) |
| Junior B Hurling | `ballincollig-gaa-fixtures-junior-b-hurling` | [Subscribe](https://ntfy.sh/ballincollig-gaa-fixtures-junior-b-hurling) |
| Junior C Football | `ballincollig-gaa-fixtures-junior-c-football` | [Subscribe](https://ntfy.sh/ballincollig-gaa-fixtures-junior-c-football) |
| Minor Football GAA | `ballincollig-gaa-fixtures-minor-football-gaa` | [Subscribe](https://ntfy.sh/ballincollig-gaa-fixtures-minor-football-gaa) |
| Minor Hurling GAA | `ballincollig-gaa-fixtures-minor-hurling-gaa` | [Subscribe](https://ntfy.sh/ballincollig-gaa-fixtures-minor-hurling-gaa) |
| U12 GAA | `ballincollig-gaa-fixtures-u12` | [Subscribe](https://ntfy.sh/ballincollig-gaa-fixtures-u12) |
| U13 GAA | `ballincollig-gaa-fixtures-u13` | [Subscribe](https://ntfy.sh/ballincollig-gaa-fixtures-u13) |
| U14 GAA | `ballincollig-gaa-fixtures-u14` | [Subscribe](https://ntfy.sh/ballincollig-gaa-fixtures-u14) |
| U15 GAA | `ballincollig-gaa-fixtures-u15` | [Subscribe](https://ntfy.sh/ballincollig-gaa-fixtures-u15) |
| U16 GAA | `ballincollig-gaa-fixtures-u16` | [Subscribe](https://ntfy.sh/ballincollig-gaa-fixtures-u16) |
| GAA U21 Football | `ballincollig-gaa-fixtures-gaa-u21-a-football` | [Subscribe](https://ntfy.sh/ballincollig-gaa-fixtures-gaa-u21-a-football) |
| GAA U21 Hurling | `ballincollig-gaa-fixtures-gaa-u21-a-hurling` | [Subscribe](https://ntfy.sh/ballincollig-gaa-fixtures-gaa-u21-a-hurling) |

**How to subscribe:** Install the free [ntfy app](https://ntfy.sh) on your phone (Android/iOS), tap **+**, and enter the topic name from the table above.

## Safety

- On its first run, it won't bulk-upload everything — it waits for confirmation to prevent duplicates
- If an edit fails (e.g. ClubZap is temporarily down), it retries automatically on the next run
- The club's ClubZap login credentials are stored securely as encrypted secrets — never visible in code or logs

## Next Steps

### LGFA (Ladies Football) Support

The county board website already publishes LGFA fixtures alongside the men's games. The system currently filters these out, but enabling them is straightforward:

- Remove the LGFA exclusion filter
- Add team name mappings so LGFA competitions (e.g. "LGFA Junior A Football") map to the correct ClubZap team names
- Ensure the corresponding LGFA teams are set up in ClubZap

This is a small change and could be turned on quickly once the ClubZap team names are confirmed.

### Camogie Support

Camogie fixtures are managed by a separate county board and are likely published on a different website (e.g. Cork Camogie or Foireann). Supporting Camogie would require:

- Identifying where Ballincollig Camogie fixtures are published online
- Building a scraper for that site (different page structure to gaacork.ie)
- Adding team name mappings for Camogie competitions
- Merging Camogie fixtures into the same pipeline so they sync to ClubZap alongside GAA and LGFA fixtures

### Other Potential Enhancements

- **Clash detection** — Flag when two club teams are scheduled at the same time, or when dual players have overlapping fixtures across codes
- **Change audit trail** — Track every fixture change over the season for AGM reporting or raising scheduling concerns with the county board

## Technical Details

### Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

### Running Locally

```bash
# Run the full pipeline (scrape + detect changes + notify)
python enhanced_monitor.py

# Just check what needs syncing to ClubZap
python clubzap_sync.py diff

# Sync changes to ClubZap (requires CLUBZAP_EMAIL and CLUBZAP_PASSWORD env vars)
python clubzap_automate.py
```

### Project Structure

```
gaa-scraper/
├── enhanced_monitor.py      # Main orchestrator — scrape, detect changes, notify
├── selenium_scraper.py      # Primary scraper (headless Chrome)
├── scraper.py               # Fallback scraper (requests + BeautifulSoup)
├── clubzap_sync.py          # Diff engine — compares fixtures vs baseline
├── clubzap_automate.py      # Browser automation — syncs changes to ClubZap
├── team_mapping.py          # Maps competition names to ClubZap team names
├── config.py                # Central configuration
├── requirements.txt         # Python dependencies
└── .github/workflows/
    ├── check_fixtures.yml   # Daily automated run (GitHub Actions)
    └── test_clubzap.yml     # Manual test workflow for ClubZap operations
```
