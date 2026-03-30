"""
Shared GAA utility functions.
"""


def gaa_total(score_str):
    """Convert a GAA score string like '1-6' to total points (1*3 + 6 = 9)."""
    try:
        goals, points = score_str.split("-")
        return int(goals) * 3 + int(points)
    except (ValueError, AttributeError):
        return 0
