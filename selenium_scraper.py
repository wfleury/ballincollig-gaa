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
            
            # Retry with increasing waits (cloud environments are slower)
            for attempt in range(3):
                wait_time = 15 + (attempt * 10)  # 15s, 25s, 35s
                print(f"Attempt {attempt + 1}/3 (waiting up to {wait_time}s)...")
                
                # Method 1: Wait for fixture elements with data-date
                try:
                    fixture_elements = WebDriverWait(self.driver, wait_time).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'ul[data-date]'))
                    )
                    print(f"Found {len(fixture_elements)} fixture elements via CSS selector")
                    return self.process_fixture_elements(fixture_elements)
                except TimeoutException:
                    print(f"No fixture elements found on attempt {attempt + 1}")
                
                # Method 2: Try JavaScript finder
                js_fixtures = self.execute_javascript_fixture_finder()
                if js_fixtures and (js_fixtures[0] or js_fixtures[1]):
                    return js_fixtures
                
                # Scroll page to trigger any lazy loading
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(2)
            
            # Method 3: Look for elements with 'fixtures' in class
            try:
                fixture_elements = self.driver.find_elements(By.CSS_SELECTOR, 'ul[class*="fixtures"]')
                if fixture_elements:
                    print(f"Found {len(fixture_elements)} fixture elements via class name")
                    return self.process_fixture_elements(fixture_elements)
            except Exception:
                print("No fixture elements found with 'fixtures' in class")

            # Method 4: Look for any table-like structures
            try:
                fixture_elements = self.driver.find_elements(By.CSS_SELECTOR, 'ul.table-body')
                if fixture_elements:
                    print(f"Found {len(fixture_elements)} table-body elements")
                    return self.process_fixture_elements(fixture_elements)
            except Exception:
                print("No table-body elements found")
            
            # Method 5: Check page source after JavaScript execution
            print("Checking page source after JavaScript execution...")
            page_source = self.driver.page_source

            # Diagnostics: page size, iframes, SportLomo, console errors
            print(f"=== PAGE SOURCE LENGTH: {len(page_source)} chars ===")

            # Check for iframes
            try:
                iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
                print(f"=== Found {len(iframes)} iframes ===")
                for i, iframe in enumerate(iframes[:10]):
                    src = iframe.get_attribute('src') or '(no src)'
                    print(f"  iframe[{i}]: {src[:200]}")
            except Exception as e:
                print(f"  iframe check error: {e}")

            # Check for SportLomo / fixture widget scripts
            try:
                sportlomo_hits = self.driver.execute_script("""
                    var scripts = document.querySelectorAll('script[src]');
                    var hits = [];
                    for (var s of scripts) {
                        var src = s.getAttribute('src') || '';
                        if (src.match(/sportlomo|fixture|widget|club.*profile/i))
                            hits.push(src);
                    }
                    return hits;
                """)
                print(f"=== SportLomo-related scripts: {len(sportlomo_hits)} ===")
                for h in sportlomo_hits:
                    print(f"  {h}")
            except Exception as e:
                print(f"  script check error: {e}")

            # Check for data-date anywhere in full page source
            import re
            data_date_count = len(re.findall(r'data-date', page_source))
            data_hometeam_count = len(re.findall(r'data-hometeam', page_source))
            print(f"=== data-date occurrences in full source: {data_date_count} ===")
            print(f"=== data-hometeam occurrences in full source: {data_hometeam_count} ===")

            # Check for any fixture-related container
            try:
                containers = self.driver.execute_script("""
                    var results = [];
                    var all = document.querySelectorAll('[id*="fixture"], [id*="result"], [class*="fixture"], [class*="result"], [id*="sportlomo"], [class*="sportlomo"]');
                    for (var el of all) results.push(el.tagName + '#' + el.id + '.' + el.className.substring(0, 80));
                    return results.slice(0, 20);
                """)
                print(f"=== Fixture/result containers: {len(containers)} ===")
                for c in containers:
                    print(f"  {c}")
            except Exception as e:
                print(f"  container check error: {e}")

            # Dump browser console logs (JS errors, network failures)
            try:
                logs = self.driver.get_log('browser')
                errors = [l for l in logs if l.get('level') in ('SEVERE', 'WARNING')]
                print(f"=== Browser console: {len(logs)} entries, {len(errors)} errors/warnings ===")
                for entry in errors[:30]:
                    print(f"  [{entry['level']}] {entry['message'][:300]}")
            except Exception as e:
                print(f"  console log error: {e}")

            # Look for club name in the page source
            if CLUB_NAME in page_source:
                print(f"Found '{CLUB_NAME}' in page source, attempting to extract...")
                return self.extract_from_page_source(page_source)
            
            print("No fixtures found after JavaScript execution")
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
