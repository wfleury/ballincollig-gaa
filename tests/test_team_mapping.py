"""
Unit tests for team_mapping.py — maps GAA Cork competition names to ClubZap team names.
"""

import pytest
from team_mapping import map_team_name, determine_event_type


# ---------------------------------------------------------------------------
# map_team_name
# ---------------------------------------------------------------------------

class TestMapTeamName:
    """Tests for mapping competition names to ClubZap team names."""

    # -- Underage (single GAA team name regardless of code) --

    @pytest.mark.parametrize("comp,expected", [
        ("Fe12 Football League Div 1", "U12 GAA"),
        ("Fe12 Hurling League Div 2", "U12 GAA"),
    ])
    def test_fe12(self, comp, expected):
        assert map_team_name(comp) == expected

    @pytest.mark.parametrize("comp,expected", [
        ("Fe13 Football League", "U13 GAA"),
        ("Fe13 Hurling Championship", "U13 GAA"),
    ])
    def test_fe13(self, comp, expected):
        assert map_team_name(comp) == expected

    @pytest.mark.parametrize("comp,expected", [
        ("Fe14 Football League", "U14 GAA"),
        ("Fe14 Hurling League", "U14 GAA"),
    ])
    def test_fe14(self, comp, expected):
        assert map_team_name(comp) == expected

    @pytest.mark.parametrize("comp,expected", [
        ("Fe15 Football League", "U15 GAA"),
        ("Fe15 Hurling Championship", "U15 GAA"),
    ])
    def test_fe15(self, comp, expected):
        assert map_team_name(comp) == expected

    @pytest.mark.parametrize("comp,expected", [
        ("Fe16 Football League Div 1", "U16 GAA"),
        ("Fe16 Hurling League Div 2", "U16 GAA"),
    ])
    def test_fe16(self, comp, expected):
        assert map_team_name(comp) == expected

    # -- Minor (Fe18 splits by code) --

    def test_fe18_football(self):
        assert map_team_name("Fe18 Football League Div 1") == "Minor Football GAA"

    def test_fe18_hurling(self):
        assert map_team_name("Fe18 Hurling League Div 1") == "Minor Hurling GAA"

    def test_fe18_default_is_football(self):
        # If neither football nor hurling keyword, defaults to football
        assert map_team_name("Fe18 Some League") == "Minor Football GAA"

    # -- County Senior Leagues --

    def test_mccarthy_insurance_league(self):
        assert map_team_name("McCarthy Insurance Premier SFC") == "Senior Football"

    def test_mccarthy_shorthand(self):
        assert map_team_name("McCarthy Cup Rd 1") == "Senior Football"

    def test_red_fm_league(self):
        assert map_team_name("Red FM Hurling League") == "Premier Inter Hurling"

    # -- County Championships --

    def test_psfc(self):
        assert map_team_name("PSFC Round 1") == "Senior Football"

    def test_premier_senior_football(self):
        assert map_team_name("Premier Senior Football Championship") == "Senior Football"

    def test_senior_fc(self):
        assert map_team_name("Senior FC Round 2") == "Senior Football"

    def test_pihc(self):
        assert map_team_name("PIHC Quarter Final") == "Premier Inter Hurling"

    def test_premier_intermediate_hurling(self):
        assert map_team_name("Premier Intermediate Hurling Championship") == "Premier Inter Hurling"

    def test_premier_ihc(self):
        assert map_team_name("Premier IHC Semi Final") == "Premier Inter Hurling"

    # -- Divisional Junior Leagues (AOS Security sponsor) --

    def test_aos_football_default(self):
        assert map_team_name("AOS Security FL Div 1") == "Junior A Football"

    def test_aos_hurling_default(self):
        assert map_team_name("AOS Security HL Div 1") == "Junior A Hurling"

    def test_aos_div4_football(self):
        assert map_team_name("AOS Security FL Div 4") == "Junior B Football"

    def test_aos_div5_hurling(self):
        assert map_team_name("AOS Security HL Div 5") == "Junior B Hurling"

    def test_aos_div3_football(self):
        assert map_team_name("AOS Security FL Div 3") == "Junior A Football"

    def test_aos_div3_hurling(self):
        assert map_team_name("AOS Security HL Div 3") == "Junior B Hurling"

    # -- Muskerry sponsors --

    def test_cumnor_hurling(self):
        assert map_team_name("Cumnor Hurling League") == "Junior A Hurling"

    def test_eph_football_div1(self):
        assert map_team_name("EPH Football Div 1") == "Junior A Football"

    def test_eph_football_div2(self):
        assert map_team_name("EPH Division 2 Football") == "Junior B Football"

    def test_erneside_hurling(self):
        assert map_team_name("Erneside Hurling League") == "Junior B Hurling"

    # -- Division-number leagues --

    def test_division_1_fl(self):
        assert map_team_name("Division 1 FL") == "Senior Football"

    def test_division_2_fl(self):
        assert map_team_name("Division 2 FL") == "Junior A Football"

    def test_division_3_fl(self):
        assert map_team_name("Division 3 FL") == "Junior B Football"

    def test_division_1_hl(self):
        assert map_team_name("Division 1 HL") == "Senior Hurling"

    def test_division_2_hl(self):
        assert map_team_name("Division 2 HL") == "Junior A Hurling"

    def test_division_3_hl(self):
        assert map_team_name("Division 3 HL") == "Junior B Hurling"

    # -- Named junior grades --

    def test_junior_a_hurling(self):
        assert map_team_name("Junior A Hurling Championship") == "Junior A Hurling"

    def test_junior_a_football(self):
        assert map_team_name("Junior A Football Championship") == "Junior A Football"

    def test_junior_b_hurling(self):
        assert map_team_name("Junior B Hurling League") == "Junior B Hurling"

    def test_junior_b_football(self):
        assert map_team_name("Junior B Football League") == "Junior B Football"

    def test_junior_generic_hurling(self):
        assert map_team_name("Junior Hurling Shield") == "Junior A Hurling"

    def test_junior_generic_football(self):
        assert map_team_name("Junior Football Cup") == "Junior A Football"

    # -- Explicit senior --

    def test_explicit_senior_football(self):
        assert map_team_name("Senior Football League") == "Senior Football"

    def test_explicit_premier_inter_hurling(self):
        assert map_team_name("Premier Inter Hurling League") == "Premier Inter Hurling"

    # -- U21 --

    def test_u21_football(self):
        assert map_team_name("U21 Football Championship") == 'GAA U21 "A" Football'

    def test_u21_hurling(self):
        assert map_team_name("U21 Hurling Championship") == 'GAA U21 "A" Hurling'

    def test_u_21_hyphenated_football(self):
        assert map_team_name("U-21 Football League") == 'GAA U21 "A" Football'

    # -- Other / Unknown --

    def test_womens(self):
        assert map_team_name("Womens Football League") == "Womens GAA"

    def test_unknown_competition(self):
        assert map_team_name("Some Random Tournament") == "Unknown"


# ---------------------------------------------------------------------------
# determine_event_type
# ---------------------------------------------------------------------------

class TestDetermineEventType:
    """Tests for determining event type from competition name."""

    def test_championship(self):
        assert determine_event_type("Premier Senior Football Championship") == "Championship"

    def test_final(self):
        assert determine_event_type("County Final Hurling") == "Championship"

    def test_cup(self):
        assert determine_event_type("County Cup Round 1") == "Cup"

    def test_shield(self):
        assert determine_event_type("Muskerry Shield") == "Cup"

    def test_trophy(self):
        assert determine_event_type("Andy Scannell Trophy") == "Cup"

    def test_league(self):
        assert determine_event_type("McCarthy Insurance League") == "League"

    def test_division(self):
        assert determine_event_type("Division 1 FL") == "League"

    def test_fl_suffix(self):
        assert determine_event_type("AOS Security FL") == "League"

    def test_hl_suffix(self):
        assert determine_event_type("Red FM HL") == "League"

    def test_other(self):
        assert determine_event_type("Charity Match") == "Other"
