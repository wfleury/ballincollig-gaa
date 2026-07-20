"""
Selenium-based scraper to execute JavaScript and get dynamically loaded fixtures
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import json
import re
import time
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from config import CLUB_NAME, CLUB_ID, TEAM_ID, RUGBY_INDICATORS

class SeleniumScraper:
    def __init__(self):
        self.setup_driver()
        
    def setup_driver(self):
        """Setup Chrome driver with headless options"""
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36')
        # Ignore SSL errors
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--disable-ssl-errors')
        # Enable browser logging to capture JS errors
        chrome_options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            # Override headless detection properties before any page loads.
            # CloudFront WAF bot-detection checks navigator.webdriver; if it
            # finds True the session never gets an aws-waf-token cookie and
            # subsequent admin-ajax.php calls return 403.
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.navigator.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                '''
            })
            print("Chrome driver initialized successfully")
        except Exception as e:
            print(f"Failed to initialize Chrome driver: {e}")
            self.driver = None
    
    def scrape_club_profile(self, club_id, team_id):
        """Scrape club profile with JavaScript execution"""
        
        if not self.driver:
            print("No driver available")
            return []
        
        url = f"https://gaacork.ie/clubprofile/{club_id}/?team_id={team_id}"
        
        try:
            print(f"Loading page: {url}")
            self.driver.get(url)
            
            # Wait for initial page load
            time.sleep(5)
            
            # Wait for JavaScript to execute and load fixtures
            print("Waiting for JavaScript to load fixtures...")
            
            # Method 1: Wait for the page's own JS to render fixtures
            try:
                fixture_elements = WebDriverWait(self.driver, 20).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'ul[data-date]'))
                )
                print(f"Found {len(fixture_elements)} fixture elements via CSS selector")
                return self.process_fixture_elements(fixture_elements)
            except TimeoutException:
                print("No ul[data-date] elements after 20s")

            # Method 2: Try JavaScript finder on existing DOM
            js_fixtures = self.execute_javascript_fixture_finder()
            if js_fixtures and (js_fixtures[0] or js_fixtures[1]):
                return js_fixtures

            # Method 3: In-page fetch — call admin-ajax.php from within the
            # page context.  CloudFront WAF blocks direct/external calls to
            # this endpoint from datacenter IPs (403), but same-origin fetch
            # with browser credentials succeeds because the browser carries
            # valid session cookies and Sec-Fetch-* headers.
            print("DOM rendering failed — trying in-page fetch...")
            ajax_url = (
                f"/wp-admin/admin-ajax.php?action=fixtures"
                f"&club_id={club_id}&competition_id="
                f"&team_id={team_id}&is_corkpps=0&displayResults="
            )
            for fetch_attempt in range(3):
                try:
                    fetch_result = self.driver.execute_async_script(f"""
                        var cb = arguments[arguments.length - 1];
                        fetch('{ajax_url}', {{credentials: 'include'}})
                            .then(function(r) {{
                                return r.text().then(function(t) {{
                                    cb({{status: r.status, html: t}});
                                }});
                            }})
                            .catch(function(e) {{ cb({{error: e.toString()}}); }});
                    """)
                    status = fetch_result.get('status') if fetch_result else None
                    length = len(fetch_result.get('html', '')) if fetch_result else 0
                    print(f"  In-page fetch attempt {fetch_attempt+1}/3: status={status}, length={length}")
                    if status == 200 and length > 1000:
                        result = self._parse_ajax_html(fetch_result['html'])
                        if result and (result[0] or result[1]):
                            return result
                except Exception as e:
                    print(f"  In-page fetch attempt {fetch_attempt+1} error: {e}")
                time.sleep(5 * (fetch_attempt + 1))

            # Method 4: Direct HTTP fallback using Selenium's cookies
            print("Trying direct HTTP fallback...")
            try:
                result = self._fetch_fixtures_http(club_id, team_id)
                if result and (result[0] or result[1]):
                    return result
            except Exception as e:
                print(f"  HTTP fallback error: {e}")

            # Dump browser console for diagnostics
            try:
                logs = self.driver.get_log('browser')
                errors = [l for l in logs if l.get('level') in ('SEVERE', 'WARNING')]
                print(f"=== Browser console: {len(logs)} entries, {len(errors)} errors/warnings ===")
                for entry in errors[:15]:
                    print(f"  [{entry['level']}] {entry['message'][:300]}")
            except Exception as e:
                print(f"  console log error: {e}")

            # Method 5: regex extraction from page source
            page_source = self.driver.page_source
            if CLUB_NAME in page_source:
                print(f"Found '{CLUB_NAME}' in page source, attempting regex extract...")
                return self.extract_from_page_source(page_source)
            
            print("No fixtures found after all methods")
            return []
            
        except Exception as e:
            print(f"Error scraping with Selenium: {e}")
            return []
    
    def process_fixture_elements(self, elements):
        """Process fixture elements found by Selenium"""

        fixtures = []
        results = []

        for element in elements:
            try:
                # Get data attributes
                home_team = element.get_attribute('data-hometeam') or ''
                away_team = element.get_attribute('data-awayteam') or ''
                date = element.get_attribute('data-date') or ''
                fixture_time = element.get_attribute('data-time') or ''
                venue = element.get_attribute('data-venue') or ''
                competition = element.get_attribute('data-compname') or ''

                # Check for result-specific attributes
                home_score = element.get_attribute('data-homescore') or ''
                away_score = element.get_attribute('data-awayscore') or ''
                match_status = element.get_attribute('data-status') or ''

                # DEBUG: Print first element with all attributes
                if len(fixtures) == 0:
                    print("=== FIRST ELEMENT ATTRIBUTES ===")
                    print(f"  home_team: {home_team}")
                    print(f"  away_team: {away_team}")
                    print(f"  date: {date}")
                    print(f"  time: {fixture_time}")
                    print(f"  venue: {venue}")
                    print(f"  competition: {competition}")
                    print(f"  home_score: {home_score}")
                    print(f"  away_score: {away_score}")
                    print(f"  match_status: {match_status}")
                    print("=== END ATTRIBUTES ===")

                # Check if club is involved
                if CLUB_NAME in home_team or CLUB_NAME in away_team:
                    # Filter out rugby and LGFA
                    exclude_indicators = RUGBY_INDICATORS + ['lgfa', 'ladies']
                    comp_lower = competition.lower()

                    if not any(indicator in comp_lower for indicator in exclude_indicators):
                        referee = element.get_attribute('data-referee') or ''

                        # Determine if this is a result (has scores) or fixture
                        if home_score and away_score:
                            results.append({
                                'home': home_team,
                                'away': away_team,
                                'date': date,
                                'home_score': home_score,
                                'away_score': away_score,
                                'competition': competition,
                                'venue': venue,
                                'status': match_status,
                                'referee': referee.strip()
                            })
                            print(f"Found RESULT: {date} - {home_team} {home_score} v {away_score} {away_team} ({competition})")
                        else:
                            fixtures.append({
                                'home': home_team,
                                'away': away_team,
                                'date': date,
                                'time': fixture_time,
                                'venue': venue,
                                'competition': competition,
                                'referee': referee.strip()
                            })
                            print(f"Found fixture: {date} - {home_team} vs {away_team} ({competition})")

            except Exception as e:
                print(f"Error processing element: {e}")
                continue

        print(f"Processed {len(fixtures)} {CLUB_NAME} fixtures")
        print(f"Processed {len(results)} {CLUB_NAME} results")
        return fixtures, results
    
    def execute_javascript_fixture_finder(self):
        """Execute JavaScript to find fixtures"""

        js_code = f"""
        // Look for fixture data in various places
        var fixtures = [];
        var results = [];

        // Check for elements with data attributes
        var elements = document.querySelectorAll('ul[data-date], ul[data-hometeam], ul[data-awayteam]');

        for (var i = 0; i < elements.length; i++) {{
            var el = elements[i];
            var homeTeam = el.getAttribute('data-hometeam') || '';
            var awayTeam = el.getAttribute('data-awayteam') || '';
            var homeScore = el.getAttribute('data-homescore') || '';
            var awayScore = el.getAttribute('data-awayscore') || '';

            if (homeTeam.indexOf('{CLUB_NAME}') !== -1 || awayTeam.indexOf('{CLUB_NAME}') !== -1) {{
                var item = {{
                    home: homeTeam,
                    away: awayTeam,
                    date: el.getAttribute('data-date') || '',
                    time: el.getAttribute('data-time') || '',
                    venue: el.getAttribute('data-venue') || '',
                    competition: el.getAttribute('data-compname') || ''
                }};

                if (homeScore && awayScore) {{
                    item.home_score = homeScore;
                    item.away_score = awayScore;
                    item.status = el.getAttribute('data-status') || '';
                    results.push(item);
                }} else {{
                    fixtures.push(item);
                }}
            }}
        }}

        return [fixtures, results];
        """

        try:
            result = self.driver.execute_script(js_code)
            print(f"JavaScript found {len(result[0])} fixtures and {len(result[1])} results")
            return result[0], result[1]
        except Exception as e:
            print(f"Error executing JavaScript: {e}")
            return [], []
    
    def extract_from_page_source(self, page_source):
        """Extract fixtures from page source using regex"""

        fixtures = []
        results = []

        # Look for data attributes in the HTML
        club_escaped = re.escape(CLUB_NAME)
        pattern = fr'data-hometeam="([^"]*{club_escaped}[^"]*)"|data-awayteam="([^"]*{club_escaped}[^"]*)"'
        matches = re.findall(pattern, page_source)

        for match in matches:
            home_team = match[0] if match[0] else ''
            away_team = match[1] if match[1] else ''

            # Try to extract the full fixture element
            if home_team or away_team:
                # Look for the surrounding ul element
                team_name = home_team or away_team
                ul_pattern = fr'<ul[^>]*data-(?:home|away)team="[^"]*{re.escape(team_name)}[^"]*"[^>]*>.*?</ul>'
                ul_match = re.search(ul_pattern, page_source, re.DOTALL)

                if ul_match:
                    ul_html = ul_match.group()

                    # Extract all data attributes
                    data_pattern = r'data-([^=]+)="([^"]*)"'
                    data_attrs = dict(re.findall(data_pattern, ul_html))

                    item = {
                        'home': data_attrs.get('hometeam', ''),
                        'away': data_attrs.get('awayteam', ''),
                        'date': data_attrs.get('date', ''),
                        'time': data_attrs.get('time', ''),
                        'venue': data_attrs.get('venue', ''),
                        'competition': data_attrs.get('compname', '')
                    }

                    # Check for result attributes
                    home_score = data_attrs.get('homescore', '')
                    away_score = data_attrs.get('awayscore', '')

                    if home_score and away_score:
                        item['home_score'] = home_score
                        item['away_score'] = away_score
                        item['status'] = data_attrs.get('status', '')
                        results.append(item)
                    else:
                        fixtures.append(item)

        print(f"Extracted {len(fixtures)} fixtures from page source")
        print(f"Extracted {len(results)} results from page source")
        return fixtures, results
    
    def _fetch_fixtures_http(self, club_id, team_id):
        """Fetch fixtures via direct HTTP using Selenium's CloudFront cookies.

        The in-page AJAX call to admin-ajax.php is blocked (403) on datacenter
        IPs by CloudFront WAF.  However, a plain *requests* call with the
        browser's session cookies (including aws-waf-token) can succeed.
        """
        # Grab cookies from the Selenium session
        selenium_cookies = self.driver.get_cookies()
        session = requests.Session()
        for c in selenium_cookies:
            session.cookies.set(c['name'], c['value'], domain=c.get('domain', ''))

        ajax_url = f"https://gaacork.ie/wp-admin/admin-ajax.php"
        params = {
            'action': 'fixtures',
            'club_id': str(club_id),
            'competition_id': '',
            'team_id': str(team_id),
            'is_corkpps': '0',
            'displayResults': '',
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
            'Referer': f'https://gaacork.ie/clubprofile/{club_id}/?team_id={team_id}',
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': '*/*',
        }

        resp = session.get(ajax_url, params=params, headers=headers,
                           timeout=30, verify=False)
        print(f"  HTTP fallback: status={resp.status_code}, length={len(resp.text)}")
        if resp.status_code != 200:
            print(f"  HTTP fallback: non-200 response")
            return [], []

        return self._parse_ajax_html(resp.text)

    def _parse_ajax_html(self, html):
        """Parse the fixture HTML returned by admin-ajax.php.

        The response contains <ul class="table-body"> elements whose data-*
        attributes hold match details (same attributes that Selenium reads
        via process_fixture_elements).
        """
        soup = BeautifulSoup(html, 'html.parser')
        fixtures = []
        results = []

        for ul in soup.select('ul.table-body'):
            try:
                home_team = ul.get('data-hometeam', '')
                away_team = ul.get('data-awayteam', '')

                if CLUB_NAME not in home_team and CLUB_NAME not in away_team:
                    continue

                competition = ul.get('data-compname', '')
                exclude_indicators = RUGBY_INDICATORS + ['lgfa', 'ladies']
                if any(ind in competition.lower() for ind in exclude_indicators):
                    continue

                home_score = ul.get('data-homescore', '')
                away_score = ul.get('data-awayscore', '')
                referee = (ul.get('data-referee', '') or '').strip()

                if home_score and away_score:
                    results.append({
                        'home': home_team,
                        'away': away_team,
                        'date': ul.get('data-date', ''),
                        'home_score': home_score,
                        'away_score': away_score,
                        'competition': competition,
                        'venue': ul.get('data-venue', ''),
                        'status': ul.get('data-status', ''),
                        'referee': referee,
                    })
                else:
                    fixtures.append({
                        'home': home_team,
                        'away': away_team,
                        'date': ul.get('data-date', ''),
                        'time': ul.get('data-time', ''),
                        'venue': ul.get('data-venue', ''),
                        'competition': competition,
                        'referee': referee,
                    })
            except Exception as e:
                print(f"  _parse_ajax_html: error on element: {e}")
                continue

        print(f"  Parsed from AJAX HTML: {len(fixtures)} fixtures, {len(results)} results")
        return fixtures, results

    def close(self):
        """Close the driver"""
        if self.driver:
            self.driver.quit()

if __name__ == "__main__":
    scraper = SeleniumScraper()

    if scraper.driver:
        try:
            fixtures, results = scraper.scrape_club_profile(CLUB_ID, TEAM_ID)

            print("\n=== Fixtures Found ===")
            for fixture in fixtures[:5]:  # Show first 5
                print(f"{fixture['date']}: {fixture['home']} vs {fixture['away']} ({fixture['competition']})")
            if len(fixtures) > 5:
                print(f"... and {len(fixtures) - 5} more fixtures")

            print(f"\nTotal fixtures: {len(fixtures)}")

            print("\n=== Results Found ===")
            for result in results[:5]:  # Show first 5
                print(f"{result['date']}: {result['home']} {result.get('home_score', '')} v {result.get('away_score', '')} {result['away']} ({result['competition']})")
            if len(results) > 5:
                print(f"... and {len(results) - 5} more results")

            print(f"\nTotal results: {len(results)}")

        finally:
            scraper.close()
    else:
        print("Could not initialize Selenium driver")
        print("You may need to install ChromeDriver:")
        print("1. Download ChromeDriver: https://chromedriver.chromium.org/")
        print("2. Add it to your PATH or place it in the project directory")
