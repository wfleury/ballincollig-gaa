"""
Results Scraper for GAA Cork

Extracts match results from gaacork.ie and prepares them for ClubZap sync.
Unlike fixtures which can be bulk uploaded, results must be entered individually.
"""

import csv
import os
import json
from datetime import datetime
from selenium_scraper import SeleniumScraper
from team_mapping import map_team_name, determine_event_type
from gaa_utils import gaa_total
from config import CLUB_NAME, CLUB_ID, TEAM_ID


class ResultsScraper:
    def __init__(self):
        self.selenium_scraper = SeleniumScraper()
        
    def get_results_data(self):
        """Get current results data using Selenium scraper."""
        try:
            fixtures, results = self.selenium_scraper.scrape_club_profile(club_id=CLUB_ID, team_id=TEAM_ID)
            print(f"Found {len(results)} results from GAA Cork")
            return self.process_results(results)
        except Exception as e:
            print(f"Error scraping results: {e}")
            return []
    
    def process_results(self, raw_results):
        """Process raw results into standardized format for ClubZap sync."""
        processed_results = []
        
        for result in raw_results:
            home_team = result.get('home', '')
            away_team = result.get('away', '')
            date = result.get('date', '')
            home_score = result.get('home_score', '')
            away_score = result.get('away_score', '')
            competition = result.get('competition', '')
            venue = result.get('venue', '')
            referee = result.get('referee', '').strip()
            status = result.get('status', '')
            
            # Skip if club not involved
            if CLUB_NAME not in home_team and CLUB_NAME not in away_team:
                continue
                
            # Skip if no scores (shouldn't happen for results, but safety check)
            if not home_score or not away_score:
                continue
            
            # Determine if club is home or away
            if CLUB_NAME in home_team:
                ground = 'Home'
                opponent = away_team
                our_score = home_score
                opponent_score = away_score
            else:
                ground = 'Away'
                opponent = home_team
                our_score = away_score
                opponent_score = home_score
            
            # Map team name and event type
            team = map_team_name(competition)
            event_type = determine_event_type(competition)
            
            # Format date for consistency
            try:
                dt = datetime.strptime(date, '%d %b %Y')
                formatted_date = dt.strftime('%d/%m/%Y')
            except (ValueError, TypeError):
                formatted_date = date
            
            # Calculate total scores for result determination
            our_total = gaa_total(our_score)
            opponent_total = gaa_total(opponent_score)
            
            if our_total > opponent_total:
                result_outcome = 'Win'
            elif our_total < opponent_total:
                result_outcome = 'Loss'
            else:
                result_outcome = 'Draw'
            
            processed_result = {
                'date': formatted_date,
                'team': team,
                'competition': competition,
                'opponent': opponent,
                'ground': ground,
                'venue': venue,
                'referee': referee or 'TBC',
                'home_team': home_team,
                'away_team': away_team,
                'home_score': home_score,
                'away_score': away_score,
                'our_score': our_score,
                'opponent_score': opponent_score,
                'our_total': our_total,
                'opponent_total': opponent_total,
                'result': result_outcome,
                'status': status,
                'event_type': event_type
            }
            
            processed_results.append(processed_result)
            print(f"Processed result: {formatted_date} - {team} {our_score} v {opponent_score} {opponent} ({result_outcome})")
        
        return processed_results
    
    def save_results_json(self, results, filepath="current_results.json"):
        """Save results to JSON file for tracking and sync."""
        results_data = {
            'timestamp': datetime.now().isoformat(),
            'count': len(results),
            'results': results
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        
        print(f"Saved {len(results)} results to {filepath}")
        return filepath
    
    def generate_result_key(self, result):
        """Generate a unique key for a result based on date, teams, and competition."""
        return f"{result['date']}|{result['team']}|{result['opponent']}|{result['competition']}"
    
    def close(self):
        """Close the selenium scraper."""
        if self.selenium_scraper:
            self.selenium_scraper.close()


def main():
    """Test the results scraper."""
    scraper = ResultsScraper()
    try:
        results = scraper.get_results_data()
        if results:
            scraper.save_results_json(results)
            print(f"\nSummary:")
            print(f"Total results: {len(results)}")
            
            # Group by outcome
            wins = [r for r in results if r['result'] == 'Win']
            losses = [r for r in results if r['result'] == 'Loss']
            draws = [r for r in results if r['result'] == 'Draw']
            
            print(f"Wins: {len(wins)}")
            print(f"Losses: {len(losses)}")
            print(f"Draws: {len(draws)}")
            
            # Show recent results
            print(f"\nRecent results:")
            for result in results[-5:]:
                print(f"  {result['date']} - {result['team']} {result['our_score']} v {result['opponent_score']} {result['opponent']} ({result['result']})")
        else:
            print("No results found")
    finally:
        scraper.close()


if __name__ == "__main__":
    main()