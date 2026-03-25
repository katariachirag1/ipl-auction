#!/usr/bin/env python3
"""IPL Auction Bidding App - Minimal Flask backend."""

import json
import os
import random
import sqlite3
import time
from flask import Flask, g, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static")
DB_PATH = os.path.join(os.path.dirname(__file__), "auction.db")
AUCTION_DURATION = 60  # 1 minute per player
MIN_DISPLAY_TIME = 10  # minimum seconds before auto-close can happen
BUDGET = 100  # points per bidder


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS bidders (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            budget REAL NOT NULL DEFAULT 100
        );
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            team TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT '',
            base_price REAL NOT NULL DEFAULT 1,
            sold_to INTEGER REFERENCES bidders(id),
            sold_price REAL
        );
        CREATE TABLE IF NOT EXISTS auction_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            current_player_id INTEGER REFERENCES players(id),
            started_at REAL,
            highest_bid REAL DEFAULT 0,
            highest_bidder_id INTEGER REFERENCES bidders(id)
        );
        CREATE TABLE IF NOT EXISTS bids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL REFERENCES players(id),
            bidder_id INTEGER NOT NULL REFERENCES bidders(id),
            amount REAL NOT NULL,
            ts REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS passes (
            player_id INTEGER NOT NULL,
            bidder_id INTEGER NOT NULL,
            PRIMARY KEY (player_id, bidder_id)
        );
        CREATE TABLE IF NOT EXISTS autopass (
            bidder_id INTEGER PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 0
        );
        INSERT OR IGNORE INTO auction_state (id) VALUES (1);
    """)
    # Seed bidders if empty — no longer pre-seeded, users join dynamically
    # Seed players if empty
    cur = db.execute("SELECT COUNT(*) FROM players")
    if cur.fetchone()[0] == 0:
        _seed_players(db)
    db.commit()
    db.close()


def _seed_players(db):
    """Seed with actual IPL 2026 players (all 10 teams, 250 players)."""
    teams = {
        "CSK": [
            ("Ruturaj Gaikwad", "Batsman", 2), ("Ayush Mhatre", "Batsman", 1), ("Dewald Brevis", "Batsman", 2), ("Sarfaraz Khan", "Batsman", 1),
            ("MS Dhoni", "WK", 2), ("Sanju Samson", "WK", 2), ("Kartik Sharma", "WK", 2), ("Urvil Patel", "WK", 1),
            ("Shivam Dube", "All-rounder", 2), ("Matthew Short", "All-rounder", 1), ("Jamie Overton", "All-rounder", 1), ("Prashant Veer", "All-rounder", 2),
            ("Aman Khan", "All-rounder", 1), ("Anshul Kamboj", "All-rounder", 1), ("Zak Foulkes", "All-rounder", 1),
            ("Khaleel Ahmed", "Bowler", 1), ("Rahul Chahar", "Bowler", 1), ("Nathan Ellis", "Bowler", 1), ("Matt Henry", "Bowler", 1),
            ("Noor Ahmad", "Bowler", 1), ("Akeal Hosein", "Bowler", 1), ("Mukesh Choudhary", "Bowler", 1), ("Shreyas Gopal", "Bowler", 1),
            ("Gurjapneet Singh", "Bowler", 1), ("Ramkrishna Ghosh", "Bowler", 1),
        ],
        "DC": [
            ("KL Rahul", "WK", 2), ("Axar Patel", "All-rounder", 2), ("Kuldeep Yadav", "Bowler", 2), ("Mitchell Starc", "Bowler", 2),
            ("Karun Nair", "Batsman", 1), ("Prithvi Shaw", "Batsman", 1), ("David Miller", "Batsman", 2), ("Pathum Nissanka", "Batsman", 1),
            ("Tristan Stubbs", "WK", 1), ("Ben Duckett", "WK", 1), ("Abhishek Porel", "WK", 1),
            ("Nitish Rana", "All-rounder", 1), ("Auqib Dar", "All-rounder", 1), ("Vipraj Nigam", "All-rounder", 1),
            ("Lungi Ngidi", "Bowler", 1), ("Kyle Jamieson", "Bowler", 1), ("Mukesh Kumar", "Bowler", 1), ("T Natarajan", "Bowler", 1),
            ("Dushmantha Chameera", "Bowler", 1), ("Ashutosh Sharma", "Batsman", 1), ("Sahil Parakh", "Batsman", 1),
            ("Sameer Rizvi", "Batsman", 1), ("Ajay Mandal", "All-rounder", 1), ("Madhav Tiwari", "All-rounder", 1), ("Tripurana Vijay", "All-rounder", 1),
        ],
        "GT": [
            ("Shubman Gill", "Batsman", 2), ("Rashid Khan", "Bowler", 2), ("Kagiso Rabada", "Bowler", 2), ("Jos Buttler", "WK", 2),
            ("Sai Sudharsan", "Batsman", 2), ("Shahrukh Khan", "Batsman", 1), ("Glenn Phillips", "All-rounder", 1),
            ("Washington Sundar", "All-rounder", 1), ("Rahul Tewatia", "All-rounder", 1), ("Mohammed Siraj", "Bowler", 1),
            ("Prasidh Krishna", "Bowler", 1), ("R Sai Kishore", "Bowler", 1), ("Manav Suthar", "Bowler", 1),
            ("Jason Holder", "All-rounder", 1), ("Luke Wood", "Bowler", 1), ("Ishant Sharma", "Bowler", 1),
            ("Anuj Rawat", "WK", 1), ("Kumar Khushagra", "WK", 1), ("Tom Banton", "WK", 1),
            ("Jayant Yadav", "All-rounder", 1), ("Nishant Sindhu", "All-rounder", 1), ("Arshad Khan", "All-rounder", 1),
            ("Ashok Sharma", "Bowler", 1), ("Gurnoor Brar", "Bowler", 1), ("Prithviraj Yarra", "Bowler", 1),
        ],
        "KKR": [
            ("Rinku Singh", "Batsman", 2), ("Sunil Narine", "All-rounder", 2), ("Varun Chakravarthy", "Bowler", 2),
            ("Cameron Green", "All-rounder", 2), ("Harshit Rana", "Bowler", 1), ("Rachin Ravindra", "All-rounder", 1),
            ("Ajinkya Rahane", "Batsman", 1), ("Rovman Powell", "Batsman", 1), ("Manish Pandey", "Batsman", 1),
            ("Rahul Tripathi", "Batsman", 1), ("Finn Allen", "WK", 1), ("Tim Seifert", "WK", 1),
            ("Matheesha Pathirana", "Bowler", 2), ("Mustafizur Rahman", "Bowler", 1), ("Umran Malik", "Bowler", 1),
            ("Akash Deep", "Bowler", 1), ("Vaibhav Arora", "Bowler", 1), ("Kartik Tyagi", "Bowler", 1),
            ("Ramandeep Singh", "All-rounder", 1), ("Anukul Roy", "All-rounder", 1), ("Angkrish Raghuvanshi", "Batsman", 1),
            ("Tejasvi Singh", "WK", 1), ("Daksh Kamra", "All-rounder", 1), ("Sarthak Ranjan", "All-rounder", 1), ("Prashant Solanki", "Bowler", 1),
        ],
        "LSG": [
            ("Rishabh Pant", "WK", 2), ("Nicholas Pooran", "WK", 2), ("Mayank Yadav", "Bowler", 2), ("Mitchell Marsh", "All-rounder", 2),
            ("Ayush Badoni", "Batsman", 1), ("Aiden Markram", "Batsman", 1), ("Mohammed Shami", "Bowler", 2),
            ("Avesh Khan", "Bowler", 1), ("Anrich Nortje", "Bowler", 1), ("Wanindu Hasaranga", "All-rounder", 1),
            ("Josh Inglis", "WK", 1), ("Shahbaz Ahmed", "All-rounder", 1), ("Abdul Samad", "All-rounder", 1),
            ("Arshin Kulkarni", "All-rounder", 1), ("Arjun Tendulkar", "All-rounder", 1),
            ("Himmat Singh", "Batsman", 1), ("Matthew Breetzke", "Batsman", 1), ("Akshat Raghuvanshi", "Batsman", 1),
            ("Mukul Choudhary", "WK", 1), ("Mohsin Khan", "Bowler", 1), ("M Siddharth", "Bowler", 1),
            ("Akash Singh", "Bowler", 1), ("Digvesh Singh", "Bowler", 1), ("Naman Tiwari", "Bowler", 1), ("Prince Yadav", "Bowler", 1),
        ],
        "MI": [
            ("Jasprit Bumrah", "Bowler", 2), ("Suryakumar Yadav", "Batsman", 2), ("Hardik Pandya", "All-rounder", 2), ("Rohit Sharma", "Batsman", 2),
            ("Tilak Varma", "Batsman", 2), ("Trent Boult", "Bowler", 2), ("Quinton de Kock", "WK", 2),
            ("Will Jacks", "All-rounder", 1), ("Deepak Chahar", "Bowler", 1), ("Shardul Thakur", "Bowler", 1),
            ("Mitchell Santner", "All-rounder", 1), ("Naman Dhir", "All-rounder", 1), ("Raj Bawa", "All-rounder", 1),
            ("Ryan Rickelton", "WK", 1), ("Robin Minz", "WK", 1), ("Sherfane Rutherford", "Batsman", 1),
            ("Corbin Bosch", "All-rounder", 1), ("Allah Ghazanfar", "Bowler", 1), ("Atharva Ankolekar", "All-rounder", 1),
            ("Danish Melawar", "Batsman", 1), ("Mayank Rawat", "All-rounder", 1), ("Ashwani Kumar", "Bowler", 1),
            ("Mayank Markande", "Bowler", 1), ("Mohammad Izhar", "Bowler", 1), ("Raghu Sharma", "Bowler", 1),
        ],
        "PBKS": [
            ("Shreyas Iyer", "Batsman", 2), ("Arshdeep Singh", "Bowler", 2), ("Yuzvendra Chahal", "Bowler", 2),
            ("Marcus Stoinis", "All-rounder", 2), ("Marco Jansen", "All-rounder", 2), ("Lockie Ferguson", "Bowler", 1),
            ("Musheer Khan", "Batsman", 1), ("Nehal Wadhera", "Batsman", 1), ("Shashank Singh", "Batsman", 1),
            ("Azmatullah Omarzai", "All-rounder", 1), ("Harpreet Brar", "All-rounder", 1), ("Cooper Connolly", "All-rounder", 1),
            ("Xavier Bartlett", "Bowler", 1), ("Ben Dwarshuis", "Bowler", 1), ("Yash Thakur", "Bowler", 1),
            ("Prabsimran Singh", "WK", 1), ("Vishnu Vinod", "WK", 1), ("Priyansh Arya", "Batsman", 1),
            ("Harnoor Pannu", "Batsman", 1), ("Michell Owen", "Batsman", 1), ("Pyla Avinash", "Batsman", 1),
            ("Suryansh Shedge", "All-rounder", 1), ("Pravin Dubey", "Bowler", 1), ("Vishal Nishad", "Bowler", 1), ("Vyshak Vijaykumar", "Bowler", 1),
        ],
        "RR": [
            ("Yashasvi Jaiswal", "Batsman", 2), ("Riyan Parag", "All-rounder", 2), ("Jofra Archer", "Bowler", 2),
            ("Ravindra Jadeja", "All-rounder", 2), ("Sam Curran", "All-rounder", 2), ("Shimron Hetmyer", "Batsman", 1),
            ("Dhruv Jurel", "WK", 1), ("Vaibhav Suryavanshi", "Batsman", 1), ("Ravi Bishnoi", "Bowler", 1),
            ("Tushar Deshpande", "Bowler", 1), ("Sandeep Sharma", "Bowler", 1), ("Kuldeep Sen", "Bowler", 1),
            ("Kwena Maphaka", "Bowler", 1), ("Adam Milne", "Bowler", 1), ("Nandre Burger", "Bowler", 1),
            ("Donovan Ferreira", "WK", 1), ("Lhuan de Pretorius", "WK", 1), ("Ravi Singh", "WK", 1),
            ("Shubham Dubey", "Batsman", 1), ("Aman Rao", "Batsman", 1), ("Sushant Mishra", "Bowler", 1),
            ("Brijesh Sharma", "Bowler", 1), ("Vignesh Puthur", "Bowler", 1), ("Yash Punja", "Bowler", 1), ("Yudhvir Charak", "Bowler", 1),
        ],
        "RCB": [
            ("Virat Kohli", "Batsman", 2), ("Rajat Patidar", "Batsman", 2), ("Phil Salt", "WK", 2), ("Josh Hazlewood", "Bowler", 2),
            ("Venkatesh Iyer", "All-rounder", 1), ("Krunal Pandya", "All-rounder", 1), ("Devdutt Padikkal", "Batsman", 1),
            ("Tim David", "Batsman", 2), ("Jacob Bethell", "All-rounder", 1), ("Yash Dayal", "Bowler", 1),
            ("Bhuvneshwar Kumar", "Bowler", 1), ("Rasikh Dar", "Bowler", 1), ("Nuwan Thushara", "Bowler", 1),
            ("Jacob Duffy", "Bowler", 1), ("Romario Shepherd", "All-rounder", 1), ("Jitesh Sharma", "WK", 1),
            ("Jordan Cox", "WK", 1), ("Satvik Deswal", "Batsman", 1), ("Swapnil Singh", "All-rounder", 1),
            ("Kanishk Chouhan", "All-rounder", 1), ("Mangesh Yadav", "All-rounder", 1), ("Vihaan Malhotra", "All-rounder", 1),
            ("Vicky Ostwal", "Bowler", 1), ("Abhinandan Singh", "Bowler", 1), ("Suyash Sharma", "Bowler", 1),
        ],
        "SRH": [
            ("Travis Head", "Batsman", 2), ("Heinrich Klaasen", "WK", 2), ("Pat Cummins", "Bowler", 2), ("Abhishek Sharma", "All-rounder", 2),
            ("Ishan Kishan", "WK", 2), ("Nitish Reddy", "All-rounder", 2), ("Harshal Patel", "Bowler", 1),
            ("Liam Livingstone", "All-rounder", 1), ("Brydon Carse", "All-rounder", 1), ("Kamindu Mendis", "All-rounder", 1),
            ("Salil Arora", "WK", 1), ("Shivam Mavi", "Bowler", 1), ("Jaydev Unadkat", "Bowler", 1),
            ("Jack Edwards", "All-rounder", 1), ("Smaran Ravichandran", "Batsman", 1), ("Aniket Verma", "Batsman", 1),
            ("Shivang Kumar", "All-rounder", 1), ("Ehsan Malinga", "Bowler", 1), ("Harsh Dubey", "Bowler", 1),
            ("Amit Kumar", "Bowler", 1), ("Onkar Tarmale", "Bowler", 1), ("Krains Fuletra", "Bowler", 1),
            ("Praful Hinge", "Bowler", 1), ("Sakib Hussain", "Bowler", 1), ("Zeeshan Ansari", "Bowler", 1),
        ],
    }
    for team, players in teams.items():
        for name, role, base in players:
            db.execute("INSERT INTO players (name, team, role, base_price) VALUES (?,?,?,?)",
                       (name, team, role, base))


# ── API Routes ──────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/join", methods=["POST"])
def join():
    db = get_db()
    data = request.json
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400

    # Check if name already taken
    existing = db.execute("SELECT * FROM bidders WHERE name=?", (name,)).fetchone()
    if existing:
        return jsonify({"bidder_id": existing["id"], "name": existing["name"], "budget": existing["budget"]})

    # Check if slots available
    count = db.execute("SELECT COUNT(*) FROM bidders").fetchone()[0]
    if count >= 5:
        return jsonify({"error": "All 5 slots taken. Current bidders: " +
                        ", ".join(r["name"] for r in db.execute("SELECT name FROM bidders").fetchall())}), 400

    db.execute("INSERT INTO bidders (name, budget) VALUES (?, ?)", (name, BUDGET))
    db.commit()
    bidder = db.execute("SELECT * FROM bidders WHERE name=?", (name,)).fetchone()
    return jsonify({"bidder_id": bidder["id"], "name": bidder["name"], "budget": bidder["budget"]})


@app.route("/api/state")
def get_state():
    db = get_db()
    state = db.execute("SELECT * FROM auction_state WHERE id=1").fetchone()
    current = None
    time_left = 0
    highest_bid = 0
    highest_bidder = None

    if state["current_player_id"]:
        player = db.execute("SELECT * FROM players WHERE id=?", (state["current_player_id"],)).fetchone()
        elapsed = time.time() - (state["started_at"] or 0)
        time_left = max(0, AUCTION_DURATION - elapsed)
        if player:
            current = dict(player)
        highest_bid = state["highest_bid"] or 0
        if state["highest_bidder_id"]:
            b = db.execute("SELECT name FROM bidders WHERE id=?", (state["highest_bidder_id"],)).fetchone()
            highest_bidder = b["name"] if b else None

        # Auto-close if timer expired
        if time_left <= 0 and player and not player["sold_to"]:
            _close_auction(db, state)
            return get_state()  # recurse to get fresh state

    bidders = [dict(r) for r in db.execute("SELECT * FROM bidders ORDER BY id").fetchall()]
    unsold = db.execute("SELECT COUNT(*) FROM players WHERE sold_to IS NULL AND (sold_price IS NULL OR sold_price != -1)").fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    sold_players = [dict(r) for r in db.execute(
        "SELECT p.*, b.name as buyer_name FROM players p JOIN bidders b ON p.sold_to=b.id WHERE p.sold_to IS NOT NULL ORDER BY p.id"
    ).fetchall()]

    # Get passes for current player
    passed_ids = []
    if state["current_player_id"]:
        passed_ids = [r[0] for r in db.execute(
            "SELECT bidder_id FROM passes WHERE player_id=?", (state["current_player_id"],)).fetchall()]

        # Auto-pass bidders who already have 15 players
        for b in bidders:
            owned = db.execute("SELECT COUNT(*) FROM players WHERE sold_to=?", (b["id"],)).fetchone()[0]
            if owned >= 15 and b["id"] not in passed_ids:
                db.execute("INSERT OR IGNORE INTO passes (player_id, bidder_id) VALUES (?,?)",
                           (state["current_player_id"], b["id"]))
                passed_ids.append(b["id"])
                db.commit()

        elapsed = time.time() - (state["started_at"] or 0)

        # Auto-close if all non-leading bidders have passed (but not before MIN_DISPLAY_TIME)
        if elapsed >= MIN_DISPLAY_TIME:
            if state["highest_bidder_id"] and len(bidders) > 0:
                non_leaders = [b for b in bidders if b["id"] != state["highest_bidder_id"]]
                if non_leaders and all(b["id"] in passed_ids for b in non_leaders):
                    _close_auction(db, state)
                    return get_state()
            # Auto-close if ALL bidders passed (no bids at all — player unsold)
            if len(bidders) > 0 and len(passed_ids) >= len(bidders):
                _close_auction(db, state)
                return get_state()

    return jsonify({
        "current_player": current,
        "time_left": round(time_left),
        "highest_bid": highest_bid,
        "highest_bidder": highest_bidder,
        "bidders": bidders,
        "unsold_count": unsold,
        "total_count": total,
        "sold_players": sold_players,
        "auction_active": current is not None and time_left > 0,
        "passed_ids": passed_ids,
        "autopass_ids": [r["bidder_id"] for r in db.execute("SELECT bidder_id FROM autopass WHERE enabled=1").fetchall()],
    })


@app.route("/api/next", methods=["POST"])
def next_player():
    db = get_db()
    # Close current if any
    state = db.execute("SELECT * FROM auction_state WHERE id=1").fetchone()
    if state["current_player_id"]:
        _close_auction(db, state)

    # Pick random unsold player — higher base_price first
    unsold = db.execute("SELECT id, base_price FROM players WHERE sold_to IS NULL AND (sold_price IS NULL OR sold_price != -1) ORDER BY base_price DESC").fetchall()
    if not unsold:
        return jsonify({"error": "All players sold"}), 400

    # Group by base_price, pick from highest tier first
    max_price = unsold[0]["base_price"]
    top_tier = [r for r in unsold if r["base_price"] == max_price]
    pick = random.choice(top_tier)
    player = db.execute("SELECT * FROM players WHERE id=?", (pick["id"],)).fetchone()
    db.execute(
        "UPDATE auction_state SET current_player_id=?, started_at=?, highest_bid=?, highest_bidder_id=NULL WHERE id=1",
        (pick["id"], time.time(), 0),
    )
    db.execute("DELETE FROM passes")
    db.commit()

    # Auto-pass bidders who have autopass enabled or already have 15 players
    all_bidders = db.execute("SELECT id FROM bidders").fetchall()
    for b in all_bidders:
        owned = db.execute("SELECT COUNT(*) FROM players WHERE sold_to=?", (b["id"],)).fetchone()[0]
        autopass = db.execute("SELECT enabled FROM autopass WHERE bidder_id=?", (b["id"],)).fetchone()
        if owned >= 15 or (autopass and autopass[0]):
            db.execute("INSERT OR IGNORE INTO passes (player_id, bidder_id) VALUES (?,?)", (pick["id"], b["id"]))
    db.commit()
    return jsonify({"player": dict(player)})


@app.route("/api/bid", methods=["POST"])
def place_bid():
    db = get_db()
    data = request.json
    bidder_id = data.get("bidder_id")
    amount = data.get("amount")

    if not bidder_id or not amount:
        return jsonify({"error": "Missing bidder_id or amount"}), 400

    state = db.execute("SELECT * FROM auction_state WHERE id=1").fetchone()
    if not state["current_player_id"]:
        return jsonify({"error": "No active auction"}), 400

    elapsed = time.time() - (state["started_at"] or 0)
    if elapsed > AUCTION_DURATION:
        return jsonify({"error": "Auction expired"}), 400

    amount = float(amount)
    current_high = state["highest_bid"] or 0
    if amount <= current_high:
        return jsonify({"error": f"Bid must be higher than {current_high}"}), 400

    # First bid must be at least base price
    player = db.execute("SELECT base_price FROM players WHERE id=?", (state["current_player_id"],)).fetchone()
    if player and amount < player["base_price"]:
        return jsonify({"error": f"Bid must be at least base price ({player['base_price']})"}), 400

    bidder = db.execute("SELECT * FROM bidders WHERE id=?", (bidder_id,)).fetchone()
    if not bidder:
        return jsonify({"error": "Invalid bidder"}), 400

    # Budget guard: reserve 1 point per remaining player needed to reach 15
    owned = db.execute("SELECT COUNT(*) FROM players WHERE sold_to=?", (bidder_id,)).fetchone()[0]
    slots_needed = max(0, 14 - owned)  # 14 because current auction fills one slot
    max_bid = bidder["budget"] - slots_needed
    if max_bid < 1:
        return jsonify({"error": f"Can't bid — need {slots_needed + 1} more players but only {bidder['budget']} pts left"}), 400
    if amount > max_bid:
        return jsonify({"error": f"Max bid is {max_bid} pts (reserving {slots_needed} pts for {slots_needed} more players)"}), 400

    db.execute("INSERT INTO bids (player_id, bidder_id, amount, ts) VALUES (?,?,?,?)",
               (state["current_player_id"], bidder_id, amount, time.time()))
    db.execute("UPDATE auction_state SET highest_bid=?, highest_bidder_id=? WHERE id=1",
               (amount, bidder_id))

    # Extend timer by 15 sec on each bid, but never exceed AUCTION_DURATION
    elapsed = time.time() - (state["started_at"] or 0)
    time_left = max(0, AUCTION_DURATION - elapsed)
    new_time_left = min(AUCTION_DURATION, time_left + 15)
    new_started = time.time() - (AUCTION_DURATION - new_time_left)
    db.execute("UPDATE auction_state SET started_at=? WHERE id=1", (new_started,))

    db.commit()
    return jsonify({"success": True, "new_high": amount, "bidder": bidder["name"]})


@app.route("/api/pass", methods=["POST"])
def pass_player():
    db = get_db()
    data = request.json
    bidder_id = data.get("bidder_id")
    state = db.execute("SELECT * FROM auction_state WHERE id=1").fetchone()
    if not state["current_player_id"]:
        return jsonify({"error": "No active auction"}), 400
    if state["highest_bidder_id"] == bidder_id:
        return jsonify({"error": "You're the highest bidder — can't pass"}), 400
    db.execute("INSERT OR IGNORE INTO passes (player_id, bidder_id) VALUES (?,?)",
               (state["current_player_id"], bidder_id))
    db.commit()
    return jsonify({"success": True})


@app.route("/api/autopass", methods=["POST"])
def toggle_autopass():
    db = get_db()
    data = request.json
    bidder_id = data.get("bidder_id")
    enabled = data.get("enabled", False)
    db.execute("INSERT OR REPLACE INTO autopass (bidder_id, enabled) VALUES (?,?)",
               (bidder_id, 1 if enabled else 0))
    # If enabling autopass and there's an active auction, auto-pass current player too
    if enabled:
        state = db.execute("SELECT * FROM auction_state WHERE id=1").fetchone()
        if state["current_player_id"] and state["highest_bidder_id"] != bidder_id:
            db.execute("INSERT OR IGNORE INTO passes (player_id, bidder_id) VALUES (?,?)",
                       (state["current_player_id"], bidder_id))
    db.commit()
    return jsonify({"success": True})


@app.route("/api/optin", methods=["POST"])
def opt_in():
    """Remove pass for current player (opt back in to bid)."""
    db = get_db()
    data = request.json
    bidder_id = data.get("bidder_id")
    state = db.execute("SELECT * FROM auction_state WHERE id=1").fetchone()
    if not state["current_player_id"]:
        return jsonify({"error": "No active auction"}), 400
    db.execute("DELETE FROM passes WHERE player_id=? AND bidder_id=?",
               (state["current_player_id"], bidder_id))
    db.commit()
    return jsonify({"success": True})


@app.route("/api/reset", methods=["POST"])
def reset():
    db = get_db()
    db.executescript("""
        DELETE FROM bids; DELETE FROM passes; DELETE FROM autopass; DELETE FROM auction_state; DELETE FROM players; DELETE FROM bidders;
        INSERT INTO auction_state (id) VALUES (1);
    """)
    db.commit()
    init_db()
    return jsonify({"success": True})


@app.route("/api/export")
def export_results():
    import csv
    import io
    db = get_db()
    bidders = {r["id"]: r["name"] for r in db.execute("SELECT * FROM bidders").fetchall()}
    sold = db.execute("SELECT * FROM players WHERE sold_to IS NOT NULL ORDER BY sold_price DESC").fetchall()
    unsold = db.execute("SELECT * FROM players WHERE sold_to IS NULL ORDER BY name").fetchall()

    # JSON export
    result = {"bidders": [], "sold": [], "unsold": []}
    for b_id, b_name in bidders.items():
        budget = db.execute("SELECT budget FROM bidders WHERE id=?", (b_id,)).fetchone()
        players = db.execute("SELECT name, team, role, sold_price FROM players WHERE sold_to=? ORDER BY sold_price DESC", (b_id,)).fetchall()
        result["bidders"].append({
            "name": b_name, "remaining_budget": budget["budget"],
            "players": [dict(p) for p in players], "count": len(players),
        })
    for p in sold:
        result["sold"].append({"name": p["name"], "team": p["team"], "role": p["role"],
                                "price": p["sold_price"], "buyer": bidders.get(p["sold_to"], "?")})
    for p in unsold:
        result["unsold"].append({"name": p["name"], "team": p["team"], "role": p["role"]})

    # Save to file
    out_path = os.path.join(os.path.dirname(__file__), "auction_results.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    return jsonify({"saved_to": out_path, "results": result})


def _close_auction(db, state):
    pid = state["current_player_id"]
    if state["highest_bidder_id"] and state["highest_bid"]:
        db.execute("UPDATE players SET sold_to=?, sold_price=? WHERE id=?",
                   (state["highest_bidder_id"], state["highest_bid"], pid))
        db.execute("UPDATE bidders SET budget = budget - ? WHERE id=?",
                   (state["highest_bid"], state["highest_bidder_id"]))
    else:
        # No bids — mark as unsold (sold_price = -1 sentinel)
        db.execute("UPDATE players SET sold_price=-1 WHERE id=?", (pid,))
    db.execute("UPDATE auction_state SET current_player_id=NULL, started_at=NULL, highest_bid=0, highest_bidder_id=NULL WHERE id=1")
    db.commit()


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5050)
else:
    # For gunicorn / production
    init_db()
