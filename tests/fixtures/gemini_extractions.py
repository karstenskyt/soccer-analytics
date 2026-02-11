"""Adapted Gemini 5c session plan JSON fixtures.

These fixtures are adapted from Gemini Pro's research extractions of 4 real
coaching session plans. Field names, enum casing, and structure have been
corrected to conform to our Pydantic schema (SessionPlan).

Each dict can be passed to SessionPlan.model_validate() directly.

Sources (Gemini 5c):
- Karsten Nielsen: 4v4+3 tactical game with pitch zones (Setups 1 & 3)
- Ashley Roberts: Cutback crossing drill with directional arrows
- Phil Wheddon: GK handling/shot-stopping with desired_outcome
"""

from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Karsten Nielsen — 4v4+3 Positional Game (Setups 1 & 3)
# ---------------------------------------------------------------------------
GEMINI_NIELSEN: dict = {
    "id": "c2d3e4f5-a6b7-8901-def0-234567890123",
    "metadata": {
        "title": "Building Out From the Back — 4v4+3 Positional Play",
        "category": "Tactical: Build-Up Play",
        "difficulty": "Advanced",
        "author": "Karsten Nielsen",
        "target_age_group": "U17+",
        "duration_minutes": 75,
        "desired_outcome": "Players understand positional rotations in "
        "build-up play, recognizing when to play through central "
        "corridors vs switching play to wide areas.",
    },
    "drills": [
        {
            "id": "d3e4f5a6-b7c8-9012-ef01-345678901234",
            "name": "Setup 1: 4v4+3 Positional Rondo",
            "drill_type": "Small-Sided Game",
            "directional": False,
            "setup": {
                "description": "4v4 with 3 neutral players who always play "
                "with the team in possession. Grid 25x20 yards. "
                "Neutrals positioned on the outside edges.",
                "player_count": "4v4 + 3 Neutrals",
                "equipment": ["8 cones", "5 balls", "bibs (3 colors)"],
                "area_dimensions": "25x20 yards",
            },
            "diagram": {
                "description": "4v4+3 rondo in a rectangular grid. "
                "4 red attackers, 4 blue defenders, 3 yellow neutrals "
                "on the outside. Ball played between attacking team "
                "and neutrals to maintain possession.",
                "player_positions": [
                    {"label": "A1", "x": 30.0, "y": 40.0, "role": "attacker"},
                    {"label": "A2", "x": 60.0, "y": 35.0, "role": "attacker"},
                    {"label": "A3", "x": 40.0, "y": 55.0, "role": "attacker"},
                    {"label": "A4", "x": 70.0, "y": 55.0, "role": "attacker"},
                    {"label": "D1", "x": 35.0, "y": 45.0, "role": "defender"},
                    {"label": "D2", "x": 55.0, "y": 45.0, "role": "defender"},
                    {"label": "D3", "x": 45.0, "y": 50.0, "role": "defender"},
                    {"label": "D4", "x": 65.0, "y": 50.0, "role": "defender"},
                    {"label": "N1", "x": 10.0, "y": 48.0, "role": "neutral"},
                    {"label": "N2", "x": 50.0, "y": 70.0, "role": "neutral"},
                    {"label": "N3", "x": 90.0, "y": 48.0, "role": "neutral"},
                ],
                "pitch_view": {
                    "view_type": "custom",
                    "length_meters": 25.0,
                    "width_meters": 20.0,
                    "orientation": "vertical",
                },
                "arrows": [
                    {
                        "start_x": 30.0,
                        "start_y": 40.0,
                        "end_x": 10.0,
                        "end_y": 48.0,
                        "arrow_type": "pass",
                        "from_label": "A1",
                        "to_label": "N1",
                        "sequence_number": 1,
                    },
                    {
                        "start_x": 10.0,
                        "start_y": 48.0,
                        "end_x": 40.0,
                        "end_y": 55.0,
                        "arrow_type": "pass",
                        "from_label": "N1",
                        "to_label": "A3",
                        "sequence_number": 2,
                    },
                    {
                        "start_x": 40.0,
                        "start_y": 55.0,
                        "end_x": 70.0,
                        "end_y": 55.0,
                        "arrow_type": "pass",
                        "from_label": "A3",
                        "to_label": "A4",
                        "sequence_number": 3,
                    },
                ],
                "equipment": [
                    {"equipment_type": "cone", "x": 15.0, "y": 30.0},
                    {"equipment_type": "cone", "x": 85.0, "y": 30.0},
                    {"equipment_type": "cone", "x": 15.0, "y": 65.0},
                    {"equipment_type": "cone", "x": 85.0, "y": 65.0},
                    {"equipment_type": "cone", "x": 50.0, "y": 30.0},
                    {"equipment_type": "cone", "x": 50.0, "y": 65.0},
                    {"equipment_type": "cone", "x": 15.0, "y": 48.0},
                    {"equipment_type": "cone", "x": 85.0, "y": 48.0},
                ],
                "goals": [],
                "balls": [{"x": 30.0, "y": 40.0}],
                "zones": [],
            },
            "sequence": [
                "Team in possession (4+3) tries to complete 6 consecutive passes",
                "If defenders win ball, they become the attacking team",
                "Neutrals always support the team in possession",
                "Play restarts from coach if ball goes out",
            ],
            "rules": [
                "Neutrals are limited to 2 touches",
                "Inside players have free touches",
                "No tackling the neutral players",
            ],
            "scoring": [
                "1 point per 6 consecutive passes",
                "3 points for a split pass through defenders",
            ],
            "coaching_points": [
                "Body shape open to receive — half-turn",
                "Recognize when to play through the middle vs. wide",
                "Movement off the ball to create passing lanes",
                "Neutrals: quick decision — one touch if possible",
            ],
            "progressions": [
                "Reduce neutral touches to 1",
                "Add a target goal — score by passing to end neutral",
                "Make the grid smaller to increase pressure",
            ],
        },
        {
            "id": "e4f5a6b7-c8d9-0123-f012-456789012345",
            "name": "Setup 3: 4v4+3 to Goals with Zones",
            "drill_type": "Game-Related Practice",
            "directional": True,
            "setup": {
                "description": "4v4+3 with two mini goals. Playing area "
                "divided into defensive third and attacking third. "
                "Build from the back, play through zones to score.",
                "player_count": "4v4 + 3 Neutrals + 2 GKs",
                "equipment": [
                    "2 mini goals",
                    "12 cones",
                    "5 balls",
                    "bibs (3 colors)",
                ],
                "area_dimensions": "40x30 yards",
            },
            "diagram": {
                "description": "4v4+3 game with two mini goals and "
                "marked zones. Defensive line zone marked in blue, "
                "PK exclusion zone in red. Directional play from "
                "one goal to the other.",
                "player_positions": [
                    {"label": "GK1", "x": 50.0, "y": 5.0, "role": "goalkeeper"},
                    {"label": "A1", "x": 25.0, "y": 30.0, "role": "attacker"},
                    {"label": "A2", "x": 50.0, "y": 25.0, "role": "attacker"},
                    {"label": "A3", "x": 75.0, "y": 30.0, "role": "attacker"},
                    {"label": "A4", "x": 50.0, "y": 45.0, "role": "attacker"},
                    {"label": "D1", "x": 30.0, "y": 55.0, "role": "defender"},
                    {"label": "D2", "x": 50.0, "y": 60.0, "role": "defender"},
                    {"label": "D3", "x": 70.0, "y": 55.0, "role": "defender"},
                    {"label": "D4", "x": 50.0, "y": 70.0, "role": "defender"},
                    {"label": "N1", "x": 5.0, "y": 50.0, "role": "neutral"},
                    {"label": "N2", "x": 50.0, "y": 50.0, "role": "neutral"},
                    {"label": "N3", "x": 95.0, "y": 50.0, "role": "neutral"},
                    {"label": "GK2", "x": 50.0, "y": 95.0, "role": "goalkeeper"},
                ],
                "pitch_view": {
                    "view_type": "half_pitch",
                    "orientation": "vertical",
                },
                "arrows": [
                    {
                        "start_x": 50.0,
                        "start_y": 5.0,
                        "end_x": 25.0,
                        "end_y": 30.0,
                        "arrow_type": "pass",
                        "from_label": "GK1",
                        "to_label": "A1",
                        "sequence_number": 1,
                    },
                    {
                        "start_x": 25.0,
                        "start_y": 30.0,
                        "end_x": 50.0,
                        "end_y": 45.0,
                        "arrow_type": "pass",
                        "from_label": "A1",
                        "to_label": "A4",
                        "sequence_number": 2,
                    },
                    {
                        "start_x": 50.0,
                        "start_y": 45.0,
                        "end_x": 75.0,
                        "end_y": 30.0,
                        "arrow_type": "through_ball",
                        "from_label": "A4",
                        "to_label": "A3",
                        "sequence_number": 3,
                    },
                    {
                        "start_x": 75.0,
                        "start_y": 30.0,
                        "end_x": 50.0,
                        "end_y": 90.0,
                        "arrow_type": "shot",
                        "from_label": "A3",
                        "sequence_number": 4,
                    },
                ],
                "equipment": [
                    {"equipment_type": "mini_goal", "x": 50.0, "y": 0.0},
                    {"equipment_type": "mini_goal", "x": 50.0, "y": 100.0},
                    {"equipment_type": "cone", "x": 10.0, "y": 40.0},
                    {"equipment_type": "cone", "x": 90.0, "y": 40.0},
                    {"equipment_type": "cone", "x": 10.0, "y": 60.0},
                    {"equipment_type": "cone", "x": 90.0, "y": 60.0},
                ],
                "goals": [
                    {"x": 50.0, "y": 0.0, "goal_type": "mini_goal"},
                    {"x": 50.0, "y": 100.0, "goal_type": "mini_goal"},
                ],
                "balls": [{"x": 50.0, "y": 5.0}],
                "zones": [
                    {
                        "zone_type": "area",
                        "x1": 10.0,
                        "y1": 0.0,
                        "x2": 90.0,
                        "y2": 40.0,
                        "label": "Defensive Third",
                        "color": "#1565C0",
                    },
                    {
                        "zone_type": "area",
                        "x1": 10.0,
                        "y1": 60.0,
                        "x2": 90.0,
                        "y2": 100.0,
                        "label": "Attacking Third",
                        "color": "#C62828",
                    },
                ],
            },
            "sequence": [
                "GK1 builds from the back into A1 or A2",
                "Attacking team plays through the middle zone",
                "Must complete at least 1 pass in the defensive third before advancing",
                "Score in the opposite mini goal",
                "If defenders win, they attack the other direction",
            ],
            "rules": [
                "Must play out from the GK (no long balls)",
                "Neutrals have 2 touches maximum",
                "Cannot score from the defensive third",
            ],
            "scoring": [
                "1 point per goal",
                "Bonus point if all 4 outfield players touch the ball in the build-up",
            ],
            "coaching_points": [
                "GK distribution — play short to feet",
                "Create width in the build-up phase",
                "Recognize the moment to play forward (trigger passes)",
                "Third-man runs to break defensive lines",
            ],
            "progressions": [
                "Add offside line at the zone boundary",
                "Limit defending team to 1 player in the defensive third",
                "Play 2-touch in the defensive third, free touch in attack",
            ],
        },
    ],
    "source": {
        "filename": "Nielsen_BuildUp_4v4.pdf",
        "page_count": 6,
        "extraction_timestamp": "2025-01-15T12:00:00Z",
    },
}

# ---------------------------------------------------------------------------
# Ashley Roberts — Crossing & Cutback Drill
# ---------------------------------------------------------------------------
GEMINI_ROBERTS: dict = {
    "id": "f5a6b7c8-d9e0-1234-0123-567890123456",
    "metadata": {
        "title": "Wide Play: Crossing & Cutback Finishing",
        "category": "Attacking: Wide Play",
        "difficulty": "Moderate",
        "author": "Ashley Roberts",
        "target_age_group": "U15+",
        "duration_minutes": 60,
        "desired_outcome": "Players develop timing of runs into the box and "
        "technique for first-time finishes from cutback crosses.",
    },
    "drills": [
        {
            "id": "a6b7c8d9-e0f1-2345-1234-678901234567",
            "name": "Drill 1: Cutback Crossing Pattern",
            "drill_type": "Technical Drill",
            "directional": True,
            "setup": {
                "description": "Wide player (W) starts with ball on the "
                "touchline. Two attackers (A1, A2) make runs into the "
                "box. GK in goal. Mannequin as passive defender.",
                "player_count": "1 GK + 1 Wide Player + 2 Attackers",
                "equipment": ["1 full goal", "6 cones", "1 mannequin", "10 balls"],
                "area_dimensions": "Half pitch width, penalty area depth",
            },
            "diagram": {
                "description": "Crossing drill from the right wing. "
                "Wide player dribbles to byline, cuts back. A1 attacks "
                "near post, A2 attacks far post / cutback zone. "
                "Arrows show dribble, cross, and runs.",
                "player_positions": [
                    {"label": "GK", "x": 50.0, "y": 5.0, "role": "goalkeeper"},
                    {"label": "W", "x": 90.0, "y": 50.0, "role": "attacker"},
                    {"label": "A1", "x": 60.0, "y": 40.0, "role": "attacker"},
                    {"label": "A2", "x": 45.0, "y": 35.0, "role": "attacker"},
                ],
                "pitch_view": {
                    "view_type": "half_pitch",
                    "orientation": "vertical",
                },
                "arrows": [
                    {
                        "start_x": 90.0,
                        "start_y": 50.0,
                        "end_x": 88.0,
                        "end_y": 15.0,
                        "arrow_type": "dribble",
                        "from_label": "W",
                        "sequence_number": 1,
                        "label": "Dribble to byline",
                    },
                    {
                        "start_x": 88.0,
                        "start_y": 15.0,
                        "end_x": 60.0,
                        "end_y": 18.0,
                        "arrow_type": "cross",
                        "from_label": "W",
                        "sequence_number": 2,
                        "label": "Cutback",
                    },
                    {
                        "start_x": 60.0,
                        "start_y": 40.0,
                        "end_x": 65.0,
                        "end_y": 15.0,
                        "arrow_type": "run",
                        "from_label": "A1",
                        "sequence_number": 3,
                        "label": "Near post run",
                    },
                    {
                        "start_x": 45.0,
                        "start_y": 35.0,
                        "end_x": 55.0,
                        "end_y": 18.0,
                        "arrow_type": "run",
                        "from_label": "A2",
                        "sequence_number": 4,
                        "label": "Cutback zone",
                    },
                    {
                        "start_x": 55.0,
                        "start_y": 18.0,
                        "end_x": 50.0,
                        "end_y": 5.0,
                        "arrow_type": "shot",
                        "from_label": "A2",
                        "sequence_number": 5,
                    },
                ],
                "equipment": [
                    {"equipment_type": "cone", "x": 90.0, "y": 50.0, "label": "Start"},
                    {"equipment_type": "cone", "x": 60.0, "y": 40.0},
                    {"equipment_type": "cone", "x": 45.0, "y": 35.0},
                    {"equipment_type": "cone", "x": 65.0, "y": 18.0, "label": "Near post"},
                    {"equipment_type": "cone", "x": 55.0, "y": 18.0, "label": "Cutback zone"},
                    {
                        "equipment_type": "mannequin",
                        "x": 62.0,
                        "y": 20.0,
                        "label": "Passive CB",
                    },
                ],
                "goals": [
                    {"x": 50.0, "y": 0.0, "goal_type": "full_goal", "width_meters": 7.32},
                ],
                "balls": [{"x": 90.0, "y": 52.0}],
                "zones": [],
            },
            "sequence": [
                "W receives ball on the right touchline",
                "W dribbles towards the byline at pace",
                "A1 times near-post run",
                "A2 holds then attacks the cutback zone",
                "W delivers cutback cross to A2",
                "A2 finishes first-time into the goal",
            ],
            "rules": [
                "W must reach the byline before crossing",
                "Attackers must stay onside (behind the mannequin line)",
            ],
            "scoring": [],
            "coaching_points": [
                "Winger: head up before crossing — pick the runner",
                "A1: decoy run — take the defender to the near post",
                "A2: patience — arrive late into the cutback zone",
                "First-time finish: side foot, low and across the keeper",
            ],
            "progressions": [
                "Switch to left wing delivery",
                "Add a live defender instead of mannequin",
                "W chooses between cutback and near-post cross",
            ],
        },
    ],
    "source": {
        "filename": "Roberts_Crossing_Cutback.pdf",
        "page_count": 3,
        "extraction_timestamp": "2025-01-15T12:00:00Z",
    },
}

# ---------------------------------------------------------------------------
# Phil Wheddon — GK Handling & Shot-Stopping
# ---------------------------------------------------------------------------
GEMINI_WHEDDON: dict = {
    "id": "16a7b8c9-d0e1-2345-2345-789012345678",
    "metadata": {
        "title": "Goalkeeper Handling & Shot-Stopping",
        "category": "Goalkeeping: Shot-Stopping",
        "difficulty": "Intermediate",
        "author": "Phil Wheddon",
        "target_age_group": "U14+",
        "duration_minutes": 60,
        "desired_outcome": "Dealing with shots from angles, repositioning, "
        "timing and balance.",
    },
    "drills": [
        {
            "id": "27b8c9d0-e1f2-3456-3456-890123456789",
            "name": "Drill 1: Angled Shot-Stopping with Transition",
            "drill_type": "Technical Drill",
            "directional": True,
            "setup": {
                "description": "Two servers (S1 left, S2 right) positioned "
                "at 45-degree angles to goal, 18 yards out. GK starts "
                "central. Transition movement between saves.",
                "player_count": "1 GK + 2 Servers",
                "equipment": ["1 full goal", "4 cones", "20 balls"],
                "area_dimensions": "Penalty area width",
            },
            "diagram": {
                "description": "GK faces alternating shots from S1 and "
                "S2 at 45-degree angles. Transition arrows show GK "
                "shuffling across goal between saves. Cones mark "
                "the GK's set positions.",
                "player_positions": [
                    {"label": "GK", "x": 50.0, "y": 8.0, "role": "goalkeeper"},
                    {"label": "S1", "x": 20.0, "y": 55.0, "role": "neutral"},
                    {"label": "S2", "x": 80.0, "y": 55.0, "role": "neutral"},
                ],
                "pitch_view": {
                    "view_type": "penalty_area",
                    "orientation": "vertical",
                },
                "arrows": [
                    {
                        "start_x": 20.0,
                        "start_y": 55.0,
                        "end_x": 40.0,
                        "end_y": 10.0,
                        "arrow_type": "shot",
                        "from_label": "S1",
                        "sequence_number": 1,
                    },
                    {
                        "start_x": 40.0,
                        "start_y": 10.0,
                        "end_x": 60.0,
                        "end_y": 10.0,
                        "arrow_type": "movement",
                        "from_label": "GK",
                        "sequence_number": 2,
                        "label": "Transition shuffle",
                    },
                    {
                        "start_x": 80.0,
                        "start_y": 55.0,
                        "end_x": 60.0,
                        "end_y": 10.0,
                        "arrow_type": "shot",
                        "from_label": "S2",
                        "sequence_number": 3,
                    },
                    {
                        "start_x": 60.0,
                        "start_y": 10.0,
                        "end_x": 40.0,
                        "end_y": 10.0,
                        "arrow_type": "movement",
                        "from_label": "GK",
                        "sequence_number": 4,
                        "label": "Transition shuffle",
                    },
                ],
                "equipment": [
                    {"equipment_type": "cone", "x": 40.0, "y": 8.0, "label": "Set pos L"},
                    {"equipment_type": "cone", "x": 60.0, "y": 8.0, "label": "Set pos R"},
                    {"equipment_type": "cone", "x": 20.0, "y": 55.0},
                    {"equipment_type": "cone", "x": 80.0, "y": 55.0},
                ],
                "goals": [
                    {"x": 50.0, "y": 0.0, "goal_type": "full_goal", "width_meters": 7.32},
                ],
                "balls": [
                    {"x": 20.0, "y": 57.0},
                    {"x": 80.0, "y": 57.0},
                ],
                "zones": [],
            },
            "sequence": [
                "GK starts at left set position (cone)",
                "S1 shoots from left angle",
                "GK saves, distributes, shuffles to right set position",
                "S2 shoots from right angle",
                "GK saves, distributes, shuffles back to left",
                "Repeat 5 times each side",
            ],
            "rules": [
                "Servers wait until GK reaches set position cone",
                "Shots must be within frame",
            ],
            "scoring": [],
            "coaching_points": [
                "Set position: ball-line between post and ball",
                "Stay on toes — do not lean back",
                "Low shots: collapse technique, lead with hands",
                "High shots: power step, attack the ball",
                "Transition: quick shuffle, eyes on the ball",
            ],
            "progressions": [
                "Add a third server centrally (S3)",
                "S1/S2 can pass to each other before shooting",
                "GK must play a distribution pass before transitioning",
            ],
        },
    ],
    "source": {
        "filename": "Wheddon_GK_Handling.pdf",
        "page_count": 4,
        "extraction_timestamp": "2025-01-15T12:00:00Z",
    },
}

# Convenience list of all fixture dicts
ALL_GEMINI_FIXTURES: list[dict] = [
    GEMINI_NIELSEN,
    GEMINI_ROBERTS,
    GEMINI_WHEDDON,
]
