"""
Shared team-name mapping and event-type detection for GAA fixtures.

Used by both scraper.py (fallback) and enhanced_monitor.py (primary).
Keeping one canonical version avoids divergent mappings.
"""


def map_team_name(comp_name):
    """Map a GAA Cork competition name to the Ballincollig ClubZap team name.

    ClubZap team names:
        Senior Football, Premier Inter Hurling,
        Junior A Football, Junior A Hurling,
        Junior B Football, Junior B Hurling, Junior C Football,
        Minor Football GAA, Minor Hurling GAA,
        U14 GAA, U16 GAA,
        GAA U21 "A" Football, GAA U21 "A" Hurling,
        GAA U21 "B" Football, GAA U21 "B" Hurling,
        BCC Senior Squad, BCC Junior Squad, BCC 2026 Minor  (Camogie)

    Note: Camogie fixtures from corkcamogie.com are normally pre-mapped by
    the camogie_scraper (team name set via config), so this function is only
    a fallback for camogie competition names.
    """
    comp_lower = comp_name.lower()

    # Determine code (football or hurling)
    is_football = any(x in comp_lower for x in ["football", " fl"])
    is_hurling = any(x in comp_lower for x in ["hurling", " hl"])

    # --- Underage (Fe14 / Fe16 use single "GAA" team name for both codes) ---
    if "fe12" in comp_lower:
        return "U12 GAA"
    if "fe13" in comp_lower:
        return "U13 GAA"
    if "fe14" in comp_lower:
        return "U14 GAA"
    if "fe15" in comp_lower:
        return "U15 GAA"
    if "fe16" in comp_lower:
        return "U16 GAA"

    # --- Minor (Fe18 splits by code) ---
    if "fe18" in comp_lower:
        if is_hurling:
            return "Minor Hurling GAA"
        return "Minor Football GAA"

    # --- County Senior Leagues ---
    if "mccarthy insurance" in comp_lower or "mccarthy" in comp_lower:
        return "Senior Football"
    if "red fm" in comp_lower:
        return "Premier Inter Hurling"

    # --- County Championships ---
    if "psfc" in comp_lower or ("premier senior" in comp_lower and is_football):
        return "Senior Football"
    if "senior fc" in comp_lower:
        return "Senior Football"
    if "pihc" in comp_lower or ("premier intermediate" in comp_lower and is_hurling):
        return "Premier Inter Hurling"
    if "premier ihc" in comp_lower:
        return "Premier Inter Hurling"

    # --- Divisional Junior Leagues (AOS Security = Muskerry division) ---
    if "aos security" in comp_lower or "aos " in comp_lower:
        if "div 4" in comp_lower or "div 5" in comp_lower:
            if is_hurling:
                return "Junior B Hurling"
            return "Junior B Football"
        elif "div 3" in comp_lower:
            if is_hurling:
                return "Junior B Hurling"
            return "Junior A Football"
        else:
            if is_hurling:
                return "Junior A Hurling"
            return "Junior A Football"

    # --- Muskerry Divisional Junior Leagues (Cumnor, EPH, Erneside sponsors) ---
    if "cumnor" in comp_lower:
        return "Junior A Hurling"
    if "eph " in comp_lower:
        if "division 2" in comp_lower or "division 3" in comp_lower:
            return "Junior B Football"
        return "Junior A Football"
    if "erneside" in comp_lower:
        return "Junior B Hurling"

    # --- Division-number leagues ---
    if "division 1 fl" in comp_lower:
        return "Senior Football"
    if "division 2 fl" in comp_lower:
        return "Junior A Football"
    if "division 3 fl" in comp_lower:
        return "Junior B Football"
    if "division 1 hl" in comp_lower:
        return "Senior Hurling"
    if "division 2 hl" in comp_lower:
        return "Junior A Hurling"
    if "division 3 hl" in comp_lower:
        return "Junior B Hurling"

    # --- Named junior grades ---
    if "junior a hurling" in comp_lower:
        return "Junior A Hurling"
    if "junior a football" in comp_lower:
        return "Junior A Football"
    if "junior b hurling" in comp_lower:
        return "Junior B Hurling"
    if "junior b football" in comp_lower:
        return "Junior B Football"
    if "junior" in comp_lower:
        if is_hurling:
            return "Junior A Hurling"
        return "Junior A Football"

    # --- Explicit senior names ---
    if "senior football" in comp_lower:
        return "Senior Football"
    if "premier inter hurling" in comp_lower:
        return "Premier Inter Hurling"

    # --- U21 ---
    if "u21" in comp_lower or "u-21" in comp_lower:
        if is_hurling:
            return 'GAA U21 "A" Hurling'
        return 'GAA U21 "A" Football'

    # --- Other ---
    if "womens" in comp_lower:
        return "Womens GAA"
    if "u18.5" in comp_lower:
        return "U18.5 GAA"

    return "Unknown"


def determine_event_type(comp_name):
    """Determine event type (League / Championship / Cup / Other) from a competition name."""
    comp_lower = comp_name.lower()

    if "championship" in comp_lower or "final" in comp_lower:
        return "Championship"
    if any(x in comp_lower for x in ["cup", "shield", "trophy"]):
        return "Cup"
    if any(x in comp_lower for x in ["league", "division", " fl", " hl"]):
        return "League"
    return "Other"
