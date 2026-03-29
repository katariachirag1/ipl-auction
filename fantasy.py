"""Fantasy points calculator using CricAPI."""

import os
import json
import urllib.request

API_KEY = os.environ.get("CRICAPI_KEY", "17c1a5d4-ad60-4f88-b673-f601e553ea16")
BASE_URL = "https://api.cricapi.com/v1"

# Dream11-style T20 fantasy points
POINTS = {
    "run": 1,
    "four_bonus": 1,       # extra per 4
    "six_bonus": 2,        # extra per 6
    "thirty_bonus": 4,     # 30+ runs
    "fifty_bonus": 8,      # 50+ runs
    "hundred_bonus": 16,   # 100+ runs
    "duck": -2,            # 0 runs (batsman only, not bowler)
    "wicket": 25,
    "maiden": 12,
    "three_wkt_bonus": 4,
    "four_wkt_bonus": 8,
    "five_wkt_bonus": 16,
    "catch": 8,
    "stumping": 12,
    "run_out": 12,         # direct hit
    "sr_below_50": -6,     # strike rate penalties (min 10 balls)
    "sr_50_60": -4,
    "sr_60_70": -2,
    "econ_below_5": 6,     # economy bonuses (min 2 overs)
    "econ_5_6": 4,
    "econ_6_7": 2,
    "econ_10_11": -2,
    "econ_11_12": -4,
    "econ_above_12": -6,
}


IPL_2026_SERIES_ID = "87c62aac-bc3c-4738-ab93-19da0690488f"


def fetch_scorecard(match_id):
    """Fetch match scorecard from CricAPI."""
    url = f"{BASE_URL}/match_scorecard?apikey={API_KEY}&id={match_id}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    if data.get("status") != "success":
        raise Exception(f"API error: {data}")
    return data.get("data", {})


def fetch_ipl_matches(series_id=None):
    """Fetch IPL 2026 match list."""
    sid = series_id or IPL_2026_SERIES_ID
    url = f"{BASE_URL}/series_info?apikey={API_KEY}&id={sid}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    return data.get("data", {}).get("matchList", [])


def calculate_fantasy_points(scorecard):
    """Calculate fantasy points per player from a match scorecard.
    Returns dict: {player_name: {"points": X, "breakdown": {...}}}
    """
    player_points = {}

    for inning in scorecard.get("scorecard", []):
        # Batting
        for b in inning.get("batting", []):
            name = b.get("batsman", {}).get("name", "")
            if not name:
                continue
            if name not in player_points:
                player_points[name] = {"points": 0, "breakdown": {}}

            runs = b.get("r", 0) or 0
            balls = b.get("b", 0) or 0
            fours = b.get("4s", 0) or 0
            sixes = b.get("6s", 0) or 0
            dismissal = b.get("dismissal", "")

            pts = 0
            bd = {}

            # Runs
            bd["runs"] = runs * POINTS["run"]
            pts += bd["runs"]

            # Boundary bonus
            bd["fours"] = fours * POINTS["four_bonus"]
            bd["sixes"] = sixes * POINTS["six_bonus"]
            pts += bd["fours"] + bd["sixes"]

            # Milestone bonus
            if runs >= 100:
                bd["hundred"] = POINTS["hundred_bonus"]
                pts += bd["hundred"]
            elif runs >= 50:
                bd["fifty"] = POINTS["fifty_bonus"]
                pts += bd["fifty"]
            elif runs >= 30:
                bd["thirty"] = POINTS["thirty_bonus"]
                pts += bd["thirty"]

            # Duck
            if runs == 0 and dismissal and dismissal != "not out":
                bd["duck"] = POINTS["duck"]
                pts += bd["duck"]

            # Strike rate penalty (min 10 balls)
            if balls >= 10:
                sr = (runs / balls) * 100 if balls > 0 else 0
                if sr < 50:
                    bd["sr_penalty"] = POINTS["sr_below_50"]
                elif sr < 60:
                    bd["sr_penalty"] = POINTS["sr_50_60"]
                elif sr < 70:
                    bd["sr_penalty"] = POINTS["sr_60_70"]
                if "sr_penalty" in bd:
                    pts += bd["sr_penalty"]

            player_points[name]["points"] += pts
            player_points[name]["breakdown"].update(bd)

        # Bowling
        for bw in inning.get("bowling", []):
            name = bw.get("bowler", {}).get("name", "")
            if not name:
                continue
            if name not in player_points:
                player_points[name] = {"points": 0, "breakdown": {}}

            wickets = bw.get("w", 0) or 0
            overs = bw.get("o", 0) or 0
            maidens = bw.get("m", 0) or 0
            econ = bw.get("eco", 0) or 0

            pts = 0
            bd = player_points[name]["breakdown"]

            # Wickets
            wkt_pts = wickets * POINTS["wicket"]
            bd["wickets"] = bd.get("wickets", 0) + wkt_pts
            pts += wkt_pts

            # Maiden
            maiden_pts = maidens * POINTS["maiden"]
            bd["maidens"] = bd.get("maidens", 0) + maiden_pts
            pts += maiden_pts

            # Wicket bonus
            if wickets >= 5:
                bd["five_wkt"] = POINTS["five_wkt_bonus"]
                pts += bd["five_wkt"]
            elif wickets >= 4:
                bd["four_wkt"] = POINTS["four_wkt_bonus"]
                pts += bd["four_wkt"]
            elif wickets >= 3:
                bd["three_wkt"] = POINTS["three_wkt_bonus"]
                pts += bd["three_wkt"]

            # Economy bonus/penalty (min 2 overs)
            if overs >= 2:
                if econ < 5:
                    bd["econ_bonus"] = POINTS["econ_below_5"]
                elif econ < 6:
                    bd["econ_bonus"] = POINTS["econ_5_6"]
                elif econ < 7:
                    bd["econ_bonus"] = POINTS["econ_6_7"]
                elif econ > 12:
                    bd["econ_bonus"] = POINTS["econ_above_12"]
                elif econ > 11:
                    bd["econ_bonus"] = POINTS["econ_10_11"]
                elif econ > 10:
                    bd["econ_bonus"] = POINTS["econ_10_11"]
                if "econ_bonus" in bd:
                    pts += bd["econ_bonus"]

            player_points[name]["points"] += pts

        # Fielding (catches from dismissal-text)
        for b in inning.get("batting", []):
            catcher = b.get("catcher", {}).get("name", "")
            dismissal = b.get("dismissal", "")
            if catcher and dismissal == "catch":
                if catcher not in player_points:
                    player_points[catcher] = {"points": 0, "breakdown": {}}
                player_points[catcher]["points"] += POINTS["catch"]
                player_points[catcher]["breakdown"]["catches"] = \
                    player_points[catcher]["breakdown"].get("catches", 0) + POINTS["catch"]

            if dismissal == "stumped":
                stumper = b.get("catcher", {}).get("name", "")
                if stumper:
                    if stumper not in player_points:
                        player_points[stumper] = {"points": 0, "breakdown": {}}
                    player_points[stumper]["points"] += POINTS["stumping"]
                    player_points[stumper]["breakdown"]["stumpings"] = \
                        player_points[stumper]["breakdown"].get("stumpings", 0) + POINTS["stumping"]

            if dismissal == "run out":
                # Run out credit goes to catcher field
                fielder = b.get("catcher", {}).get("name", "")
                if fielder:
                    if fielder not in player_points:
                        player_points[fielder] = {"points": 0, "breakdown": {}}
                    player_points[fielder]["points"] += POINTS["run_out"]
                    player_points[fielder]["breakdown"]["run_outs"] = \
                        player_points[fielder]["breakdown"].get("run_outs", 0) + POINTS["run_out"]

    return player_points
