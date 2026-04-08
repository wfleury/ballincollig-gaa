#!/usr/bin/env python3
"""
Generate static HTML dashboards from competition baselines.

Reads the JSON baselines saved by the competition monitor and produces:
  - ``dashboard/index.html`` — landing page linking to each age group
  - ``dashboard/{age_group}/index.html`` — per-age-group dashboard

Run after the competition monitor:
    python generate_dashboard.py
"""

import json
import os
import shutil
from datetime import datetime
from html import escape

from competition_monitor.config import (
    AGE_GROUPS, BASELINE_DIR, CLUB_NAME, competition_url,
    get_active_competitions,
)
from gaa_utils import gaa_total

DASHBOARD_DIR = "dashboard"


# ------------------------------------------------------------------
# Data loading
# ------------------------------------------------------------------

def _load_baselines(competitions):
    """Load competition baselines and return {comp_name: baseline}."""
    baselines = {}
    for comp_name in competitions:
        safe = comp_name.lower().replace(" ", "_").replace("/", "_")
        path = os.path.join(BASELINE_DIR, f"{safe}.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    baselines[comp_name] = json.load(f)
            except (json.JSONDecodeError, ValueError):
                pass
    return baselines


def _is_ours(match):
    """True if Ballincollig is home or away."""
    name = CLUB_NAME.lower()
    return (name in match.get("home", "").lower() or
            name in match.get("away", "").lower())


def _parse_date(date_str):
    """Try to parse a date string into a datetime for sorting."""
    for fmt in ("%d/%m/%Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, TypeError):
            continue
    return datetime.max


# ------------------------------------------------------------------
# HTML generation
# ------------------------------------------------------------------

_CSS = """\
:root {
  --primary: #1a5632;
  --primary-light: #e8f5e9;
  --accent: #ffc107;
  --bg: #f5f5f5;
  --card: #ffffff;
  --text: #212121;
  --muted: #757575;
  --border: #e0e0e0;
  --highlight: #fff8e1;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.5;
  max-width: 960px; margin: 0 auto; padding: 16px;
}
.header { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }
.header img { height: 56px; width: auto; }
h1 { color: var(--primary); font-size: 1.6em; }
.subtitle { color: var(--muted); font-size: 0.9em; margin-bottom: 20px; }
h2 { color: var(--primary); margin: 24px 0 12px; font-size: 1.25em;
     border-bottom: 2px solid var(--primary); padding-bottom: 4px; }
h3 { color: var(--primary); margin: 16px 0 8px; font-size: 1.05em; }
.card { background: var(--card); border-radius: 8px; padding: 16px;
        margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
th { background: var(--primary); color: white; text-align: left;
     padding: 8px 10px; font-weight: 600; }
td { padding: 6px 10px; border-bottom: 1px solid var(--border); }
tr.ours { background: var(--highlight); font-weight: 600; }
tr:hover { background: var(--primary-light); }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px;
         font-size: 0.75em; font-weight: 600; }
.badge-win { background: #c8e6c9; color: #2e7d32; }
.badge-loss { background: #ffcdd2; color: #c62828; }
.badge-draw { background: #fff9c4; color: #f57f17; }
.badge-postponed { background: #e0e0e0; color: #616161; }
.badge-upcoming { background: #bbdefb; color: #1565c0; }
a { color: var(--primary); }
.fixture-grid { display: grid; gap: 8px; }
.fixture-row { display: grid; grid-template-columns: 90px 1fr 60px;
               gap: 8px; align-items: center; padding: 6px 0;
               border-bottom: 1px solid var(--border); }
.fixture-date { font-weight: 600; font-size: 0.85em; }
.fixture-teams { }
.fixture-time { text-align: right; font-size: 0.85em; color: var(--muted); }
.empty { color: var(--muted); font-style: italic; padding: 12px 0; }
a { color: var(--primary); }
@media (max-width: 600px) {
  body { padding: 10px; }
  .fixture-row { grid-template-columns: 70px 1fr 50px; }
}
"""


def _result_badge(match):
    hs = gaa_total(match.get("home_score", "0-0"))
    aws = gaa_total(match.get("away_score", "0-0"))
    is_home = CLUB_NAME.lower() in match.get("home", "").lower()
    ours = hs if is_home else aws
    theirs = aws if is_home else hs
    if ours > theirs:
        return '<span class="badge badge-win">W</span>'
    elif ours < theirs:
        return '<span class="badge badge-loss">L</span>'
    return '<span class="badge badge-draw">D</span>'


def _render_fixtures(fixtures):
    """Render a list of upcoming fixtures as HTML."""
    our = [f for f in fixtures if _is_ours(f)]
    our.sort(key=lambda f: _parse_date(f.get("date", "")))
    if not our:
        return '<p class="empty">No upcoming fixtures.</p>'
    rows = []
    for f in our:
        postponed = f.get("postponed")
        time_str = '<span class="badge badge-postponed">Postponed</span>' if postponed else escape(f.get("time", ""))
        rows.append(
            f'<div class="fixture-row">'
            f'<div class="fixture-date">{escape(f.get("date", ""))}</div>'
            f'<div class="fixture-teams">{escape(f["home"])} vs {escape(f["away"])}</div>'
            f'<div class="fixture-time">{time_str}</div>'
            f'</div>'
        )
    return '<div class="fixture-grid">' + "\n".join(rows) + '</div>'


def _render_results(results):
    """Render a list of results as HTML."""
    our = [r for r in results if _is_ours(r)]
    our.sort(key=lambda r: _parse_date(r.get("date", "")), reverse=True)
    if not our:
        return '<p class="empty">No results yet.</p>'
    rows = []
    for r in our:
        badge = _result_badge(r)
        rows.append(
            f'<div class="fixture-row">'
            f'<div class="fixture-date">{escape(r.get("date", ""))}</div>'
            f'<div class="fixture-teams">'
            f'{escape(r["home"])} {escape(r.get("home_score",""))} - '
            f'{escape(r.get("away_score",""))} {escape(r["away"])}'
            f'</div>'
            f'<div class="fixture-time">{badge}</div>'
            f'</div>'
        )
    return '<div class="fixture-grid">' + "\n".join(rows) + '</div>'


def _render_table(table):
    """Render a league table as an HTML table."""
    if not table:
        return '<p class="empty">No league table available.</p>'
    html = (
        '<table><thead><tr>'
        '<th>#</th><th>Team</th><th>Pld</th>'
        '<th>W</th><th>D</th><th>L</th>'
        '<th>PD</th><th>Pts</th>'
        '</tr></thead><tbody>'
    )
    for row in table:
        cls = ' class="ours"' if CLUB_NAME.lower() in row.get("team", "").lower() else ""
        html += (
            f'<tr{cls}>'
            f'<td>{row.get("position","")}</td>'
            f'<td>{escape(row.get("team",""))}</td>'
            f'<td>{row.get("played","")}</td>'
            f'<td>{row.get("won","")}</td>'
            f'<td>{row.get("drawn","")}</td>'
            f'<td>{row.get("lost","")}</td>'
            f'<td>{row.get("pd","")}</td>'
            f'<td>{row.get("pts","")}</td>'
            f'</tr>'
        )
    html += '</tbody></table>'
    return html


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

_LANDING_CSS = """\
:root {
  --primary: #1a5632;
  --primary-light: #e8f5e9;
  --bg: #f5f5f5;
  --card: #ffffff;
  --text: #212121;
  --muted: #757575;
  --border: #e0e0e0;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.5;
  max-width: 600px; margin: 0 auto; padding: 32px 16px;
  text-align: center;
}
.crest { height: 80px; width: auto; margin-bottom: 12px; }
h1 { color: var(--primary); margin-bottom: 4px; font-size: 1.8em; }
.subtitle { color: var(--muted); font-size: 0.9em; margin-bottom: 32px; }
.age-grid { display: grid; gap: 12px; }
.age-link {
  display: block; padding: 16px; border-radius: 8px;
  background: var(--card); box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  text-decoration: none; color: var(--primary);
  font-size: 1.1em; font-weight: 600;
  transition: background 0.2s, box-shadow 0.2s;
}
.age-link:hover { background: var(--primary-light);
  box-shadow: 0 2px 6px rgba(0,0,0,0.12); }
"""


def _generate_landing_page(age_groups_with_data, now):
    """Write dashboard/index.html with links to each age group page."""
    age_labels = {"u13": "U13", "u14": "U14", "u15": "U15",
                  "u16": "U16", "minor": "Minor"}

    links = ""
    for ag_key in ["u13", "u14", "u15", "u16", "minor"]:
        if ag_key not in age_groups_with_data:
            continue
        label = age_labels.get(ag_key, ag_key.upper())
        links += f'<a class="age-link" href="{ag_key}/">{label}</a>\n'

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{CLUB_NAME} GAA</title>
<style>{_LANDING_CSS}</style>
</head>
<body>
<img src="img/crest.gif" alt="{CLUB_NAME} crest" class="crest">
<h1>{CLUB_NAME} GAA</h1>
<p class="subtitle">Competition Dashboards &mdash; updated {now}</p>
<div class="age-grid">
{links}
</div>
<script data-goatcounter="https://ballincolliggaa.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>
</body>
</html>
"""
    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    path = os.path.join(DASHBOARD_DIR, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Landing page written to {path}")


def _generate_age_group_page(ag_key, comps, baselines, now):
    """Write dashboard/{ag_key}/index.html for one age group."""
    age_labels = {"u13": "U13", "u14": "U14", "u15": "U15",
                  "u16": "U16", "minor": "Minor"}
    label = age_labels.get(ag_key, ag_key.upper())

    # Split competitions into league vs championship
    league_comps = [(n, c) for n, c in comps if "championship" not in n.lower()]
    champ_comps = [(n, c) for n, c in comps if "championship" in n.lower()]

    content_html = ""
    for section_label, section_comps in [("League", league_comps), ("Championship", champ_comps)]:
        if not section_comps:
            continue
        content_html += f'<h2>{section_label}</h2>'
        for comp_name, comp_config in section_comps:
            baseline = baselines.get(comp_name)
            url = competition_url(comp_config)
            content_html += f'<h3><a href="{url}" target="_blank">{escape(comp_name)}</a></h3>'
            content_html += '<div class="card">'
            if baseline:
                fixtures = list(baseline.get("fixtures", {}).values())
                results = list(baseline.get("results", {}).values())
                table = baseline.get("table", [])

                content_html += '<h3>Upcoming</h3>'
                content_html += _render_fixtures(fixtures)
                content_html += '<h3>Results</h3>'
                content_html += _render_results(results)
                content_html += '<h3>Table</h3>'
                content_html += _render_table(table)
            else:
                content_html += '<p class="empty">No data yet — waiting for first monitor run.</p>'
            content_html += '</div>'

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{CLUB_NAME} GAA – {label}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="header">
  <a href="../"><img src="../img/crest.gif" alt="{CLUB_NAME} crest"></a>
  <h1><a href="../" style="text-decoration:none">{CLUB_NAME} GAA</a></h1>
</div>
<p class="subtitle">{label} Dashboard &mdash; updated {now}</p>
{content_html}
<script data-goatcounter="https://ballincolliggaa.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>
</body>
</html>
"""
    out_dir = os.path.join(DASHBOARD_DIR, ag_key)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{label} dashboard written to {path}")


def generate():
    competitions = get_active_competitions()
    baselines = _load_baselines(competitions)
    if not baselines:
        print("No baselines found — run the competition monitor first.")
        return

    now = datetime.now().strftime("%d %b %Y %H:%M")

    # Group competitions by age group
    by_age = {}
    for comp_name, comp_config in competitions.items():
        ag = comp_config.get("age_group", "other")
        by_age.setdefault(ag, []).append((comp_name, comp_config))

    # Generate a page per age group
    for ag_key in ["u13", "u14", "u15", "u16", "minor"]:
        comps = by_age.get(ag_key, [])
        if not comps:
            continue
        _generate_age_group_page(ag_key, comps, baselines, now)

    # Generate landing page
    _generate_landing_page(set(by_age.keys()), now)

    # Copy static assets (crest image etc.)
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        for item in os.listdir(static_dir):
            src = os.path.join(static_dir, item)
            dst = os.path.join(DASHBOARD_DIR, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        print("Static assets copied to dashboard/")


if __name__ == "__main__":
    generate()
