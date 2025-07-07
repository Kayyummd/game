from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, join_room, emit
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os, random

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
    raw_password = Column(String(120), nullable=False)  # For admin viewing
    role = Column(String(20), default='user')  # user / admin
    mode = Column(String(20), default='none')  # bot / multiplayer

def init_db():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    if not session.query(User).filter_by(username='admin').first():
        admin_password = 'Admin@123'
        admin_user = User(
            username='admin',
            password=generate_password_hash(admin_password),
            raw_password=admin_password,
            role='admin'
        )
        session.add(admin_user)
        session.commit()
    session.close()
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
    session = Session()
    if session.query(User).filter_by(username=username).first():
        return jsonify({"success": False, "message": "Username already exists"}), 409
    new_user = User(
        username=username,
        password=generate_password_hash(password),
        raw_password=password
    )
    session.add(new_user)
    session.commit()
    session.close()
    return jsonify({"success": True})

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username, password = data.get("username"), data.get("password")
    session = Session()
    user = session.query(User).filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        with open("login_history.log", "a") as f:
            f.write(f"{username} logged in successfully\n")
        is_admin = user.role == 'admin'
        session.close()
        return jsonify({"success": True, "is_admin": is_admin})
    session.close()
    return jsonify({"success": False, "message": "Invalid credentials"}), 401

@app.route("/set_mode", methods=["POST"])
def set_mode():
    data = request.get_json()
    username = data.get("username")
    mode = data.get("mode")
    if not username or mode not in ["bot", "multiplayer"]:
        return jsonify({"success": False, "message": "Invalid input"}), 400
    session = Session()
    user = session.query(User).filter_by(username=username).first()
    if user:
        user.mode = mode
        session.commit()
        session.close()
        return jsonify({"success": True})
    session.close()
    return jsonify({"success": False, "message": "User not found"}), 404

# ✅ NEW ROUTE: Log user playing mode
@app.route("/track_mode", methods=["POST"])
def track_mode():
    data = request.get_json()
    username = data.get("username")
    mode = data.get("mode")
    if not username or not mode:
        return jsonify({"success": False, "message": "Missing data"}), 400
    with open("login_history.log", "a") as f:
        f.write(f"{username} started playing in {mode} mode\n")
    return jsonify({"success": True})

# --- Admin Helper ---
def is_admin(auth):
    if not auth or not auth.username:
        return False
    session = Session()
    admin_user = session.query(User).filter_by(username=auth.username).first()
    valid = admin_user and check_password_hash(admin_user.password, auth.password) and admin_user.role == 'admin'
    session.close()
    return valid

# --- Admin Routes ---
@app.route("/admin/users", methods=["GET"])
def get_users():
    if not is_admin(request.authorization):
        return jsonify({"error": "Unauthorized"}), 401
    session = Session()
    users = session.query(User).filter(User.username != "admin").all()
    result = [
        {
            "id": u.id,
            "username": u.username,
            "password": u.raw_password,
            "role": u.role,
            "mode": u.mode
        } for u in users
    ]
    session.close()
    return jsonify(result)

@app.route("/admin/delete_user/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    if not is_admin(request.authorization):
        return jsonify({"error": "Unauthorized"}), 401
    session = Session()
    user = session.query(User).filter_by(id=user_id).first()
    if user and user.username != "admin":
        session.delete(user)
        session.commit()
        session.close()
        return jsonify({"success": True})
    session.close()
    return jsonify({"success": False, "message": "Cannot delete admin or user not found"})

@app.route("/admin/promote/<int:user_id>", methods=["POST"])
def promote_user(user_id):
    if not is_admin(request.authorization):
        return jsonify({"error": "Unauthorized"}), 401
    session = Session()
    user = session.query(User).filter_by(id=user_id).first()
    if user:
        user.role = "admin"
        session.commit()
        with open("login_history.log", "a") as f:
            f.write(f"{user.username} was promoted to admin\n")
        session.close()
        return jsonify({"success": True, "message": f"{user.username} promoted to admin"})
    session.close()
    return jsonify({"success": False, "message": "User not found"})

@app.route("/admin/add_user", methods=["POST"])
def add_user_by_admin():
    if not is_admin(request.authorization):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    username, password = data.get("username"), data.get("password")
    if not username or not password:
        return jsonify({"success": False, "message": "Username and password required"})
    session = Session()
    if session.query(User).filter_by(username=username).first():
        return jsonify({"success": False, "message": "User already exists"})
    new_user = User(username=username, password=generate_password_hash(password), raw_password=password)
    session.add(new_user)
    session.commit()
    session.close()
    return jsonify({"success": True, "message": "User added successfully"})

@app.route("/admin/logins", methods=["GET"])
def view_logins():
    if not is_admin(request.authorization):
        return jsonify({"error": "Unauthorized"}), 401
    if os.path.exists("login_history.log"):
        with open("login_history.log", "r") as f:
            logs = f.readlines()
        return jsonify({"logs": logs})
    return jsonify({"logs": []})

# --- Pages ---
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

@app.route("/admin")
def admin_page():
    return render_template("admin.html")

# --- Multiplayer Game Logic ---
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
        if m1 == m2:
            if r["innings"] == 1:
                r["target"] = r["scores"].get(batter_sid, 0) + 1
                r["innings"] = 2
            else:
                scores = r["scores"]
                p1_score = scores.get(p1, 0)
                p2_score = scores.get(p2, 0)
                winner = p1 if p1_score > p2_score else p2 if p2_score > p1_score else None
                emit("game_over", {
                    "winner_sid": winner,
                    "winner_name": r["names"].get(winner, "Tie") if winner else "Tie",
                    "usernames": r["names"]
                }, room=room)
                r["target"] = None
            emit("round_result", {
                "type": "out",
                "num": m1,
                "moves": {p1: m1, p2: m2},
                "usernames": r["names"]
            }, room=room)
        else:
            if batter_sid == p1:
                r["scores"][p1] = r["scores"].get(p1, 0) + m1
            else:
                r["scores"][p2] = r["scores"].get(p2, 0) + m2
            if r["innings"] == 2 and r["target"] is not None and r["scores"].get(batter_sid, 0) >= r["target"]:
                emit("game_over", {
                    "winner_sid": batter_sid,
                    "winner_name": r["names"].get(batter_sid, "Player"),
                    "usernames": r["names"]
                }, room=room)
                r["target"] = None
                r["moves"] = {}
                return
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
