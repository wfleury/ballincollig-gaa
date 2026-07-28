#!/usr/bin/env python3
"""
Generate static HTML dashboards from competition baselines.

Reads the JSON baselines saved by the competition monitor and produces:
  - ``dashboard/index.html`` — landing page linking to each age group
  - ``dashboard/{age_group}/index.html`` — per-age-group dashboard

Run after the competition monitor:
    python generate_dashboard.py
"""

import calendar
import json
import os
import shutil
from collections import defaultdict
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
  --input-bg: #ffffff;
}
html[data-theme="dark"] {
  --primary: #4caf82;
  --primary-light: #1f3a2a;
  --accent: #ffc107;
  --bg: #121212;
  --card: #1e1e1e;
  --text: #e8e8e8;
  --muted: #9e9e9e;
  --border: #333;
  --highlight: #3a2f10;
  --input-bg: #2a2a2a;
}
html { color-scheme: light dark; }
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
        margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        overflow-x: auto; }
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
.muted { color: var(--muted); }
.form-cell { white-space: nowrap; }
.form-btn { border: none; cursor: pointer;
  font-family: inherit; line-height: inherit; }
.form-tip { display: none; }
.form-btn:focus { outline: 2px solid var(--primary); outline-offset: 1px; }
.form-btn:focus .form-tip { display: block; position: fixed;
  left: 16px; right: 16px; bottom: 16px;
  background: var(--text); color: white; padding: 8px 14px;
  border-radius: 8px; font-size: 0.85em; font-weight: 400;
  white-space: normal; z-index: 100; text-align: center; }
.section-nav { display: flex; gap: 8px; margin-bottom: 16px; }
.section-nav a {
  padding: 6px 16px; border-radius: 6px; font-weight: 600;
  font-size: 0.9em; text-decoration: none;
  background: var(--primary); color: white;
}
.section-nav a:hover { opacity: 0.85; }
a { color: var(--primary); }
@media (max-width: 600px) {
  body { padding: 10px; }
  .fixture-row { grid-template-columns: 70px 1fr 50px; }
  .hide-mobile { display: none; }
}
.back-to-top {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--primary);
  color: white;
  border: none;
  cursor: pointer;
  font-size: 24px;
  display: none;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  z-index: 1000;
}
.back-to-top:hover {
  background: var(--primary-light);
  color: var(--primary);
}
/* Theme toggle button */
.theme-toggle {
  background: transparent; border: 1px solid var(--border);
  color: var(--text); padding: 6px 10px; border-radius: 6px;
  cursor: pointer; font-size: 0.85em;
}
.theme-toggle:hover { background: var(--primary-light); }
.header-actions { display: flex; align-items: center; gap: 8px;
  margin-left: auto; }
/* Filter bar */
.filter-bar {
  display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px;
  padding: 10px; background: var(--card); border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.filter-bar input[type="search"] {
  flex: 1 1 200px; min-width: 0; padding: 8px 10px;
  border: 1px solid var(--border); border-radius: 6px;
  background: var(--input-bg); color: var(--text);
  font-size: 0.9em; font-family: inherit;
}
.filter-bar input[type="search"]:focus {
  outline: 2px solid var(--primary); outline-offset: 1px;
}
.filter-bar select {
  padding: 8px 10px; border: 1px solid var(--border);
  border-radius: 6px; background: var(--input-bg); color: var(--text);
  font-size: 0.9em; font-family: inherit;
}
.filter-clear {
  background: var(--border); border: none; color: var(--text);
  padding: 6px 12px; border-radius: 6px; cursor: pointer;
  font-size: 0.85em;
}
.filter-clear:hover { background: var(--primary-light); }
.filter-empty { display: none; color: var(--muted); font-style: italic;
  padding: 20px; text-align: center; }
.filter-empty.show { display: block; }
/* Collapsible competition */
.comp { margin-bottom: 16px; }
.comp-header {
  background: var(--card); border-radius: 8px;
  padding: 12px 16px; cursor: pointer; user-select: none;
  display: flex; align-items: center; justify-content: space-between;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  border: none; width: 100%; text-align: left;
  font-family: inherit; color: var(--text);
}
.comp-header:hover { background: var(--primary-light); }
.comp-header h3 { margin: 0; color: var(--primary); font-size: 1.05em; }
.comp-header .chev { transition: transform 0.2s; color: var(--muted);
  font-size: 1.2em; margin-left: 8px; }
.comp.open .comp-header .chev { transform: rotate(180deg); }
.comp-body { display: none; margin-top: 4px; }
.comp.open .comp-body { display: block; }
/* Desktop: default-open unless explicitly closed */
@media (min-width: 601px) {
  .comp:not(.user-closed) .comp-body { display: block; }
  .comp:not(.user-closed) .comp-header .chev { transform: rotate(180deg); }
}
/* Mobile: default-closed unless explicitly opened */
@media (max-width: 600px) {
  .comp .comp-body { display: none; }
  .comp.open .comp-body { display: block; }
}
.row-hidden { display: none !important; }
/* Calendar */
.cal-wrap { margin-bottom: 20px; }
.cal-nav { display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px; }
.cal-nav button { background: var(--primary); color: white; border: none;
  border-radius: 6px; padding: 6px 14px; cursor: pointer; font-weight: 600;
  font-size: 0.85em; }
.cal-nav button:hover { opacity: 0.85; }
.cal-nav .cal-title { font-weight: 700; font-size: 1.05em; }
.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
.cal-hdr { text-align: center; font-weight: 700; font-size: 0.75em;
  color: var(--muted); padding: 4px 0; }
.cal-cell { min-height: 60px; background: var(--card); border-radius: 4px;
  padding: 4px; font-size: 0.75em; border: 1px solid var(--border);
  overflow: hidden; position: relative; }
.cal-cell.empty { background: transparent; border-color: transparent; }
.cal-cell .day-num { font-weight: 700; font-size: 0.85em; color: var(--muted); }
.cal-cell.today { border-color: var(--primary); border-width: 2px; }
.cal-cell.today .day-num { color: var(--primary); }
.cal-cell.has-match { background: var(--highlight); }
.cal-evt { display: block; margin-top: 2px; padding: 1px 3px;
  border-radius: 3px; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; line-height: 1.3;
  background: var(--primary-light); color: var(--primary);
  font-size: 0.8em; font-weight: 600; cursor: default; }
.cal-evt:hover { opacity: 0.8; }
.cal-month { display: none; }
.cal-month.active { display: block; }
@media (max-width: 600px) {
  .cal-cell { min-height: 44px; font-size: 0.65em; }
  .cal-evt { font-size: 0.7em; padding: 0 2px; }
}
.next-match {
  background: linear-gradient(135deg, var(--primary), #2e7d32);
  color: white; border-radius: 10px; padding: 18px 20px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
html[data-theme="dark"] .next-match {
  background: linear-gradient(135deg, #1b5e20, #2e7d32);
}
.next-match h2 {
  color: white; border: none; margin: 0 0 10px; padding: 0;
  font-size: 1.1em; opacity: 0.9;
}
.next-match-card {
  background: rgba(255,255,255,0.15); border-radius: 8px;
  padding: 12px 16px; margin-bottom: 8px;
}
.next-match-card:last-child { margin-bottom: 0; }
.next-match-date { font-size: 0.85em; opacity: 0.85; margin-bottom: 2px; }
.next-match-teams { font-size: 1.15em; font-weight: 700; }
.next-match-meta {
  font-size: 0.85em; opacity: 0.85; margin-top: 4px;
  display: flex; flex-wrap: wrap; gap: 12px;
}
.next-match-meta span::before { margin-right: 4px; }
"""


def _pwa_head(relative_prefix=""):
    """HTML head tags for PWA manifest + apple-touch icon."""
    return (
        f'<link rel="manifest" href="{relative_prefix}manifest.webmanifest">\n'
        f'<meta name="theme-color" content="#1a5632" '
        f'media="(prefers-color-scheme: light)">\n'
        f'<meta name="theme-color" content="#121212" '
        f'media="(prefers-color-scheme: dark)">\n'
        f'<meta name="apple-mobile-web-app-capable" content="yes">\n'
        f'<meta name="apple-mobile-web-app-title" content="{CLUB_NAME} GAA">\n'
        f'<link rel="apple-touch-icon" href="{relative_prefix}img/crest.gif">\n'
        f'<link rel="icon" href="{relative_prefix}img/crest.gif">'
    )


def _og_head(title, desc, image_url):
    return (
        f'<meta property="og:title" content="{escape(title)}">\n'
        f'<meta property="og:description" content="{escape(desc)}">\n'
        f'<meta property="og:type" content="website">\n'
        f'<meta property="og:image" content="{escape(image_url)}">\n'
        f'<meta name="twitter:card" content="summary">'
    )


_THEME_INIT = """\
<script>
(function() {
  try {
    var stored = localStorage.getItem('theme');
    var theme = stored || (window.matchMedia &&
      window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);
  } catch (e) {}
})();
</script>"""


_THEME_TOGGLE_SCRIPT = """\
<script>
(function() {
  var btn = document.querySelector('.theme-toggle');
  if (!btn) return;
  function update() {
    var t = document.documentElement.getAttribute('data-theme') || 'light';
    btn.textContent = t === 'dark' ? 'Light' : 'Dark';
    btn.setAttribute('aria-label',
      'Switch to ' + (t === 'dark' ? 'light' : 'dark') + ' theme');
  }
  update();
  btn.addEventListener('click', function() {
    var cur = document.documentElement.getAttribute('data-theme') || 'light';
    var next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem('theme', next); } catch (e) {}
    update();
  });
})();
</script>"""


_COLLAPSE_SCRIPT = """\
<script>
(function() {
  var isMobile = window.matchMedia('(max-width: 600px)').matches;
  document.querySelectorAll('.comp').forEach(function(comp) {
    var header = comp.querySelector('.comp-header');
    if (!header) return;
    if (isMobile) comp.classList.remove('open');
    header.addEventListener('click', function() {
      comp.classList.toggle('open');
      comp.classList.toggle('user-closed', !comp.classList.contains('open'));
    });
  });
})();
</script>"""


_FILTER_SCRIPT = """\
<script>
(function() {
  var search = document.getElementById('filter-search');
  var type = document.getElementById('filter-type');
  var clear = document.getElementById('filter-clear');
  var empty = document.getElementById('filter-empty');
  if (!search) return;

  function apply() {
    var q = (search.value || '').trim().toLowerCase();
    var t = type ? type.value : 'all';
    var anyVisible = false;
    var filtering = q !== '' || t !== 'all';

    document.querySelectorAll('.comp').forEach(function(comp) {
      var compName = (comp.getAttribute('data-comp') || '').toLowerCase();
      var compMatchesText = !q || compName.indexOf(q) !== -1;
      var anyRowVisible = false;

      comp.querySelectorAll('[data-filter-row]').forEach(function(row) {
        var kind = row.getAttribute('data-filter-row');
        var teams = (row.getAttribute('data-teams') || '').toLowerCase();
        var outcome = row.getAttribute('data-outcome') || '';
        var typeOk = (t === 'all' ||
          (t === 'fixtures' && kind === 'fixture') ||
          (t === 'results' && kind === 'result') ||
          (t === outcome));
        var textOk = !q || compMatchesText || teams.indexOf(q) !== -1;
        var visible = typeOk && textOk;
        row.classList.toggle('row-hidden', !visible);
        if (visible) anyRowVisible = true;
      });

      comp.querySelectorAll('[data-section]').forEach(function(sec) {
        var rows = sec.querySelectorAll('[data-filter-row]');
        if (rows.length === 0) return;
        var shown = Array.prototype.some.call(rows, function(r) {
          return !r.classList.contains('row-hidden');
        });
        sec.style.display = shown ? '' : 'none';
      });

      var show;
      if (!filtering) {
        show = true;
      } else {
        show = compMatchesText || anyRowVisible;
      }
      comp.style.display = show ? '' : 'none';
      if (show) anyVisible = true;
    });

    if (empty) empty.classList.toggle('show', !anyVisible);
  }

  search.addEventListener('input', apply);
  if (type) type.addEventListener('change', apply);
  if (clear) clear.addEventListener('click', function() {
    search.value = '';
    if (type) type.value = 'all';
    apply();
  });
})();
</script>"""


_CALENDAR_SCRIPT = """\
<script>
(function() {
  var wrap = document.querySelector('.cal-wrap');
  if (!wrap) return;
  var months = wrap.querySelectorAll('.cal-month');
  var title = wrap.querySelector('.cal-title');
  var prev = wrap.querySelector('.cal-prev');
  var next = wrap.querySelector('.cal-next');
  var cur = 0;
  function show(idx) {
    if (idx < 0 || idx >= months.length) return;
    months[cur].classList.remove('active');
    cur = idx;
    months[cur].classList.add('active');
    title.textContent = months[cur].getAttribute('data-cal-title');
    prev.disabled = cur === 0;
    next.disabled = cur === months.length - 1;
  }
  prev.addEventListener('click', function() { show(cur - 1); });
  next.addEventListener('click', function() { show(cur + 1); });
  show(0);
})();
</script>"""


_SW_REGISTER = """\
<script>
if ('serviceWorker' in navigator) {
  window.addEventListener('load', function() {
    navigator.serviceWorker.register('{sw_path}').catch(function(){});
  });
}
</script>"""


def _collect_calendar_fixtures(comps, baselines):
    """Collect all upcoming Ballincollig fixtures across competitions.

    Returns a dict mapping date strings (YYYY-MM-DD) to lists of
    (time, opponent, comp_name, venue, is_postponed) tuples.
    """
    by_date = defaultdict(list)
    now = datetime.now()
    for comp_name, comp_config in comps:
        baseline = baselines.get(comp_name)
        if not baseline:
            continue
        for f in baseline.get("fixtures", {}).values():
            if not _is_ours(f):
                continue
            dt = _parse_date(f.get("date", ""))
            if dt == datetime.max:
                continue
            # Include today and future fixtures
            if dt.date() < now.date():
                continue
            home = f.get("home", "")
            away = f.get("away", "")
            is_home = CLUB_NAME.lower() in home.lower()
            opponent = away if is_home else home
            venue = f.get("venue", "").strip()
            time_str = f.get("time", "")
            postponed = bool(f.get("postponed"))
            date_key = dt.strftime("%Y-%m-%d")
            by_date[date_key].append((
                time_str, opponent, comp_name, venue, postponed
            ))
    # Sort each day's fixtures by time
    for date_key in by_date:
        by_date[date_key].sort(key=lambda x: x[0])
    return dict(by_date)


def _render_calendar(comps, baselines):
    """Render a month-view calendar with upcoming fixtures."""
    fixtures_by_date = _collect_calendar_fixtures(comps, baselines)
    if not fixtures_by_date:
        return ""

    today = datetime.now()
    # Determine which months to render (current + next 2)
    months = []
    y, m = today.year, today.month
    for _ in range(3):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    grids_html = ""
    for idx, (year, month) in enumerate(months):
        active = ' active' if idx == 0 else ''
        cal = calendar.monthcalendar(year, month)
        title = f"{month_names[month - 1]} {year}"
        grid = '<div class="cal-grid">'
        for day_name in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            grid += f'<div class="cal-hdr">{day_name}</div>'
        for week in cal:
            for day in week:
                if day == 0:
                    grid += '<div class="cal-cell empty"></div>'
                    continue
                date_key = f"{year}-{month:02d}-{day:02d}"
                is_today = (year == today.year and month == today.month
                            and day == today.day)
                day_fixtures = fixtures_by_date.get(date_key, [])
                cls = "cal-cell"
                if is_today:
                    cls += " today"
                if day_fixtures:
                    cls += " has-match"
                cell = f'<div class="{cls}"><span class="day-num">{day}</span>'
                for time_str, opponent, comp_name, venue, postponed in day_fixtures:
                    opp_short = escape(opponent)[:15]
                    if postponed:
                        label = f"PP: vs {opp_short}"
                    else:
                        label = f"{escape(time_str)} vs {opp_short}"
                    # Short comp name for tooltip
                    tooltip = escape(f"{comp_name}: {time_str} vs {opponent}")
                    if venue:
                        tooltip += escape(f" @ {venue}")
                    if postponed:
                        tooltip += " (Postponed)"
                    cell += f'<span class="cal-evt" title="{tooltip}">{label}</span>'
                cell += '</div>'
                grid += cell
        grid += '</div>'
        grids_html += (
            f'<div class="cal-month{active}" data-cal-idx="{idx}" '
            f'data-cal-title="{escape(title)}">'
            f'{grid}</div>'
        )

    return (
        '<div id="calendar" class="cal-wrap">'
        '<div class="cal-nav">'
        '<button type="button" class="cal-prev">&larr;</button>'
        f'<span class="cal-title">{escape(month_names[months[0][1] - 1])} '
        f'{months[0][0]}</span>'
        '<button type="button" class="cal-next">&rarr;</button>'
        '</div>'
        f'{grids_html}'
        '</div>'
    )


def _find_next_matches(comps, baselines):
    """Find the soonest upcoming Ballincollig fixture(s) across all competitions.

    Returns a list of (fixture, comp_name) tuples for all matches on the
    earliest upcoming date.  Returns an empty list if none found.
    """
    now = datetime.now()
    candidates = []
    for comp_name, comp_config in comps:
        baseline = baselines.get(comp_name)
        if not baseline:
            continue
        for f in baseline.get("fixtures", {}).values():
            if not _is_ours(f):
                continue
            if f.get("postponed"):
                continue
            dt = _parse_date(f.get("date", ""))
            if dt >= now or dt.date() == now.date():
                candidates.append((dt, f, comp_name))
    if not candidates:
        return []
    candidates.sort(key=lambda x: x[0])
    earliest_date = candidates[0][0].date()
    return [(f, cn) for dt, f, cn in candidates if dt.date() == earliest_date]


def _render_next_match(comps, baselines):
    """Render a 'Next Match' hero section showing the soonest fixture(s)."""
    matches = _find_next_matches(comps, baselines)
    if not matches:
        return ""
    cards = ""
    for fixture, comp_name in matches:
        home = escape(fixture.get("home", ""))
        away = escape(fixture.get("away", ""))
        date_str = escape(fixture.get("date", ""))
        time_str = escape(fixture.get("time", ""))
        venue = fixture.get("venue", "").strip()
        venue_html = (f'<span>📍 {escape(venue)}</span>' if venue else "")
        cards += (
            f'<div class="next-match-card">'
            f'<div class="next-match-date">{date_str}</div>'
            f'<div class="next-match-teams">{home} vs {away}</div>'
            f'<div class="next-match-meta">'
            f'<span>🕐 {time_str}</span>'
            f'{venue_html}'
            f'<span>🏆 {escape(comp_name)}</span>'
            f'</div>'
            f'</div>'
        )
    title = "Next Match" if len(matches) == 1 else "Next Matches"
    return f'<div class="next-match"><h2>{title}</h2>{cards}</div>'


def _compute_form(results, max_recent=5):
    """Compute recent form (W/D/L) per team from results.

    Returns {team_name: [(outcome, summary), ...]} oldest first,
    up to *max_recent* entries.  *summary* is e.g. "3-8 vs Nemo Rangers 1-5".
    """
    by_team = {}
    for r in results:
        # Handle conceded matches
        if r.get("conceded"):
            conceded_by = r.get("conceded_by", "unknown")
            dt = _parse_date(r.get("date", ""))
            home = r.get("home", "")
            away = r.get("away", "")
            date_str = r.get("date", "")
            for team, is_home in [(home, True), (away, False)]:
                if not team:
                    continue
                # Team loses if they conceded
                if conceded_by == "home" and is_home:
                    outcome = "L"
                elif conceded_by == "away" and not is_home:
                    outcome = "L"
                else:
                    outcome = "W"
                opp = away if is_home else home
                summary = f"{date_str}: Conceded vs {opp}"
                by_team.setdefault(team, []).append((dt, outcome, summary))
            continue

        hs = gaa_total(r.get("home_score", "0-0"))
        aws = gaa_total(r.get("away_score", "0-0"))
        dt = _parse_date(r.get("date", ""))
        home = r.get("home", "")
        away = r.get("away", "")
        home_score = r.get("home_score", "")
        away_score = r.get("away_score", "")
        date_str = r.get("date", "")
        for team, is_home in [(home, True), (away, False)]:
            if not team:
                continue
            ours = hs if is_home else aws
            theirs = aws if is_home else hs
            if ours > theirs:
                outcome = "W"
            elif ours < theirs:
                outcome = "L"
            else:
                outcome = "D"
            opp = away if is_home else home
            our_score = home_score if is_home else away_score
            opp_score = away_score if is_home else home_score
            summary = f"{date_str}: {our_score} vs {opp} {opp_score}"
            by_team.setdefault(team, []).append((dt, outcome, summary))

    form = {}
    for team, entries in by_team.items():
        entries.sort(key=lambda e: e[0], reverse=True)
        recent = [(o, s) for _, o, s in entries[:max_recent]]
        recent.reverse()  # oldest first (left to right)
        form[team] = recent
    return form


def _result_badge(match):
    # Handle conceded matches
    if match.get("conceded"):
        conceded_by = match.get("conceded_by", "unknown")
        is_home = CLUB_NAME.lower() in match.get("home", "").lower()
        if (conceded_by == "home" and is_home) or (conceded_by == "away" and not is_home):
            return '<span class="badge badge-loss">Conceded</span>'
        else:
            return '<span class="badge badge-win">Won (Conceded)</span>'
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
        time_str = ('<span class="badge badge-postponed">Postponed</span>'
                    if postponed else escape(f.get("time", "")))
        teams = f'{f.get("home", "")} {f.get("away", "")}'
        outcome = "postponed" if postponed else "upcoming"
        rows.append(
            f'<div class="fixture-row" data-filter-row="fixture" '
            f'data-teams="{escape(teams)}" data-outcome="{outcome}">'
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
        # Handle conceded matches
        if r.get("conceded"):
            conceded_by = r.get("conceded_by", "unknown")
            is_home = CLUB_NAME.lower() in r.get("home", "").lower()
            if (conceded_by == "home" and is_home) or (conceded_by == "away" and not is_home):
                outcome = "loss"
            else:
                outcome = "win"
            badge = _result_badge(r)
            teams = f'{r.get("home", "")} {r.get("away", "")}'
            rows.append(
                f'<div class="fixture-row" data-filter-row="result" '
                f'data-teams="{escape(teams)}" data-outcome="{outcome}">'
                f'<div class="fixture-date">{escape(r.get("date", ""))}</div>'
                f'<div class="fixture-teams">'
                f'{escape(r["home"])} v {escape(r["away"])} (Conceded by {escape(r.get("home") if conceded_by == "home" else r.get("away"))})'
                f'</div>'
                f'<div class="fixture-time">{badge}</div>'
                f'</div>'
            )
            continue

        hs = gaa_total(r.get("home_score", "0-0"))
        aws = gaa_total(r.get("away_score", "0-0"))
        is_home = CLUB_NAME.lower() in r.get("home", "").lower()
        ours = hs if is_home else aws
        theirs = aws if is_home else hs
        outcome = "win" if ours > theirs else "loss" if ours < theirs else "draw"
        badge = _result_badge(r)
        teams = f'{r.get("home", "")} {r.get("away", "")}'
        rows.append(
            f'<div class="fixture-row" data-filter-row="result" '
            f'data-teams="{escape(teams)}" data-outcome="{outcome}">'
            f'<div class="fixture-date">{escape(r.get("date", ""))}</div>'
            f'<div class="fixture-teams">'
            f'{escape(r["home"])} {escape(r.get("home_score",""))} - '
            f'{escape(r.get("away_score",""))} {escape(r["away"])}'
            f'</div>'
            f'<div class="fixture-time">{badge}</div>'
            f'</div>'
        )
    return '<div class="fixture-grid">' + "\n".join(rows) + '</div>'


def _render_table(table, form=None):
    """Render a league table as an HTML table."""
    if not table:
        return '<p class="empty">No league table available.</p>'
    form = form or {}
    badge_cls = {"W": "badge-win", "L": "badge-loss", "D": "badge-draw"}
    html = (
        '<table><thead><tr>'
        '<th>#</th><th>Team</th><th>Pld</th>'
        '<th class="hide-mobile">W</th><th class="hide-mobile">D</th><th class="hide-mobile">L</th>'
        '<th>PD</th><th>Pts</th><th>Form</th>'
        '</tr></thead><tbody>'
    )
    for row in table:
        team = row.get("team", "")
        cls = ' class="ours"' if CLUB_NAME.lower() in team.lower() else ""
        team_form = form.get(team, [])
        form_html = " ".join(
            f'<button class="form-btn badge {badge_cls.get(o, "")}" title="{escape(s)}">'
            f'{o}<span class="form-tip">{escape(s)}</span></button>'
            for o, s in team_form
        ) if team_form else '<span class="muted">-</span>'
        html += (
            f'<tr{cls}>'
            f'<td>{row.get("position","")}</td>'
            f'<td>{escape(team)}</td>'
            f'<td>{row.get("played","")}</td>'
            f'<td class="hide-mobile">{row.get("won","")}</td>'
            f'<td class="hide-mobile">{row.get("drawn","")}</td>'
            f'<td class="hide-mobile">{row.get("lost","")}</td>'
            f'<td>{row.get("pd","")}</td>'
            f'<td>{row.get("pts","")}</td>'
            f'<td class="form-cell">{form_html}</td>'
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
html[data-theme="dark"] {
  --primary: #4caf82;
  --primary-light: #1f3a2a;
  --bg: #121212;
  --card: #1e1e1e;
  --text: #e8e8e8;
  --muted: #9e9e9e;
  --border: #333;
}
html { color-scheme: light dark; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.5;
  max-width: 600px; margin: 0 auto; padding: 32px 16px;
  text-align: center;
}
.theme-toggle {
  position: absolute; top: 16px; right: 16px;
  background: transparent; border: 1px solid var(--border);
  color: var(--text); padding: 6px 10px; border-radius: 6px;
  cursor: pointer; font-size: 0.85em;
}
.theme-toggle:hover { background: var(--primary-light); }
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
.back-to-top {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--primary);
  color: white;
  border: none;
  cursor: pointer;
  font-size: 24px;
  display: none;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  z-index: 1000;
}
.back-to-top:hover {
  background: var(--primary-light);
  color: var(--primary);
}
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

    pwa_head = _pwa_head("")
    og_head = _og_head(
        f"{CLUB_NAME} GAA",
        f"Live fixtures, results and league tables for {CLUB_NAME} GAA.",
        "img/crest.gif",
    )

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{CLUB_NAME} GAA</title>
{_THEME_INIT}
{pwa_head}
{og_head}
<style>{_LANDING_CSS}</style>
</head>
<body>
<button class="theme-toggle" type="button" aria-label="Toggle theme">Dark</button>
<img src="img/crest.gif" alt="{CLUB_NAME} crest" class="crest">
<h1>{CLUB_NAME} GAA</h1>
<p class="subtitle">Competition Dashboards &mdash; updated {now}</p>
<div class="age-grid">
{links}
</div>
<button class="back-to-top" onclick="window.scrollTo({{top: 0, behavior: 'smooth'}})">↑</button>
<script>
window.addEventListener('scroll', function() {{
  const btn = document.querySelector('.back-to-top');
  if (window.scrollY > 200) {{
    btn.style.display = 'flex';
  }} else {{
    btn.style.display = 'none';
  }}
}});
</script>
{_THEME_TOGGLE_SCRIPT}
{_SW_REGISTER.replace("{sw_path}", "sw.js")}
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

    # Jump links (only when both sections exist)
    nav_html = ""
    if league_comps and champ_comps:
        nav_html = (
            '<nav class="section-nav">'
            '<a href="#calendar">Calendar</a>'
            '<a href="#league">League</a>'
            '<a href="#championship">Championship</a>'
            '</nav>'
        )

    filter_bar = """
<div class="filter-bar">
  <input id="filter-search" type="search" placeholder="Filter by team or competition…" aria-label="Filter">
  <select id="filter-type" aria-label="Filter type">
    <option value="all">All</option>
    <option value="fixtures">Fixtures only</option>
    <option value="results">Results only</option>
    <option value="win">Wins</option>
    <option value="loss">Losses</option>
    <option value="draw">Draws</option>
  </select>
  <button id="filter-clear" class="filter-clear" type="button">Clear</button>
</div>
<p id="filter-empty" class="filter-empty">No matches for your filter.</p>
"""

    next_match_html = _render_next_match(
        league_comps + champ_comps, baselines)

    calendar_html = _render_calendar(
        league_comps + champ_comps, baselines)

    content_html = ""
    for section_label, section_comps in [("League", league_comps), ("Championship", champ_comps)]:
        if not section_comps:
            continue
        anchor = section_label.lower()
        content_html += f'<h2 id="{anchor}">{section_label}</h2>'
        for comp_name, comp_config in section_comps:
            baseline = baselines.get(comp_name)
            url = competition_url(comp_config)
            # .open so desktop (non-user-closed) shows everything; mobile
            # script removes .open on small screens at load.
            content_html += (
                f'<div class="comp open" data-comp="{escape(comp_name)}">'
            )
            content_html += (
                f'<button class="comp-header" type="button" '
                f'aria-expanded="true">'
                f'<h3>{escape(comp_name)}</h3>'
                f'<span class="chev" aria-hidden="true">▾</span>'
                f'</button>'
            )
            content_html += '<div class="comp-body"><div class="card">'
            content_html += (
                f'<p class="muted" style="margin-bottom:8px">'
                f'<a href="{url}" target="_blank" rel="noopener">'
                f'View on rebelog.ie ↗</a></p>'
            )
            if baseline:
                fixtures = list(baseline.get("fixtures", {}).values())
                results = list(baseline.get("results", {}).values())
                table = baseline.get("table", [])

                content_html += '<div data-section="upcoming"><h3>Upcoming</h3>'
                content_html += _render_fixtures(fixtures)
                content_html += '</div>'
                content_html += '<div data-section="results"><h3>Results</h3>'
                content_html += _render_results(results)
                content_html += '</div>'
                content_html += '<div data-section="table"><h3>Table</h3>'
                content_html += _render_table(table, _compute_form(results))
                content_html += '</div>'
            else:
                content_html += '<p class="empty">No data yet — waiting for first monitor run.</p>'
            content_html += '</div></div></div>'

    pwa_head = _pwa_head("../")
    og_head = _og_head(
        f"{CLUB_NAME} GAA – {label}",
        f"{label} fixtures, results and league tables for {CLUB_NAME} GAA.",
        "../img/crest.gif",
    )

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{CLUB_NAME} GAA – {label}</title>
{_THEME_INIT}
{pwa_head}
{og_head}
<style>{_CSS}</style>
</head>
<body>
<div class="header">
  <a href="../"><img src="../img/crest.gif" alt="{CLUB_NAME} crest"></a>
  <h1><a href="../" style="text-decoration:none">{CLUB_NAME} GAA</a></h1>
  <div class="header-actions">
    <button class="theme-toggle" type="button" aria-label="Toggle theme">Dark</button>
  </div>
</div>
<p class="subtitle">{label} Dashboard &mdash; updated {now}</p>
{nav_html}
{next_match_html}
{calendar_html}
{filter_bar}
{content_html}
<button class="back-to-top" onclick="window.scrollTo({{top: 0, behavior: 'smooth'}})">↑</button>
<script>
window.addEventListener('scroll', function() {{
  const btn = document.querySelector('.back-to-top');
  if (window.scrollY > 200) {{
    btn.style.display = 'flex';
  }} else {{
    btn.style.display = 'none';
  }}
}});
</script>
{_THEME_TOGGLE_SCRIPT}
{_COLLAPSE_SCRIPT}
{_FILTER_SCRIPT}
{_CALENDAR_SCRIPT}
{_SW_REGISTER.replace("{sw_path}", "../sw.js")}
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


# ------------------------------------------------------------------
# Diff-only rebuild helpers
# ------------------------------------------------------------------

def _baseline_mtime(comp_name):
    """Return mtime of baseline JSON, or 0 if missing."""
    safe = comp_name.lower().replace(" ", "_").replace("/", "_")
    path = os.path.join(BASELINE_DIR, f"{safe}.json")
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def _latest_baseline_mtime(comps):
    """Return the max baseline mtime across a list of comp names."""
    mtimes = [_baseline_mtime(n) for n in comps]
    return max(mtimes) if mtimes else 0


def _output_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


# ------------------------------------------------------------------
# PWA assets
# ------------------------------------------------------------------

def _write_manifest():
    """Write a PWA manifest referencing the club crest."""
    manifest = {
        "name": f"{CLUB_NAME} GAA",
        "short_name": f"{CLUB_NAME}",
        "description": (
            f"Fixtures, results and league tables for {CLUB_NAME} GAA."
        ),
        "start_url": "./",
        "scope": "./",
        "display": "standalone",
        "background_color": "#f5f5f5",
        "theme_color": "#1a5632",
        "icons": [
            {
                "src": "img/crest.gif",
                "sizes": "128x128",
                "type": "image/gif",
                "purpose": "any",
            }
        ],
    }
    path = os.path.join(DASHBOARD_DIR, "manifest.webmanifest")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest written to {path}")


def _write_service_worker(version):
    """Write a minimal cache-first service worker.

    *version* is used as the cache name so a new build invalidates
    stale caches.
    """
    sw = f"""\
// Service worker for {CLUB_NAME} GAA dashboard
const CACHE = 'gaa-dash-{version}';
const CORE = ['./img/crest.gif', './manifest.webmanifest'];

self.addEventListener('install', (e) => {{
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting())
  );
}});

self.addEventListener('activate', (e) => {{
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))
    )).then(() => self.clients.claim())
  );
}});

self.addEventListener('fetch', (e) => {{
  if (e.request.method !== 'GET') return;
  const url = new URL(e.request.url);
  if (url.origin !== self.location.origin) return;

  const isHTML = e.request.mode === 'navigate' ||
    (e.request.headers.get('accept') || '').includes('text/html');

  if (isHTML) {{
    // Network-first for HTML so new deploys appear immediately.
    e.respondWith(
      fetch(e.request).then((res) => {{
        if (res && res.status === 200) {{
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
        }}
        return res;
      }}).catch(() => caches.match(e.request))
    );
    return;
  }}

  // Cache-first for static assets.
  e.respondWith(
    caches.match(e.request).then((cached) => {{
      const network = fetch(e.request).then((res) => {{
        if (res && res.status === 200) {{
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
        }}
        return res;
      }}).catch(() => cached);
      return cached || network;
    }})
  );
}});
"""
    path = os.path.join(DASHBOARD_DIR, "sw.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write(sw)
    print(f"Service worker written to {path}")


def generate(force=False):
    """Generate dashboard pages.

    By default, only regenerates pages whose baselines have changed
    since the last build (diff-only rebuild). Pass ``force=True`` or
    set env ``DASHBOARD_FORCE=1`` to always rebuild everything.
    """
    force = force or bool(os.environ.get("DASHBOARD_FORCE"))
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

    rebuilt = []
    # Generate a page per age group (diff-only)
    for ag_key in ["u13", "u14", "u15", "u16", "minor"]:
        comps = by_age.get(ag_key, [])
        if not comps:
            continue
        page_path = os.path.join(DASHBOARD_DIR, ag_key, "index.html")
        latest = _latest_baseline_mtime([n for n, _ in comps])
        out_mtime = _output_mtime(page_path)
        if not force and out_mtime > 0 and (latest == 0 or out_mtime >= latest):
            print(f"Skipping {ag_key}: up to date")
            continue
        _generate_age_group_page(ag_key, comps, baselines, now)
        rebuilt.append(ag_key)

    # Landing page: regenerate if any age group page was rebuilt or
    # landing doesn't exist yet.
    landing_path = os.path.join(DASHBOARD_DIR, "index.html")
    if force or rebuilt or not os.path.exists(landing_path):
        _generate_landing_page(set(by_age.keys()), now)
    else:
        print("Skipping landing page: no age-group changes")

    # Copy static assets (crest image etc.) — cheap, always do it so
    # manifest/sw.js referenced images exist.
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

    # PWA: always write manifest + service worker. sw.js cache version
    # is the largest baseline mtime so new data invalidates caches.
    _write_manifest()
    version = int(_latest_baseline_mtime(list(competitions.keys()))) or int(
        datetime.now().timestamp())
    _write_service_worker(version)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Generate dashboard HTML")
    ap.add_argument("--force", action="store_true",
                    help="Regenerate all pages even if baselines unchanged")
    args = ap.parse_args()
    generate(force=args.force)
