"""
Unit tests for rebelog_scraper.py — scrapes SportLomo fixture data
from rebelog.ie competition pages.
"""

import pytest
from bs4 import BeautifulSoup

from rebelog_scraper import _parse_fixtures, deduplicate_fixtures


# ---------------------------------------------------------------------------
# Sample SportLomo HTML fragments (matching rebelog.ie format)
# ---------------------------------------------------------------------------

FIXTURE_HTML = """\
<html><body>
<ul class="table-body fixtures-218166" data-date="17 Aug 2026"
    data-time="18:15" data-hometeam="Ballincollig" data-awayteam="Ballinora"
    data-homescore="" data-awayscore="" data-referee=""
    data-comment="ET if needed" data-venue="Ballinhassig"
    data-compname="Rebel Og Coiste Fe16 Premier 1 Hurling Championship Semi Finals/Final">
  <li>17/08/2026</li>
</ul>
<ul class="table-body fixtures-218166" data-date="17 Aug 2026"
    data-time="19:00" data-hometeam="Ballyhea Milford" data-awayteam="Midleton"
    data-homescore="" data-awayscore="" data-referee=""
    data-venue="Rathcormac"
    data-compname="Rebel Og Coiste Fe16 Premier 1 Hurling Championship Semi Finals/Final">
  <li>17/08/2026</li>
</ul>
</body></html>
"""

RESULT_HTML = """\
<html><body>
<ul class="table-body results" data-date="03 Aug 2026"
    data-time="15:00" data-hometeam="Glen Rovers" data-awayteam="Ballincollig"
    data-homescore="1-12" data-awayscore="0-15" data-referee="John Smith"
    data-venue="Glen Field"
    data-compname="Rebel Og Coiste Fe16 Premier 1 Hurling Championship">
  <li>03/08/2026</li><li>1-12 v 0-15</li>
</ul>
</body></html>
"""

MIXED_HTML = """\
<html><body>
<ul class="table-body fixtures-218279" data-date="24 Aug 2026"
    data-time="19:00" data-hometeam="Ballincollig" data-awayteam="Bishopstown"
    data-homescore="" data-awayscore="" data-referee=""
    data-venue="Ballincollig"
    data-compname="Rebel Og Coiste Fe 16 Premier 1 Football Championship Play-Off">
  <li>24/08/2026</li>
</ul>
<ul class="table-body results" data-date="10 Aug 2026"
    data-time="19:00" data-hometeam="Ballincollig" data-awayteam="Douglas"
    data-homescore="0-9" data-awayscore="1-14" data-referee=""
    data-venue="Ballincollig"
    data-compname="Rebel Og Coiste Fe16 Premier 1 Football Championship">
  <li>10/08/2026</li><li>0-9 v 1-14</li>
</ul>
<ul class="table-body fixtures-218279" data-date="24 Aug 2026"
    data-time="19:00" data-hometeam="Macroom" data-awayteam="Eire Og"
    data-homescore="" data-awayscore="" data-referee=""
    data-venue="Macroom"
    data-compname="Rebel Og Coiste Fe16 Premier 1 Football Championship Play Offs">
  <li>24/08/2026</li>
</ul>
</body></html>
"""


# ---------------------------------------------------------------------------
# _parse_fixtures
# ---------------------------------------------------------------------------

class TestParseFixtures:
    """Tests for parsing fixture data from HTML."""

    def test_extracts_ballincollig_fixture(self):
        soup = BeautifulSoup(FIXTURE_HTML, 'html.parser')
        fixtures = _parse_fixtures(soup, "Ballincollig")
        assert len(fixtures) == 1
        f = fixtures[0]
        assert f['home'] == 'Ballincollig'
        assert f['away'] == 'Ballinora'
        assert f['date'] == '17 Aug 2026'
        assert f['time'] == '18:15'
        assert f['venue'] == 'Ballinhassig'
        assert 'Semi Finals/Final' in f['competition']

    def test_skips_non_ballincollig(self):
        soup = BeautifulSoup(FIXTURE_HTML, 'html.parser')
        fixtures = _parse_fixtures(soup, "Ballincollig")
        # Only one fixture involves Ballincollig, not the Ballyhea/Midleton one
        assert len(fixtures) == 1
        assert fixtures[0]['home'] == 'Ballincollig'

    def test_skips_results(self):
        soup = BeautifulSoup(RESULT_HTML, 'html.parser')
        fixtures = _parse_fixtures(soup, "Ballincollig")
        assert len(fixtures) == 0

    def test_mixed_fixtures_and_results(self):
        soup = BeautifulSoup(MIXED_HTML, 'html.parser')
        fixtures = _parse_fixtures(soup, "Ballincollig")
        # Should get the play-off fixture but not the result
        assert len(fixtures) == 1
        assert fixtures[0]['away'] == 'Bishopstown'

    def test_away_fixture_included(self):
        html = """\
        <html><body>
        <ul class="table-body" data-date="19 Aug 2026"
            data-time="20:15" data-hometeam="Carrigaline" data-awayteam="Ballincollig"
            data-homescore="" data-awayscore="" data-referee=""
            data-venue="Carrigaline"
            data-compname="Fe18 Hurling Championship">
          <li>19/08/2026</li>
        </ul>
        </body></html>
        """
        soup = BeautifulSoup(html, 'html.parser')
        fixtures = _parse_fixtures(soup, "Ballincollig")
        assert len(fixtures) == 1
        assert fixtures[0]['home'] == 'Carrigaline'
        assert fixtures[0]['away'] == 'Ballincollig'

    def test_empty_page(self):
        soup = BeautifulSoup("<html><body></body></html>", 'html.parser')
        fixtures = _parse_fixtures(soup, "Ballincollig")
        assert fixtures == []


# ---------------------------------------------------------------------------
# deduplicate_fixtures
# ---------------------------------------------------------------------------

class TestDeduplicateFixtures:
    """Tests for deduplication of rebelog fixtures against gaacork fixtures."""

    def test_removes_duplicates(self):
        gaacork = [
            {'date': '17 Aug 2026', 'home': 'Ballincollig', 'away': 'Ballinora',
             'time': '18:15', 'venue': 'Ballinhassig', 'competition': 'Fe16 Hurling'},
        ]
        rebelog = [
            {'date': '17 Aug 2026', 'home': 'Ballincollig', 'away': 'Ballinora',
             'time': '18:15', 'venue': 'Ballinhassig',
             'competition': 'Rebel Og Coiste Fe16 Premier 1 Hurling Championship SF'},
        ]
        result = deduplicate_fixtures(gaacork, rebelog)
        assert len(result) == 0

    def test_keeps_new_fixtures(self):
        gaacork = [
            {'date': '17 Aug 2026', 'home': 'Ballincollig', 'away': 'Valley Rovers',
             'time': '11:00', 'venue': 'Ballincollig', 'competition': 'U12'},
        ]
        rebelog = [
            {'date': '24 Aug 2026', 'home': 'Ballincollig', 'away': 'Bishopstown',
             'time': '19:00', 'venue': 'Ballincollig',
             'competition': 'Fe16 Football Championship Play-Off'},
        ]
        result = deduplicate_fixtures(gaacork, rebelog)
        assert len(result) == 1
        assert result[0]['away'] == 'Bishopstown'

    def test_empty_rebelog(self):
        gaacork = [{'date': '17 Aug 2026', 'home': 'A', 'away': 'B'}]
        assert deduplicate_fixtures(gaacork, []) == []

    def test_empty_gaacork(self):
        rebelog = [
            {'date': '17 Aug 2026', 'home': 'Ballincollig', 'away': 'Ballinora',
             'time': '18:15', 'venue': 'X', 'competition': 'Y'},
        ]
        result = deduplicate_fixtures([], rebelog)
        assert len(result) == 1

    def test_case_insensitive_dedup(self):
        gaacork = [
            {'date': '17 aug 2026', 'home': 'ballincollig', 'away': 'BALLINORA'},
        ]
        rebelog = [
            {'date': '17 Aug 2026', 'home': 'Ballincollig', 'away': 'Ballinora',
             'time': '18:15', 'venue': 'X', 'competition': 'Y'},
        ]
        result = deduplicate_fixtures(gaacork, rebelog)
        assert len(result) == 0

    def test_swapped_home_away_dedup(self):
        """Fixture appears with home/away swapped between sources."""
        gaacork = [
            {'date': '19 Aug 2026', 'home': 'Ballincollig', 'away': 'Carrigaline'},
        ]
        rebelog = [
            {'date': '19 Aug 2026', 'home': 'Carrigaline', 'away': 'Ballincollig',
             'time': '20:15', 'venue': 'Carrigaline', 'competition': 'Fe18 HC'},
        ]
        result = deduplicate_fixtures(gaacork, rebelog)
        assert len(result) == 0
