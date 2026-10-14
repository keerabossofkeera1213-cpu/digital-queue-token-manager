
from flask import Flask, render_template, jsonify, request
import sqlite3
from datetime import datetime
from pathlib import Path

app = Flask(__name__)

DB_PATH = Path(__file__).with_name("queue.db")


# Initialize database
def init_db():
    conn = sqlite3.connect(DB_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_number INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Waiting',
            created_at TEXT NOT NULL,
            called_at TEXT,
            completed_at TEXT,
            session_id INTEGER NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            session_id INTEGER NOT NULL
        )
    """)

    conn.execute("""
        INSERT OR IGNORE INTO app_state (id, session_id)
        VALUES (1, 1)
    """)

    conn.commit()
    conn.close()


def get_session(conn):
    row = conn.execute(
        "SELECT session_id FROM app_state WHERE id = 1"
    ).fetchone()
    return row[0]


# Home page
@app.route("/")
def home():
    return render_template("index.html")


# Display queue details
@app.route("/api/queue", methods=["GET"])
def get_queue():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    session_id = get_session(conn)

    rows = conn.execute("""
        SELECT * FROM tokens
        WHERE session_id = ?
        ORDER BY token_number
    """, (session_id,)).fetchall()

    tokens = [dict(row) for row in rows]

    serving = next(
        (t for t in tokens if t["status"] == "Serving"),
        None
    )

    waiting = sum(
        t["status"] == "Waiting" for t in tokens
    )

    completed = sum(
        t["status"] == "Completed" for t in tokens
    )

    conn.close()

    return jsonify({
        "tokens": tokens,
        "serving": serving,
        "waiting_count": waiting,
        "completed_count": completed,
        "total_count": len(tokens),
        "session_id": session_id
    })


# Generate a new token
@app.route("/api/tokens", methods=["POST"])
def generate_token():
    conn = sqlite3.connect(DB_PATH)
    session_id = get_session(conn)

    row = conn.execute("""
        SELECT COALESCE(MAX(token_number), 0) + 1
        FROM tokens WHERE session_id = ?
    """, (session_id,)).fetchone()

    token_number = row[0]
    now = datetime.now().isoformat(timespec="seconds")

    conn.execute("""
        INSERT INTO tokens
        (token_number, status, created_at, session_id)
        VALUES (?, 'Waiting', ?, ?)
    """, (token_number, now, session_id))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Token generated successfully",
        "token_number": token_number,
        "status": "Waiting"
    }), 201


# Call the next waiting token
@app.route("/api/next", methods=["POST"])
def call_next():
    conn = sqlite3.connect(DB_PATH)
    session_id = get_session(conn)

    current = conn.execute("""
        SELECT id FROM tokens
        WHERE session_id = ? AND status = 'Serving'
        LIMIT 1
    """, (session_id,)).fetchone()

    if current:
        conn.close()
        return jsonify({
            "error": "Complete the current token first."
        }), 409

    token = conn.execute("""
        SELECT id, token_number FROM tokens
        WHERE session_id = ? AND status = 'Waiting'
        ORDER BY token_number ASC
        LIMIT 1
    """, (session_id,)).fetchone()

    if not token:
        conn.close()
        return jsonify({
            "error": "No waiting tokens available."
        }), 404

    now = datetime.now().isoformat(timespec="seconds")

    conn.execute("""
        UPDATE tokens
        SET status = 'Serving', called_at = ?
        WHERE id = ?
    """, (now, token[0]))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Next token is now serving",
        "token_number": token[1],
        "status": "Serving"
    })


# Mark the current token as completed
@app.route("/api/complete", methods=["POST"])
def complete_token():
    data = request.get_json(silent=True) or {}
    token_id = data.get("id")

    if not token_id:
        return jsonify({
            "error": "Token ID is required."
        }), 400

    conn = sqlite3.connect(DB_PATH)
    session_id = get_session(conn)

    now = datetime.now().isoformat(timespec="seconds")

    cursor = conn.execute("""
        UPDATE tokens
        SET status = 'Completed', completed_at = ?
        WHERE id = ? AND session_id = ? AND status = 'Serving'
    """, (now, token_id, session_id))

    conn.commit()
    updated = cursor.rowcount
    conn.close()

    if updated == 0:
        return jsonify({
            "error": "Serving token not found."
        }), 404

    return jsonify({
        "message": "Token completed successfully",
        "status": "Completed"
    })


# Reset queue and start a new session
@app.route("/api/reset", methods=["POST"])
def reset_queue():
    conn = sqlite3.connect(DB_PATH)

    session_id = get_session(conn) + 1

    conn.execute("""
        UPDATE app_state
        SET session_id = ?
        WHERE id = 1
    """, (session_id,))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Queue reset successfully",
        "session_id": session_id
    })


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
