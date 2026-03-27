"""
Selenium-based scraper for competition pages on rebelog.ie / gaacork.ie.

Extracts all fixtures, results (with scores), and the league table
for every team in a competition — not just Ballincollig.
"""

import re
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


SCORE_RE = re.compile(r'(\d+-\d+)\s*v\s*(\d+-\d+)', re.IGNORECASE)


class CompetitionScraper:
    """Scrape a single competition page for fixtures, results and table."""

    def __init__(self):
        self.driver = None
        self._setup_driver()

    # ------------------------------------------------------------------
    # Driver setup
    # ------------------------------------------------------------------
    def _setup_driver(self):
        opts = Options()
        opts.add_argument('--headless')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--window-size=1920,1080')
        opts.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        try:
            self.driver = webdriver.Chrome(options=opts)
            print("Competition scraper: Chrome driver ready")
        except Exception as e:
            print(f"Competition scraper: failed to init Chrome – {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @staticmethod
    def _comp_id_from_url(url):
        """Extract the numeric competition ID from a SportLomo URL."""
        m = re.search(r'/league/(\d+)', url)
        return m.group(1) if m else None

    def scrape(self, competition_url):
        """Scrape a competition page and return structured data.

        SportLomo pages embed all fixtures, results, and the league
        table in the DOM with distinguishing CSS classes, so we select
        elements directly rather than relying on tab clicks and
        ``is_displayed()``, which are unreliable in headless Chrome.

        Returns dict with keys: competition_name, competition_url,
        fixtures (list), results (list), table (list).
        """
        if not self.driver:
            print("No driver available")
            return None

        comp_id = self._comp_id_from_url(competition_url)

        data = {
            "competition_name": "",
            "competition_url": competition_url,
            "fixtures": [],
            "results": [],
            "table": [],
        }

        try:
            print(f"Loading: {competition_url}")
            self.driver.get(competition_url)
            time.sleep(3)

            # Extract competition name from the page heading
            data["competition_name"] = self._get_competition_name()

            # Use CSS class selectors to pick the right elements.
            # Fixture <ul>s carry class "fixtures-{comp_id}",
            # result  <ul>s carry class "results" (inside the results
            # tab container).
            if comp_id:
                fix_sel = f'ul.fixtures-{comp_id}[data-date]'
            else:
                fix_sel = 'ul.fixtures[data-date]'

            self._extract_matches_by_selector(
                data, fix_sel, kind="fixtures")

            # Results live inside a div whose class or id references
            # "results".  They have class "results" but NOT "fixtures-*".
            res_sel = 'ul.results[data-date]'
            self._extract_matches_by_selector(
                data, res_sel, kind="results")

            # League table
            data["table"] = self._extract_table()

            print(f"Scraped {len(data['fixtures'])} fixtures, "
                  f"{len(data['results'])} results, "
                  f"{len(data['table'])} table rows")

        except Exception as e:
            print(f"Error scraping {competition_url}: {e}")

        return data

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _get_competition_name(self):
        """Try to read the main heading of the competition page."""
        for sel in ['h2', 'h1.entry-title', 'h1']:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                text = el.text.strip()
                if text and 'menu' not in text.lower():
                    return text
            except Exception:
                continue
        return ""

    def _extract_matches_by_selector(self, data, selector, kind):
        """Extract fixture or result data from elements matching *selector*.

        Uses JavaScript ``getAttribute`` / ``textContent`` so that
        elements hidden by tab CSS are still readable.

        Args:
            data: dict to append to ("fixtures" or "results" key).
            selector: CSS selector for the <ul> match elements.
            kind: "fixtures" or "results".
        """
        try:
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            elements = []

        if not elements:
            print(f"No elements for '{kind}' ({selector})")
            return

        for el in elements:
            match = self._parse_match_element(el)
            if not match:
                continue
            if kind == "results":
                # Ensure we have scores — try JS textContent as fallback
                if not match.get("home_score"):
                    text = self.driver.execute_script(
                        "return arguments[0].textContent || '';", el)
                    score_match = SCORE_RE.search(text)
                    if score_match:
                        match["home_score"] = score_match.group(1)
                        match["away_score"] = score_match.group(2)
                if match.get("home_score"):
                    data["results"].append(match)
            else:
                if not match.get("home_score"):
                    data["fixtures"].append(match)

    def _parse_match_element(self, el):
        """Parse a single fixture/result <ul> element.

        Uses JavaScript getAttribute to reliably read data attributes
        even when the element is hidden by tab CSS.
        """
        get = lambda attr: self.driver.execute_script(
            "return arguments[0].getAttribute(arguments[1]) || '';", el, attr)

        home = get('data-hometeam')
        away = get('data-awayteam')
        if not home or not away:
            return None

        date_str = get('data-date')
        time_str = get('data-time')
        venue = get('data-venue')
        comp = get('data-compname')
        referee = get('data-referee').strip()

        # Check for score in the element text (JS textContent for hidden els)
        text = self.driver.execute_script(
            "return arguments[0].textContent || '';", el)
        score_match = SCORE_RE.search(text)

        match = {
            "home": home,
            "away": away,
            "date": date_str,
            "time": time_str,
            "venue": venue,
            "competition": comp,
            "referee": referee,
        }

        if score_match:
            match["home_score"] = score_match.group(1)
            match["away_score"] = score_match.group(2)
        elif time_str in ('0:00', '00:00'):
            match["postponed"] = True

        return match

    def _extract_table(self):
        """Extract the league table from the page.

        Returns a list of dicts with keys:
        position, team, played, won, drawn, lost, pf, pa, pd, pts
        """
        # The SportLomo league table is a <table class="league_table ...">
        # element.  It may be hidden by tab CSS, so we use JS to read it.
        table_el = None
        for sel in ['table.league_table', 'table.standings',
                     'table.league-table', 'table.table', 'table']:
            try:
                candidates = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for cand in candidates:
                    # Use JS textContent to check hidden tables
                    header_text = self.driver.execute_script(
                        "return arguments[0].textContent || '';",
                        cand).lower()
                    if 'pts' in header_text and ('pld' in header_text or
                                                  'team' in header_text):
                        table_el = cand
                        break
                if table_el:
                    break
            except Exception:
                continue

        if table_el:
            return self._parse_html_table(table_el)

        # Fallback: try parsing text blocks that look like a table
        return self._parse_table_from_text()

    def _parse_html_table(self, table_el):
        """Parse a standard HTML <table> for league standings.

        Uses JavaScript to read cell text so hidden tables are handled.
        """
        rows = []
        try:
            trs = table_el.find_elements(By.CSS_SELECTOR, 'tbody tr, tr')
            for i, tr in enumerate(trs):
                cells = tr.find_elements(By.CSS_SELECTOR, 'td, th')
                # Use JS textContent for each cell
                texts = [self.driver.execute_script(
                    "return (arguments[0].textContent || '').trim();", c)
                    for c in cells]
                if not texts or len(texts) < 4:
                    continue
                # Skip header rows
                if any(h in texts[0].lower() for h in ['pos', 'position',
                                                        'league', '#']):
                    continue
                row = self._cells_to_row(texts, i)
                if row:
                    rows.append(row)
        except Exception as e:
            print(f"Error parsing HTML table: {e}")
        return rows

    def _parse_table_from_text(self):
        """Fallback: scrape the full page text and look for table-like data.

        The SportLomo pages sometimes render tables as styled <div> grids
        rather than <table> elements.
        """
        rows = []
        try:
            # Find all elements that might be table rows
            # Look for divs/uls containing team names followed by numbers
            body_text = self.driver.find_element(By.TAG_NAME, 'body').text
            # Pattern: team name followed by numbers for Pld W D L PF PA PD Pts
            table_re = re.compile(
                r'^\s*(\d+)?\s*'             # optional position
                r'([A-ZÁÉÍÓÚa-záéíóú\s\'-]+?)\s+'  # team name
                r'(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+'  # Pld W D L
                r'(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+'    # PF PA PD
                r'(\d+)',                              # Pts
                re.MULTILINE
            )
            for m in table_re.finditer(body_text):
                pos = m.group(1) or ''
                team = m.group(2).strip()
                if team.lower() in ('team', ''):
                    continue
                rows.append({
                    "position": int(pos) if pos else len(rows) + 1,
                    "team": team,
                    "played": int(m.group(3)),
                    "won": int(m.group(4)),
                    "drawn": int(m.group(5)),
                    "lost": int(m.group(6)),
                    "pf": int(m.group(7)),
                    "pa": int(m.group(8)),
                    "pd": int(m.group(9)),
                    "pts": int(m.group(10)),
                })
        except Exception as e:
            print(f"Error parsing table from text: {e}")
        return rows

    def _cells_to_row(self, texts, idx):
        """Convert a list of cell texts to a table row dict."""
        try:
            # Determine offset: first cell might be position number or team
            offset = 0
            if texts[0].isdigit():
                offset = 1

            team = texts[offset] if offset < len(texts) else ''
            if not team or team.lower() in ('team', ''):
                return None

            nums = []
            for t in texts[offset + 1:]:
                t = t.strip().lstrip('+')
                if t.lstrip('-').isdigit():
                    nums.append(int(t))

            # Expect at least: Pld W D L ... Pts (minimum 5 numbers)
            if len(nums) < 5:
                return None

            return {
                "position": int(texts[0]) if texts[0].isdigit() else idx,
                "team": team,
                "played": nums[0],
                "won": nums[1],
                "drawn": nums[2],
                "lost": nums[3],
                "pf": nums[4] if len(nums) > 4 else 0,
                "pa": nums[5] if len(nums) > 5 else 0,
                "pd": nums[6] if len(nums) > 6 else 0,
                "pts": nums[7] if len(nums) > 7 else nums[-1],
            }
        except (IndexError, ValueError):
            return None


if __name__ == "__main__":
    from competition_monitor.config import COMPETITIONS, competition_url
    scraper = CompetitionScraper()
    try:
        for name, comp in COMPETITIONS.items():
            url = competition_url(comp)
            print(f"\n=== {name} ===")
            data = scraper.scrape(url)
            if data:
                print(f"Competition: {data['competition_name']}")
                print(f"Fixtures: {len(data['fixtures'])}")
                for f in data['fixtures'][:3]:
                    p = " [POSTPONED]" if f.get('postponed') else ""
                    print(f"  {f['date']} {f['time']} "
                          f"{f['home']} vs {f['away']}{p}")
                print(f"Results: {len(data['results'])}")
                for r in data['results']:
                    print(f"  {r['date']} {r['home']} {r['home_score']} - "
                          f"{r['away_score']} {r['away']}")
                print(f"Table: {len(data['table'])} teams")
                for t in data['table']:
                    print(f"  {t['position']}. {t['team']} "
                          f"({t['pts']} pts, {t['played']} pld)")
    finally:
        scraper.close()
