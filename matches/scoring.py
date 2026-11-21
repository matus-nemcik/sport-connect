"""Scoring rules for tips (FR4).

* 3 points - exact score
* 1 point  - correct outcome (home win / draw / away win)
* 0 points - otherwise
"""

EXACT_POINTS = 3
OUTCOME_POINTS = 1


def _outcome(home, away):
    return (home > away) - (home < away)


def points_for(tip_home, tip_away, real_home, real_away):
    if tip_home == real_home and tip_away == real_away:
        return EXACT_POINTS
    if _outcome(tip_home, tip_away) == _outcome(real_home, real_away):
        return OUTCOME_POINTS
    return 0
