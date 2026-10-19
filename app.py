import random
import string
import threading
from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room as socket_join_room, emit
import os




app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-for-deployment"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# In-memory game rooms. Restarting the server clears active games.
games = {}
games_lock = threading.Lock()

WIDTH, HEIGHT = 800, 500
PADDLE_W, PADDLE_H = 112, 12
BALL_R = 8
TOP_Y, BOTTOM_Y = 32, HEIGHT - 32
MAX_LIVES = 3


def new_ball():
    return {
        "x": WIDTH / 2,
        "y": HEIGHT / 2,
        "vx": random.choice([-1, 1]) * random.uniform(3.0, 4.0),
        "vy": random.choice([-1, 1]) * random.uniform(3.0, 4.0),
    }


def make_room():
    return {
        "players": {},  # sid -> "p1" or "p2"
        "paddles": {"p1": WIDTH / 2, "p2": WIDTH / 2},
        "lives": {"p1": MAX_LIVES, "p2": MAX_LIVES},
        "ball": new_ball(),
        "status": "waiting",
        "winner": None,
        "loop_started": False,
        "last_miss": None,
    }


def generate_code():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choice(alphabet) for _ in range(5))
        if code not in games:
            return code


def public_state(code):
    game = games.get(code)
    if not game:
        return None
    return {
        "room": code,
        "status": game["status"],
        "players_count": len(game["players"]),
        "paddles": dict(game["paddles"]),
        "lives": dict(game["lives"]),
        "ball": dict(game["ball"]),
        "winner": game["winner"],
        "last_miss": game["last_miss"],
    }


def broadcast_state(code):
    state = public_state(code)
    if state:
        socketio.emit("game_state", state, to=code)


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("create_game")
def create_game():
    with games_lock:
        code = generate_code()
        games[code] = make_room()
        games[code]["players"][request.sid] = "p1"
        socket_join_room(code)
        emit("joined_game", {"room": code, "player": "p1"})
        broadcast_state(code)


@socketio.on("join_game")
def join_game(data):
    code = str((data or {}).get("room", "")).strip().upper()
    with games_lock:
        game = games.get(code)
        if not game:
            emit("join_error", {"message": "Room code nahi mila. Code check karo."})
            return
        if len(game["players"]) >= 2:
            emit("join_error", {"message": "Is room mein already 2 players hain."})
            return
        if game["status"] != "waiting":
            emit("join_error", {"message": "Ye game already start ho chuka hai."})
            return

        game["players"][request.sid] = "p2"
        game["status"] = "playing"
        game["ball"] = new_ball()
        socket_join_room(code)
        emit("joined_game", {"room": code, "player": "p2"})
        broadcast_state(code)

        if not game["loop_started"]:
            game["loop_started"] = True
            socketio.start_background_task(game_loop, code)


@socketio.on("move_paddle")
def move_paddle(data):
    code = str((data or {}).get("room", "")).strip().upper()
    try:
        x = float((data or {}).get("x", WIDTH / 2))
    except (TypeError, ValueError):
        return

    with games_lock:
        game = games.get(code)
        if not game or request.sid not in game["players"]:
            return
        if game["status"] != "playing":
            return
        player = game["players"][request.sid]
        half = PADDLE_W / 2
        game["paddles"][player] = max(half, min(WIDTH - half, x))


@socketio.on("play_again")
def play_again(data):
    code = str((data or {}).get("room", "")).strip().upper()
    with games_lock:
        game = games.get(code)
        if not game or request.sid not in game["players"]:
            return
        # Both players remain in the room; either can restart the match.
        if len(game["players"]) == 2:
            game["lives"] = {"p1": MAX_LIVES, "p2": MAX_LIVES}
            game["paddles"] = {"p1": WIDTH / 2, "p2": WIDTH / 2}
            game["ball"] = new_ball()
            game["winner"] = None
            game["last_miss"] = None
            game["status"] = "playing"
            broadcast_state(code)
            if not game["loop_started"]:
                game["loop_started"] = True
                socketio.start_background_task(game_loop, code)


@socketio.on("disconnect")
def on_disconnect(reason=None):
    sid = request.sid
    with games_lock:
        for code, game in list(games.items()):
            if sid in game["players"]:
                leaving_player = game["players"].pop(sid)
                if game["status"] == "playing":
                    game["status"] = "waiting"
                    game["winner"] = None
                    game["last_miss"] = None
                socketio.emit(
                    "opponent_left",
                    {"message": "Doosra player disconnect ho gaya. Naya player join kar sakta hai."},
                    to=code,
                )
                if not game["players"]:
                    games.pop(code, None)
                else:
                    broadcast_state(code)
                break


def game_loop(code):
    tick = 1 / 60
    while True:
        socketio.sleep(tick)
        with games_lock:
            game = games.get(code)
            if not game:
                return
            if game["status"] != "playing" or len(game["players"]) < 2:
                if game["status"] == "finished":
                    # Keep room open for play-again, but stop this loop.
                    game["loop_started"] = False
                    return
                continue

            ball = game["ball"]
            ball["x"] += ball["vx"]
            ball["y"] += ball["vy"]

            if ball["x"] <= BALL_R:
                ball["x"] = BALL_R
                ball["vx"] = abs(ball["vx"])
            elif ball["x"] >= WIDTH - BALL_R:
                ball["x"] = WIDTH - BALL_R
                ball["vx"] = -abs(ball["vx"])

            # Top paddle: player 1. Bottom paddle: player 2.
            if ball["vy"] < 0 and ball["y"] - BALL_R <= TOP_Y + PADDLE_H:
                if ball["y"] >= TOP_Y - BALL_R and abs(ball["x"] - game["paddles"]["p1"]) <= PADDLE_W / 2 + BALL_R:
                    ball["y"] = TOP_Y + PADDLE_H + BALL_R
                    ball["vy"] = abs(ball["vy"]) * 1.03
                    offset = (ball["x"] - game["paddles"]["p1"]) / (PADDLE_W / 2)
                    ball["vx"] += offset * 1.1
                    ball["vx"] = max(-6.5, min(6.5, ball["vx"]))
                elif ball["y"] < 0:
                    game["lives"]["p1"] -= 1
                    game["last_miss"] = "p1"
                    if game["lives"]["p1"] <= 0:
                        game["lives"]["p1"] = 0
                        game["winner"] = "p2"
                        game["status"] = "finished"
                    else:
                        game["ball"] = new_ball()

            # Bottom paddle: player 2.
            if game["status"] == "playing" and ball["vy"] > 0 and ball["y"] + BALL_R >= BOTTOM_Y - PADDLE_H:
                if ball["y"] <= BOTTOM_Y + BALL_R and abs(ball["x"] - game["paddles"]["p2"]) <= PADDLE_W / 2 + BALL_R:
                    ball["y"] = BOTTOM_Y - PADDLE_H - BALL_R
                    ball["vy"] = -abs(ball["vy"]) * 1.03
                    offset = (ball["x"] - game["paddles"]["p2"]) / (PADDLE_W / 2)
                    ball["vx"] += offset * 1.1
                    ball["vx"] = max(-6.5, min(6.5, ball["vx"]))
                elif ball["y"] > HEIGHT:
                    game["lives"]["p2"] -= 1
                    game["last_miss"] = "p2"
                    if game["lives"]["p2"] <= 0:
                        game["lives"]["p2"] = 0
                        game["winner"] = "p1"
                        game["status"] = "finished"
                    else:
                        game["ball"] = new_ball()

            broadcast_state(code)


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )