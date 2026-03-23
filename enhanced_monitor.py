"""
Enhanced GAA Fixture Monitor with notifications and logging
"""

import csv
import io
import os
import json
from datetime import datetime, timedelta
from scraper import GAAClubScraper
from selenium_scraper import SeleniumScraper
import hashlib
import subprocess
import sys
import requests
from team_mapping import map_team_name as _map_team_name, determine_event_type as _determine_event_type
from config import (
    CLUB_NAME, CLUB_ID, TEAM_ID, COMPETITION_ID,
    HASH_FILE, LOG_FILE, FIXTURES_CSV, NTFY_TOPIC, NTFY_ICON,
    NTFY_FIXTURES_URL, team_ntfy_topic, team_fixtures_url,
)

class EnhancedFixtureMonitor:
    def __init__(self):
        self.scraper = GAAClubScraper()
        self.selenium_scraper = SeleniumScraper()
        self.hash_file = HASH_FILE
        self.log_file = LOG_FILE
        self.output_file = FIXTURES_CSV
        self.ntfy_topic = NTFY_TOPIC
        
    def log_message(self, message):
        """Log message to file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        
        print(message)
    
    def get_fixtures_data(self):
        """Get current fixtures data using Selenium for complete coverage"""
        try:
            # Use Selenium scraper for complete fixture coverage
            fixtures = self.selenium_scraper.scrape_club_profile(club_id=CLUB_ID, team_id=TEAM_ID)
            
            if fixtures:
                # Convert to CSV format using csv.writer for proper escaping
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["Date", "Time", "Venue", "Ground", "Referee",
                                 "Team", "Competition Name", "Your Club Name",
                                 "Opponent", "Event Type"])
                
                fixture_count = 0
                for fixture in fixtures:
                    # Process fixture data
                    home_team = fixture.get('home', '')
                    away_team = fixture.get('away', '')
                    date = fixture.get('date', '')
                    time_val = fixture.get('time', '')
                    venue = fixture.get('venue', '')
                    competition = fixture.get('competition', '')
                    
                    # Determine if club is home or away
                    if CLUB_NAME in home_team:
                        ground = 'Home'
                        opponent = away_team
                    elif CLUB_NAME in away_team:
                        ground = 'Away'
                        opponent = home_team
                    else:
                        continue  # Skip if club not found
                    
                    # Map team name and event type
                    team = self.map_team_name(competition)
                    event_type = self.determine_event_type(competition)
                    
                    # Format date
                    try:
                        dt = datetime.strptime(date, '%d %b %Y')
                        formatted_date = dt.strftime('%d/%m/%Y')
                    except (ValueError, TypeError):
                        formatted_date = date
                    
                    # Format time (add leading 0 if needed)
                    # 00:00 means fixture is cancelled/postponed
                    if time_val == '00:00' or time_val == '0:00':
                        time_val = 'Postponed'
                        event_type = 'Postponed'
                    elif time_val and len(time_val) == 4:
                        time_val = f'0{time_val}'
                    
                    referee = fixture.get('referee', '').strip()
                    if not referee:
                        referee = 'TBC (Pending)'
                    
                    writer.writerow([formatted_date, time_val, venue, ground, referee,
                                     team, competition, CLUB_NAME, opponent, event_type])
                    fixture_count += 1
                
                fixtures_text = output.getvalue().rstrip('\r\n')
                fixtures_hash = hashlib.sha256(fixtures_text.encode()).hexdigest()
                
                return {
                    'hash': fixtures_hash,
                    'text': fixtures_text,
                    'count': fixture_count,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                self.log_message("No fixtures found with Selenium")
                return None
                
        except Exception as e:
            self.log_message(f"Error with Selenium scraper: {e}")
            # Fallback to original scraper
            self.log_message("Falling back to original scraper...")
            club_data = self.scraper.scrape_club_profile(club_id=CLUB_ID, competition_id=COMPETITION_ID, team_id=TEAM_ID)
            
            if club_data and club_data.get('fixtures'):
                fixtures_text = club_data['fixtures']
                fixtures_hash = hashlib.sha256(fixtures_text.encode()).hexdigest()
                fixture_count = len(fixtures_text.split('\n')) - 1  # Subtract header
                
                return {
                    'hash': fixtures_hash,
                    'text': fixtures_text,
                    'count': fixture_count,
                    'timestamp': datetime.now().isoformat()
                }
            return None
    
    def load_previous_data(self):
        """Load previous fixture data"""
        if os.path.exists(self.hash_file):
            try:
                with open(self.hash_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, ValueError):
                self.log_message("WARNING: Corrupt hash file, treating as fresh run")
        return None
    
    def save_current_data(self, data):
        """Save current fixture data"""
        with open(self.hash_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def map_team_name(self, competition_name):
        """Map competition name to Ballincollig ClubZap team name."""
        return _map_team_name(competition_name)
    
    def determine_event_type(self, competition_name):
        """Determine event type from competition name."""
        return _determine_event_type(competition_name)
    
    def regenerate_csv(self, fixtures_text):
        """Regenerate the fixtures CSV"""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(fixtures_text)
            return True
        except Exception as e:
            self.log_message(f"Error saving CSV: {e}")
            return False
    
    def _sanitize_for_xml(self, text):
        """Escape text for safe XML/PowerShell interpolation."""
        text = str(text)
        # PowerShell escapes (backtick first, then dollar)
        text = text.replace("`", "``")
        text = text.replace("$", "`$")
        # XML escapes
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace("'", "&apos;")
        text = text.replace('"', "&quot;")
        return text
    
    def send_notification(self, title, message):
        """Send Windows toast + ntfy.sh mobile push notification"""
        safe_title = self._sanitize_for_xml(title)
        safe_message = self._sanitize_for_xml(message)
        
        # --- Windows toast notification ---
        try:
            ps_script = f'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml('<toast><visual><binding template="ToastGeneric"><text>{safe_title}</text><text>{safe_message}</text></binding></visual></toast>')

$toast = New-Object Windows.UI.Notifications.ToastNotification($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("GAA Monitor").Show($toast)
'''
            
            result = subprocess.run([
                'powershell', '-Command', ps_script
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                self.log_message("Windows toast notification sent")
            else:
                msg_script = f'''
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.MessageBox]::Show("{safe_message}", "{safe_title}", "OK", "Information")
'''
                subprocess.run([
                    'powershell', '-Command', msg_script
                ], timeout=10)
                self.log_message("Message box notification sent")
                
        except Exception as e:
            self.log_message(f"Failed to send Windows notification: {e}")
            print(f"\nNOTIFICATION: {title}")
            print(f"Message: {message}\n")
        
        # --- ntfy.sh mobile push notification ---
        self.send_ntfy(title, message)
    
    def send_ntfy(self, title, message, priority=None, topic=None, team_name=None):
        """Send push notification via ntfy.sh with Ballincollig crest and fixtures link"""
        if priority is None:
            priority = "low" if os.environ.get("NTFY_QUIET") else "high"
        target_topic = topic or self.ntfy_topic
        fixtures_url = team_fixtures_url(team_name) if team_name else NTFY_FIXTURES_URL
        try:
            resp = requests.post(
                f"https://ntfy.sh/{target_topic}",
                data=message.encode('utf-8'),
                headers={
                    "Title": title,
                    "Priority": priority,
                    "Icon": NTFY_ICON,
                    "Actions": f"view, View Fixtures, {fixtures_url}",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                self.log_message(f"ntfy.sh notification sent to {target_topic}")
            else:
                self.log_message(f"ntfy.sh returned status {resp.status_code} for {target_topic}")
        except Exception as e:
            self.log_message(f"Failed to send ntfy.sh notification to {target_topic}: {e}")
    
    def analyze_changes(self, old_text, new_text):
        """Analyze what changed between old and new fixtures"""
        old_lines = set(old_text.split('\n')) if old_text else set()
        new_lines = set(new_text.split('\n')) if new_text else set()
        
        added = new_lines - old_lines
        removed = old_lines - new_lines
        
        return {
            'added': list(added),
            'removed': list(removed),
            'added_count': len(added),
            'removed_count': len(removed)
        }
    
    def check_for_changes(self):
        """Main monitoring function"""
        self.log_message("Starting fixture check...")
        
        current_data = self.get_fixtures_data()
        if not current_data:
            self.log_message("ERROR: Could not retrieve current fixtures")
            return False
        
        previous_data = self.load_previous_data()
        
        if not previous_data:
            self.log_message("INFO: First run - initializing monitoring")
            self.regenerate_csv(current_data['text'])
            self.save_current_data(current_data)
            self.send_notification(
                "GAA Fixture Monitor Initialized",
                f"Monitoring started with {current_data['count']} fixtures"
            )
            return True
        
        if current_data['hash'] != previous_data['hash']:
            self.log_message("ALERT: FIXTURE CHANGES DETECTED!")
            
            # Analyze changes
            changes = self.analyze_changes(previous_data.get('text'), current_data['text'])
            
            self.log_message(f"INFO: Previous: {previous_data['count']} fixtures")
            self.log_message(f"INFO: Current: {current_data['count']} fixtures")
            self.log_message(f"INFO: Added: {changes['added_count']} fixtures")
            self.log_message(f"INFO: Removed: {changes['removed_count']} fixtures")
            
            # Regenerate CSV
            if self.regenerate_csv(current_data['text']):
                self.save_current_data(current_data)
                
                # Run ClubZap sync diff and build detailed notification
                diff_summary = ""
                team_changes = {}  # team_name -> list of description lines
                try:
                    from clubzap_sync import read_csv_fixtures, fixture_key, FULL_CSV, BASELINE_CSV, CHANGE_COLS
                    current = read_csv_fixtures(FULL_CSV)
                    baseline = read_csv_fixtures(BASELINE_CSV)
                    
                    new_items = []
                    changed_items = []
                    postponed_items = []
                    removed_items = []
                    
                    for key, row in current.items():
                        team = row.get('Team', 'Unknown')
                        if row.get('Time', '') == 'Postponed':
                            postponed_items.append(row)
                            team_changes.setdefault(team, []).append(
                                f"POSTPONED: {row['Date']} vs {row['Opponent']}")
                        elif key not in baseline:
                            new_items.append(row)
                            team_changes.setdefault(team, []).append(
                                f"NEW: {row['Date']} vs {row['Opponent']}")
                        else:
                            old_row = baseline[key]
                            row_changes = []
                            for col in CHANGE_COLS:
                                if old_row.get(col, '').strip() != row.get(col, '').strip():
                                    row_changes.append(f"  {col}: {row.get(col, '')}")
                            if row_changes:
                                changed_items.append((row, row_changes))
                                detail = ", ".join(
                                    f"{col}: {row.get(col, '')}" for col in CHANGE_COLS
                                    if old_row.get(col, '').strip() != row.get(col, '').strip()
                                )
                                team_changes.setdefault(team, []).append(
                                    f"CHANGED: {row['Date']} vs {row['Opponent']} ({detail})")
                    
                    for key, row in baseline.items():
                        if key not in current:
                            removed_items.append(row)
                            team = row.get('Team', 'Unknown')
                            team_changes.setdefault(team, []).append(
                                f"REMOVED: {row['Date']} vs {row['Opponent']}")
                    
                    parts = []
                    if new_items:
                        parts.append(f"NEW ({len(new_items)}):")
                        for r in new_items[:5]:
                            parts.append(f"  {r['Date']} {r['Team']} vs {r['Opponent']}")
                        if len(new_items) > 5:
                            parts.append(f"  ...and {len(new_items)-5} more")
                    
                    if changed_items:
                        parts.append(f"CHANGED ({len(changed_items)}):")
                        for r, ch in changed_items[:5]:
                            parts.append(f"  {r['Date']} {r['Team']} vs {r['Opponent']}")
                            for c in ch:
                                parts.append(f"    {c}")
                        if len(changed_items) > 5:
                            parts.append(f"  ...and {len(changed_items)-5} more")
                    
                    if postponed_items:
                        parts.append(f"POSTPONED ({len(postponed_items)}):")
                        for r in postponed_items:
                            parts.append(f"  {r['Date']} {r['Team']} vs {r['Opponent']}")
                    
                    if removed_items:
                        parts.append(f"REMOVED ({len(removed_items)}):")
                        for r in removed_items:
                            parts.append(f"  {r['Date']} {r['Team']} vs {r['Opponent']}")
                    
                    diff_summary = "\n".join(parts) if parts else "No ClubZap action needed"
                    
                    # Also run the full diff to generate CSV files
                    from clubzap_sync import diff_fixtures
                    self.log_message("Running ClubZap sync diff...")
                    diff_fixtures()
                except Exception as e:
                    self.log_message(f"ClubZap sync diff failed: {e}")
                    diff_summary = f"Fixtures: {previous_data['count']} -> {current_data['count']}"
                
                notification_msg = f"{CLUB_NAME} GAA Fixtures Update\n\n{diff_summary}"
                
                # Send main notification (all fixtures topic)
                self.send_notification(f"{CLUB_NAME} GAA - Fixture Changes", notification_msg)
                
                # Send per-team notifications so managers only get their team's changes
                for team_name, lines in team_changes.items():
                    team_topic = team_ntfy_topic(team_name)
                    team_msg = f"{CLUB_NAME} {team_name}\n\n" + "\n".join(lines)
                    self.send_ntfy(
                        f"{CLUB_NAME} {team_name} - Fixture Update",
                        team_msg,
                        topic=team_topic,
                        team_name=team_name,
                    )
                
                self.log_message("SUCCESS: Changes processed successfully")
                return True
            else:
                self.log_message("ERROR: Failed to process changes")
                return False
        else:
            self.log_message(f"INFO: No changes - {current_data['count']} fixtures")
            # Always regenerate CSV so it's available for artifacts and sync
            self.regenerate_csv(current_data['text'])
            # Send low-priority "all clear" to main topic
            all_clear_msg = (
                f"No fixture changes detected.\n"
                f"{current_data['count']} fixtures monitored.\n\n"
                "If you're seeing this for the first time — "
                "welcome! Notifications are working."
            )
            self.send_ntfy(
                f"{CLUB_NAME} GAA - All Clear",
                all_clear_msg,
                priority="low",
            )
            # Also send to each per-team topic so new team subscribers
            # get confirmation that their subscription is working
            from config import CLUBZAP_TEAM_IDS
            for team_name in CLUBZAP_TEAM_IDS:
                team_topic = team_ntfy_topic(team_name)
                self.send_ntfy(
                    f"{CLUB_NAME} {team_name} - All Clear",
                    f"No {team_name} fixture changes today.\n\n"
                    "If you're seeing this for the first time — "
                    "welcome! Notifications are working.",
                    priority="low",
                    topic=team_topic,
                    team_name=team_name,
                )
            return True

def main():
    monitor = EnhancedFixtureMonitor()
    try:
        monitor.check_for_changes()
    finally:
        monitor.selenium_scraper.close()

if __name__ == "__main__":
    main()
