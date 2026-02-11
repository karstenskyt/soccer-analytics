"""Human-verified ground truth for session plan diagrams.

These counts come from manual inspection of the original PDF diagrams
and serve as the accuracy benchmark for VLM extraction.
"""

# ---------------------------------------------------------------------------
# Session Plan - Karsten Nielsen
# "Adv. Nat. GK Diploma: Defend the goal or the space"
# Source: samples/Session Plan - Karsten Nielsen.pdf  (2 pages, 3 diagrams)
# ---------------------------------------------------------------------------

NIELSEN_GROUND_TRUTH = {
    "source_filename": "Session Plan - Karsten Nielsen.pdf",
    "drill_count": 3,
    "drills": [
        {
            "name": "Coach-Goalkeeper(s)",
            "pitch_view": "penalty_area",
            "players": {
                "total": 3,
                "detail": [
                    {"role": "goalkeeper", "color": "green", "count": 1, "note": "GK in goal"},
                    {"role": "coach", "color": None, "count": 1, "note": "Coach serving"},
                    {"role": "goalkeeper", "color": "green", "count": 1, "note": "2nd GK to the left, also serving"},
                ],
            },
            "arrows": 5,
            "goals": {"full_goal": 1},
            "equipment": {},
        },
        {
            "name": "Coach-Goalkeeper(s)-Field Players",
            "pitch_view": "third",
            "players": {
                "total": 6,
                "detail": [
                    {"role": "field_player", "color": "red", "count": 4},
                    {"role": "goalkeeper", "color": "green", "count": 1, "note": "GK in goal"},
                    {"role": "goalkeeper", "color": "green", "count": 1, "note": "GK behind the goal to the right"},
                ],
            },
            "arrows": 5,
            "goals": {"full_goal": 1},
            "equipment": {"mannequin": 2, "mannequin_color": "blue"},
        },
        {
            "name": "Coach-Goalkeeper(s)-Team",
            "pitch_view": "between_half_and_full",
            "players": {
                "total": 13,
                "detail": [
                    {"role": "goalkeeper", "color": "green", "count": 2},
                    {"role": "field_player", "color": "red", "count": 4},
                    {"role": "field_player", "color": "yellow", "count": 3},
                    {"role": "field_player", "color": "blue", "count": 4},
                ],
            },
            "arrows": 0,
            "goals": {"full_goal": 2},
            "equipment": {},
        },
    ],
}


# ---------------------------------------------------------------------------
# Session Plan - Ashley Roberts
# "ANGK - METHODOLOGY - CUTBACKS FRONT POST AREA"
# Source: samples/Session Plan - Ashley Roberts.pdf
# Players drawn as circles (not standard player icons)
# ---------------------------------------------------------------------------

ROBERTS_GROUND_TRUTH = {
    "source_filename": "Session Plan - Ashley Roberts.pdf",
    "drill_count": 4,
    "drills": [
        {
            "name": "COACH-GK(S) 1",
            "pitch_view": "third",
            "players": {
                "total": 4,
                "detail": [
                    {"role": "field_player", "color": "red", "count": 2},
                    {"role": "field_player", "color": "yellow", "count": 2},
                ],
            },
            "arrows": 0,
            "goals": {"full_goal": 1, "mini_goal": 2},
            "equipment": {},
        },
        {
            "name": "COACH-GK(S) 2",
            "pitch_view": "third",
            "players": {
                "total": 6,
                "detail": [
                    {"role": "field_player", "color": "red", "count": 4},
                    {"role": "field_player", "color": "yellow", "count": 2},
                ],
            },
            "arrows": 0,
            "goals": {"full_goal": 1},
            "equipment": {},
            "note": "3 numbers on pitch are NOT players",
        },
        {
            "name": "COACH-GK-FIELD PLAYERS",
            "pitch_view": "penalty_area",
            "players": {
                "total": 8,
                "detail": [
                    {"role": "field_player", "color": "red", "count": 3},
                    {"role": "field_player", "color": "blue", "count": 3},
                    {"role": "field_player", "color": "yellow", "count": 2},
                ],
            },
            "arrows": 0,
            "goals": {"full_goal": 2},
            "equipment": {},
            "note": "2 shaded zones on sides of PK area",
        },
        {
            "name": "GAME",
            "has_diagram": False,
        },
    ],
}


# ---------------------------------------------------------------------------
# Session Plan - Phil Wheddon
# "IGCC Learning Center"
# Source: samples/Session Plan - Phil Wheddon.pdf
# Uses gray player color and air bodies as equipment
# Some players faded or obscured
# ---------------------------------------------------------------------------

WHEDDON_GROUND_TRUTH = {
    "source_filename": "Session Plan - Phil Wheddon.pdf",
    "drill_count": 2,
    "drills": [
        {
            "name": "FOCUS (warm-up)",
            "pitch_view": "third",
            "players": {
                "total": 6,
                "detail": [
                    {"role": "field_player", "color": "gray", "count": 3},
                    {"role": "field_player", "color": "yellow", "count": 3,
                     "note": "one faded"},
                ],
            },
            "arrows": 5,
            "arrow_detail": {"black": 3, "red": 2},
            "goals": {"full_goal": 1},
            "equipment": {"air_body": 2},
            "balls": 3,
            "note": "balls by gray players",
        },
        {
            "name": "FOCUS (main drill)",
            "pitch_view": "third",
            "players": {
                "total": 6,
                "detail": [
                    {"role": "field_player", "color": "gray", "count": 3},
                    {"role": "field_player", "color": "yellow", "count": 3,
                     "note": "one faded, one obscured by goal"},
                ],
            },
            "arrows": 4,
            "arrow_detail": {"black": 3, "red": 1},
            "goals": {"full_goal": 2},
            "equipment": {"air_body": 2},
            "balls": 3,
            "note": "one ball obscured by goal",
        },
    ],
}
