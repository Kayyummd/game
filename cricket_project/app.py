from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, emit
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os, random

# --- Flask Setup ---
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = 'super_secret_key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- SQLAlchemy Setup ---
Base = declarative_base()
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///users.db')

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password = Column(String(120), nullable=False)

def init_db():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    return engine

engine = init_db()
Session = sessionmaker(bind=engine)

# --- Auth Routes ---
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username, password = data.get("username"), data.get("password")
    if not username or not password:
        return jsonify({"success": False}), 400
    try:
        session = Session()
        new_user = User(username=username, password=generate_password_hash(password))
        session.add(new_user)
        session.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 409

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username, password = data.get("username"), data.get("password")
    session = Session()
    user = session.query(User).filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Invalid credentials"}), 401

# --- Serve HTML Pages ---
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/game")
def game():
    return render_template("game.html")

@app.route("/game_bot")
def game_bot():
    return render_template("game_bot.html")

@app.route("/room")
def room():
    return render_template("room.html")

@app.route("/multiplayer_game.html")
def multiplayer_game():
    return render_template("multiplayer_game.html")

# --- Game State Management ---
rooms = {}

@socketio.on("join_room")
def handle_join(data):
    room = data["room"]
    sid = request.sid
    username = data.get("username", "Player")
    is_host = data.get("host", False)

    if room not in rooms:
        rooms[room] = {
            "players": [],
            "host": None,
            "guest": None,
            "names": {},
            "toss_choice": None,
            "toss_result": None,
            "toss_winner": None,
            "bat_first_sid": None,
            "moves": {},
            "scores": {},
            "innings": 1,
            "outs": 0,
            "chat": [],
            "target": None
        }

    r = rooms[room]
    if sid not in r["players"]:
        r["players"].append(sid)
        r["names"][sid] = username
    if is_host:
        r["host"] = sid
    else:
        r["guest"] = sid

    join_room(room)

    if r["host"] and r["guest"] and len(r["players"]) == 2:
        emit("both_ready", {"usernames": r["names"]}, room=room)

@socketio.on("toss_choice")
def handle_toss(data):
    room = data["room"]
    choice = data["choice"]
    r = rooms.get(room)
    if not r:
        return

    result = random.choice(["Head", "Tail"])
    winner = "host" if choice == result else "guest"

    r["toss_choice"] = choice
    r["toss_result"] = result
    r["toss_winner"] = winner

    emit("toss_result", {"result": result, "winner": winner}, room=room)

@socketio.on("bat_bowl_choice")
def handle_bat_bowl(data):
    room = data["room"]
    choice = data["choice"]
    sid = request.sid
    r = rooms.get(room)
    if not r:
        return

    if choice == "Bat":
        r["bat_first_sid"] = sid
    else:
        r["bat_first_sid"] = next(p for p in r["players"] if p != sid)

    emit("game_start", {"bat_first_sid": r["bat_first_sid"], "usernames": r["names"]}, room=room)

@socketio.on("player_move")
def handle_player_move(data):
    room = data["room"]
    sid = request.sid
    move = data["move"]
    r = rooms.get(room)
    if not r:
        return

    r["moves"][sid] = move

    if len(r["moves"]) == 2:
        p1, p2 = r["players"]
        m1, m2 = r["moves"][p1], r["moves"][p2]

        batter_sid = r["bat_first_sid"] if r["innings"] == 1 else next(p for p in r["players"] if p != r["bat_first_sid"])
        r["scores"][batter_sid] = r["scores"].get(batter_sid, 0) + (m1 if batter_sid == p1 else m2)

        if m1 == m2:
            r["outs"] += 1
            emit("round_result", {"type": "out", "num": m1, "usernames": r["names"]}, room=room)
            if r["innings"] == 1:
                r["target"] = r["scores"].get(batter_sid, 0) + 1
                r["innings"] = 2
                r["outs"] = 0
                r["moves"] = {}
                return
            else:
                p1_score = r["scores"].get(p1, 0)
                p2_score = r["scores"].get(p2, 0)
                if p1_score > p2_score:
                    winner, loser = p1, p2
                elif p2_score > p1_score:
                    winner, loser = p2, p1
                else:
                    winner = loser = None
                emit("game_over", {
                    "winner": winner,
                    "loser": loser,
                    "winner_name": r["names"].get(winner, "Player") if winner else "Tie",
                    "loser_name": r["names"].get(loser, "Player") if loser else "Tie"
                }, room=room)
        else:
            emit("round_result", {
                "type": "continue",
                "moves": {p1: m1, p2: m2},
                "usernames": r["names"],
                "target": r["target"],
                "scores": r["scores"]
            }, room=room)

        r["moves"] = {}

@socketio.on("send_message")
def handle_send_message(data):
    room = data["room"]
    sid = request.sid
    r = rooms.get(room)
    if not r:
        return
    username = data.get("username") or r["names"].get(sid, "Player")
    message = data["message"]
    r["chat"].append({"username": username, "message": message})
    emit("receive_message", {"username": username, "message": message}, room=room)

@socketio.on("restart_game")
def handle_restart(data):
    room = data["room"]
    r = rooms.get(room)
    if not r:
        return
    r["moves"] = {}
    r["scores"] = {}
    r["outs"] = 0
    r["innings"] = 1
    r["target"] = None
    emit("game_start", {"bat_first_sid": r["bat_first_sid"], "usernames": r["names"]}, room=room)

# --- Run Server ---
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)
