"""
Unit tests for camogie_scraper.py — scrapes Foireann widget fixture cards
from corkcamogie.com.
"""

import pytest
from camogie_scraper import parse_fixture_cards, _parse_datetime, scrape_camogie_fixtures


# ---------------------------------------------------------------------------
# Sample Foireann HTML fragments
# ---------------------------------------------------------------------------

FIXTURE_CARD = """\
<article class="foireann-card"><div class="foireann-card-top">\
<div class="foireann-card-round">Round 1</div>\
<div class="foireann-card-date">Mon 30 Mar 2026 6:00 pm</div></div>\
<div class="foireann-card-body"><div class="foireann-matchup">\
<div class="foireann-team"><div class="foireann-team-logo-wrap">\
<img class="foireann-team-logo" alt="Ballincollig crest"></div>\
<div class="foireann-team-name">Ballincollig</div></div>\
<div class="foireann-match-centre"><div class="foireann-vs-badge">VS</div></div>\
<div class="foireann-team"><div class="foireann-team-logo-wrap">\
<img class="foireann-team-logo" alt="Charleville crest"></div>\
<div class="foireann-team-name">Charleville</div></div></div></div>\
<div class="foireann-card-footer">\
<div class="foireann-card-detail"><strong>Division:</strong> Premier Intermediate League 2026 - League Division 1</div>\
<div class="foireann-card-detail"><strong>Venue:</strong> Ballincollig GAA</div>\
</div></article>"""

RESULT_CARD = """\
<article class="foireann-card"><div class="foireann-card-top">\
<div class="foireann-card-round">Round 1</div>\
<div class="foireann-card-date">Mon 30 Mar 2026 6:00 pm</div></div>\
<div class="foireann-card-body"><div class="foireann-matchup">\
<div class="foireann-team"><div class="foireann-team-name">Ballincollig</div>\
<div class="foireann-score-badge">7-15</div></div>\
<div class="foireann-match-centre"><div class="foireann-vs-badge">VS</div></div>\
<div class="foireann-team"><div class="foireann-team-name">Charleville</div>\
<div class="foireann-score-badge">0-3</div></div></div></div>\
<div class="foireann-card-footer">\
<div class="foireann-card-detail"><strong>Division:</strong> Premier Intermediate League 2026 - League Division 1</div>\
</div></article>"""

AWAY_FIXTURE = """\
<article class="foireann-card"><div class="foireann-card-top">\
<div class="foireann-card-round">Round 2</div>\
<div class="foireann-card-date">Mon 6 Apr 2026 6:00 pm</div></div>\
<div class="foireann-card-body"><div class="foireann-matchup">\
<div class="foireann-team"><div class="foireann-team-name">Na Piarsaigh</div></div>\
<div class="foireann-match-centre"><div class="foireann-vs-badge">VS</div></div>\
<div class="foireann-team"><div class="foireann-team-name">Ballincollig</div></div>\
</div></div>\
<div class="foireann-card-footer">\
<div class="foireann-card-detail"><strong>Division:</strong> Premier Intermediate League 2026 - League Division 1</div>\
</div></article>"""

SECOND_TEAM_FIXTURE = """\
<article class="foireann-card"><div class="foireann-card-top">\
<div class="foireann-card-round">Round 1</div>\
<div class="foireann-card-date">Fri 3 Apr 2026 6:00 pm</div></div>\
<div class="foireann-card-body"><div class="foireann-matchup">\
<div class="foireann-team"><div class="foireann-team-name">Douglas 2</div></div>\
<div class="foireann-match-centre"><div class="foireann-vs-badge">VS</div></div>\
<div class="foireann-team"><div class="foireann-team-name">Ballincollig 2</div></div>\
</div></div>\
<div class="foireann-card-footer">\
<div class="foireann-card-detail"><strong>Division:</strong> 2026 Barry O&#039;Sullivan League - Group C</div>\
</div></article>"""

UNRELATED_FIXTURE = """\
<article class="foireann-card"><div class="foireann-card-top">\
<div class="foireann-card-round">Round 1</div>\
<div class="foireann-card-date">Mon 30 Mar 2026 6:00 pm</div></div>\
<div class="foireann-card-body"><div class="foireann-matchup">\
<div class="foireann-team"><div class="foireann-team-name">Douglas</div></div>\
<div class="foireann-match-centre"><div class="foireann-vs-badge">VS</div></div>\
<div class="foireann-team"><div class="foireann-team-name">Sarsfield</div></div>\
</div></div>\
<div class="foireann-card-footer">\
<div class="foireann-card-detail"><strong>Division:</strong> Premier Intermediate League 2026 - League Division 1</div>\
</div></article>"""


# ---------------------------------------------------------------------------
# _parse_datetime
# ---------------------------------------------------------------------------

class TestParseDatetime:
    """Tests for Foireann date/time string parsing."""

    def test_standard_format(self):
        d, t = _parse_datetime("Mon 30 Mar 2026 6:00 pm")
        assert d == "30 Mar 2026"
        assert t == "18:00"

    def test_am_time(self):
        d, t = _parse_datetime("Sat 5 Apr 2026 11:30 am")
        assert d == "05 Apr 2026"
        assert t == "11:30"

    def test_noon(self):
        d, t = _parse_datetime("Sun 6 Apr 2026 12:00 pm")
        assert d == "06 Apr 2026"
        assert t == "12:00"

    def test_midnight(self):
        d, t = _parse_datetime("Sun 6 Apr 2026 12:00 am")
        assert d == "06 Apr 2026"
        assert t == "00:00"

    def test_evening_time(self):
        d, t = _parse_datetime("Wed 1 Apr 2026 6:30 pm")
        assert d == "01 Apr 2026"
        assert t == "18:30"

    def test_whitespace_stripped(self):
        d, t = _parse_datetime("  Mon 30 Mar 2026 6:00 pm  ")
        assert d == "30 Mar 2026"
        assert t == "18:00"

    def test_fallback_unparseable(self):
        d, t = _parse_datetime("TBC")
        assert d == "TBC"
        assert t == ""


# ---------------------------------------------------------------------------
# parse_fixture_cards
# ---------------------------------------------------------------------------

class TestParseFixtureCards:
    """Tests for parsing Foireann fixture HTML into fixture dicts."""

    def test_single_home_fixture(self):
        fixtures = parse_fixture_cards(FIXTURE_CARD, "Ballincollig")
        assert len(fixtures) == 1
        fx = fixtures[0]
        assert fx["home"] == "Ballincollig"
        assert fx["away"] == "Charleville"
        assert fx["date"] == "30 Mar 2026"
        assert fx["time"] == "18:00"
        assert fx["venue"] == "Ballincollig GAA"
        assert "Premier Intermediate" in fx["competition"]

    def test_away_fixture(self):
        fixtures = parse_fixture_cards(AWAY_FIXTURE, "Ballincollig")
        assert len(fixtures) == 1
        fx = fixtures[0]
        assert fx["home"] == "Na Piarsaigh"
        assert fx["away"] == "Ballincollig"
        assert fx["date"] == "06 Apr 2026"

    def test_second_team_exact_match(self):
        """'Ballincollig 2' should match when filtering for 'Ballincollig 2'."""
        fixtures = parse_fixture_cards(SECOND_TEAM_FIXTURE, "Ballincollig 2")
        assert len(fixtures) == 1
        fx = fixtures[0]
        assert fx["away"] == "Ballincollig 2"
        assert fx["home"] == "Douglas 2"
        assert fx["competition"] == "2026 Barry O'Sullivan League - Group C"

    def test_second_team_broad_match(self):
        """'Ballincollig' (1st team name) also matches 'Ballincollig 2'."""
        fixtures = parse_fixture_cards(SECOND_TEAM_FIXTURE, "Ballincollig")
        assert len(fixtures) == 1

    def test_unrelated_fixture_excluded(self):
        fixtures = parse_fixture_cards(UNRELATED_FIXTURE, "Ballincollig")
        assert len(fixtures) == 0

    def test_multiple_cards_mixed(self):
        html = FIXTURE_CARD + UNRELATED_FIXTURE + AWAY_FIXTURE
        fixtures = parse_fixture_cards(html, "Ballincollig")
        assert len(fixtures) == 2
        homes = {f["home"] for f in fixtures}
        assert "Ballincollig" in homes
        assert "Na Piarsaigh" in homes

    def test_result_card_has_score_flag(self):
        fixtures = parse_fixture_cards(RESULT_CARD, "Ballincollig")
        assert len(fixtures) == 1
        assert fixtures[0]["_has_score"] is True

    def test_fixture_card_no_score_flag(self):
        fixtures = parse_fixture_cards(FIXTURE_CARD, "Ballincollig")
        assert len(fixtures) == 1
        assert fixtures[0]["_has_score"] is False

    def test_empty_html(self):
        assert parse_fixture_cards("", "Ballincollig") == []

    def test_html_without_cards(self):
        assert parse_fixture_cards("<html><body>Hello</body></html>", "Ballincollig") == []

    def test_html_entity_decoded(self):
        """HTML entities like &#039; should be decoded."""
        fixtures = parse_fixture_cards(SECOND_TEAM_FIXTURE, "Ballincollig")
        # &#039; -> '
        fx = fixtures[0]
        assert "O'Sullivan" in fx["competition"]

    def test_referee_defaults_empty(self):
        fixtures = parse_fixture_cards(FIXTURE_CARD, "Ballincollig")
        assert fixtures[0]["referee"] == ""

    def test_missing_venue(self):
        fixtures = parse_fixture_cards(AWAY_FIXTURE, "Ballincollig")
        assert fixtures[0]["venue"] == "Na Piarsaigh"

    def test_missing_venue_strips_team_number(self):
        fixtures = parse_fixture_cards(SECOND_TEAM_FIXTURE, "Ballincollig")
        assert fixtures[0]["venue"] == "Douglas"


# ---------------------------------------------------------------------------
# scrape_camogie_fixtures (with mocked HTTP)
# ---------------------------------------------------------------------------

class TestScrapeCamogieFixtures:
    """Integration-level tests using fake league config and mocked responses."""

    def test_returns_fixtures_with_team_mapping(self, monkeypatch):
        """Fixtures should carry the pre-mapped ClubZap team name."""
        fake_leagues = [
            {
                "url": "http://fake.test/league1/",
                "team": "BCC 2026 Senior Squad",
                "club_name": "Ballincollig",
                "competition": "Test Camogie League",
            },
        ]

        class FakeResponse:
            status_code = 200
            text = FIXTURE_CARD + AWAY_FIXTURE

            def raise_for_status(self):
                pass

        monkeypatch.setattr("camogie_scraper.requests.get", lambda *a, **kw: FakeResponse())

        fixtures = scrape_camogie_fixtures(leagues=fake_leagues)
        assert len(fixtures) == 2
        for fx in fixtures:
            assert fx["team"] == "BCC 2026 Senior Squad"
            assert fx["competition"] == "Test Camogie League"
            assert "_has_score" not in fx  # internal key stripped

    def test_deduplicates_fixture_and_result_cards(self, monkeypatch):
        """Same match appearing as fixture + result should appear only once."""
        fake_leagues = [
            {
                "url": "http://fake.test/league1/",
                "team": "BCC 2026 Senior Squad",
                "club_name": "Ballincollig",
                "competition": "Test League",
            },
        ]

        class FakeResponse:
            status_code = 200
            text = FIXTURE_CARD + RESULT_CARD  # same match, two cards

            def raise_for_status(self):
                pass

        monkeypatch.setattr("camogie_scraper.requests.get", lambda *a, **kw: FakeResponse())

        fixtures = scrape_camogie_fixtures(leagues=fake_leagues)
        assert len(fixtures) == 1

    def test_multiple_leagues_merged(self, monkeypatch):
        fake_leagues = [
            {
                "url": "http://fake.test/league1/",
                "team": "BCC 2026 Senior Squad",
                "club_name": "Ballincollig",
                "competition": "League 1",
            },
            {
                "url": "http://fake.test/league2/",
                "team": "BCC 2026 Junior Squad",
                "club_name": "Ballincollig 2",
                "competition": "League 2",
            },
        ]

        class FakeResp1:
            status_code = 200
            text = FIXTURE_CARD
            def raise_for_status(self): pass

        class FakeResp2:
            status_code = 200
            text = SECOND_TEAM_FIXTURE
            def raise_for_status(self): pass

        responses = iter([FakeResp1(), FakeResp2()])
        monkeypatch.setattr("camogie_scraper.requests.get", lambda *a, **kw: next(responses))

        fixtures = scrape_camogie_fixtures(leagues=fake_leagues)
        assert len(fixtures) == 2
        teams = {f["team"] for f in fixtures}
        assert teams == {"BCC 2026 Senior Squad", "BCC 2026 Junior Squad"}

    def test_http_failure_skips_league(self, monkeypatch):
        """If a league page fails to load, other leagues still work."""
        import requests as req

        fake_leagues = [
            {
                "url": "http://fake.test/broken/",
                "team": "BCC 2026 Senior Squad",
                "club_name": "Ballincollig",
                "competition": "Broken League",
            },
            {
                "url": "http://fake.test/working/",
                "team": "BCC 2026 Minor",
                "club_name": "Ballincollig",
                "competition": "Working League",
            },
        ]

        call_count = [0]

        def fake_get(*a, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                raise req.ConnectionError("simulated failure")

            class OK:
                status_code = 200
                text = FIXTURE_CARD
                def raise_for_status(self): pass
            return OK()

        monkeypatch.setattr("camogie_scraper.requests.get", fake_get)

        fixtures = scrape_camogie_fixtures(leagues=fake_leagues)
        assert len(fixtures) == 1
        assert fixtures[0]["team"] == "BCC 2026 Minor"

    def test_empty_leagues_returns_empty(self):
        assert scrape_camogie_fixtures(leagues=[]) == []
