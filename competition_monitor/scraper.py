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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


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
    def scrape(self, competition_url):
        """Scrape a competition page and return structured data.

        The SportLomo competition pages have tabs (Fixtures, Results,
        Table, etc.).  Selenium's .text returns empty for hidden
        elements, so we click each tab before extracting its data.

        Returns dict with keys: competition_name, competition_url,
        fixtures (list), results (list), table (list).
        """
        if not self.driver:
            print("No driver available")
            return None

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

            # Click the Fixtures tab, then extract upcoming fixtures
            self._click_tab("Fixtures")
            self._extract_matches(data, expect="fixtures")

            # Click the Results tab, then extract completed results
            self._click_tab("Results")
            self._extract_matches(data, expect="results")

            # Click the Table tab, then extract league table
            self._click_tab("Table")
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

    def _click_tab(self, label):
        """Click a tab on the competition page (Fixtures / Results / Table).

        SportLomo tabs are typically <a> or <li> elements inside a tab bar.
        """
        try:
            # Try several strategies to find the tab
            for selector in [
                f'a[href*="#{label.lower()}"]',
                f'li[data-tab="{label.lower()}"]',
                f'a.tab-link',
                f'li.tab',
                f'a',
                f'li',
            ]:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.text.strip().lower() == label.lower():
                        el.click()
                        time.sleep(1.5)
                        return True

            # Fallback: use JavaScript to click by link text
            self.driver.execute_script("""
                var tabs = document.querySelectorAll('a, li, button, span');
                for (var i = 0; i < tabs.length; i++) {
                    if (tabs[i].textContent.trim().toLowerCase() === arguments[0].toLowerCase()) {
                        tabs[i].click();
                        return true;
                    }
                }
                return false;
            """, label)
            time.sleep(1.5)
            return True
        except Exception as e:
            print(f"Could not click '{label}' tab: {e}")
            return False

    def _extract_matches(self, data, expect=None):
        """Find visible ul[data-date] elements on the current tab.

        Args:
            expect: "fixtures" or "results" — which tab we clicked.
                    When set, only visible elements are considered and
                    classification is guided by the tab context.
        """
        try:
            # Short wait — the tab content should already be loaded
            elements = WebDriverWait(self.driver, 8).until(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, 'ul[data-date]'))
            )
        except TimeoutException:
            if expect:
                print(f"No ul[data-date] on '{expect}' tab")
            return

        for el in elements:
            # Only process visible elements (the active tab's content)
            if not el.is_displayed():
                continue
            match = self._parse_match_element(el)
            if not match:
                continue
            if expect == "results":
                # On the Results tab: everything should be a result.
                # If scores weren't detected from .text, try JS textContent.
                if not match.get("home_score"):
                    text = self.driver.execute_script(
                        "return arguments[0].textContent || '';", el)
                    score_match = SCORE_RE.search(text)
                    if score_match:
                        match["home_score"] = score_match.group(1)
                        match["away_score"] = score_match.group(2)
                if match.get("home_score"):
                    data["results"].append(match)
            elif expect == "fixtures":
                # On the Fixtures tab: these are upcoming.
                if not match.get("home_score"):
                    data["fixtures"].append(match)
            else:
                # Legacy path: classify by presence of score
                if match.get("home_score"):
                    data["results"].append(match)
                else:
                    data["fixtures"].append(match)

    def _parse_match_element(self, el):
        """Parse a single fixture/result <ul> element."""
        home = el.get_attribute('data-hometeam') or ''
        away = el.get_attribute('data-awayteam') or ''
        if not home or not away:
            return None

        date_str = el.get_attribute('data-date') or ''
        time_str = el.get_attribute('data-time') or ''
        venue = el.get_attribute('data-venue') or ''
        comp = el.get_attribute('data-compname') or ''
        referee = (el.get_attribute('data-referee') or '').strip()

        # Check for score in the element text
        text = el.text or ''
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
        table_rows = []

        # The SportLomo league table is typically a <table> element.
        # Try several selectors.
        table_el = None
        for sel in ['table.standings', 'table.league-table',
                     'table.table', 'table']:
            try:
                candidates = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for cand in candidates:
                    header_text = cand.text.lower()
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
        """Parse a standard HTML <table> for league standings."""
        rows = []
        try:
            trs = table_el.find_elements(By.CSS_SELECTOR, 'tbody tr, tr')
            for i, tr in enumerate(trs):
                cells = tr.find_elements(By.CSS_SELECTOR, 'td, th')
                texts = [c.text.strip() for c in cells]
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
