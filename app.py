
import streamlit as st
import sqlite3
from pathlib import Path
from datetime import datetime

st.set_page_config(
    page_title="Digital Queue Manager",
    page_icon="🎟️",
    layout="wide"
)

DB_PATH = Path(__file__).with_name("queue.db")


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_number INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Waiting',
                created_at TEXT NOT NULL,
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


def get_session(conn):
    return conn.execute(
        "SELECT session_id FROM app_state WHERE id=1"
    ).fetchone()[0]


def get_tokens():
    with get_connection() as conn:
        session = get_session(conn)
        rows = conn.execute("""
            SELECT id, token_number, status, created_at
            FROM tokens
            WHERE session_id=?
            ORDER BY token_number
        """, (session,)).fetchall()
    return rows


def token_name(number):
    return f"A{number:03d}"


init_db()

st.title("🎟️ Interactive Digital Queue Manager")
st.caption("Generate tokens, monitor the queue, and manage service.")

tokens = get_tokens()

serving = next(
    (t for t in tokens if t[2] == "Serving"), None
)
waiting = [t for t in tokens if t[2] == "Waiting"]
completed = [t for t in tokens if t[2] == "Completed"]

# Dashboard statistics
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        "Now Serving",
        token_name(serving[1]) if serving else "None"
    )

with c2:
    st.metric("Waiting", len(waiting))

with c3:
    st.metric("Completed", len(completed))

with c4:
    st.metric("Total Tokens", len(tokens))


st.divider()

# Visitor token generation
st.subheader("🙋 Visitor")

if st.button("➕ Generate New Token", type="primary"):
    with get_connection() as conn:
        session = get_session(conn)
        number = conn.execute("""
            SELECT COALESCE(MAX(token_number), 0) + 1
            FROM tokens WHERE session_id=?
        """, (session,)).fetchone()[0]

        conn.execute("""
            INSERT INTO tokens
            (token_number, status, created_at, session_id)
            VALUES (?, 'Waiting', ?, ?)
        """, (
            number,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            session
        ))

    st.success(f"Your token number is {token_name(number)}")
    st.rerun()


st.divider()

# Administrator controls
st.subheader("🛠️ Administrator Controls")

col1, col2 = st.columns(2)

with col1:
    if st.button(
        "▶ Call Next Token",
        disabled=bool(serving) or not waiting,
        use_container_width=True
    ):
        next_token = waiting[0]

        with get_connection() as conn:
            conn.execute("""
                UPDATE tokens SET status='Serving'
                WHERE id=?
            """, (next_token[0],))

        st.success(
            f"Now serving {token_name(next_token[1])}"
        )
        st.rerun()

with col2:
    if st.button(
        "✅ Complete Current Token",
        disabled=not bool(serving),
        use_container_width=True
    ):
        with get_connection() as conn:
            conn.execute("""
                UPDATE tokens SET status='Completed'
                WHERE id=? AND status='Serving'
            """, (serving[0],))

        st.success(
            f"{token_name(serving[1])} completed successfully."
        )
        st.rerun()


st.divider()

# Queue display
st.subheader("📋 Queue Overview")

if tokens:
    search = st.text_input(
        "Search token number",
        placeholder="Enter a number, e.g. A001"
    ).strip().upper()

    for token in tokens:
        token_id, number, status, created = token
        name = token_name(number)

        if search and search not in name:
            continue

        if status == "Waiting":
            indicator = "🟡"
        elif status == "Serving":
            indicator = "🟣"
        else:
            indicator = "🟢"

        with st.container(border=True):
            left, middle, right = st.columns([2, 3, 2])

            left.markdown(f"### {name}")
            middle.write(f"{indicator} **{status}**")
            right.caption(f"Arrived: {created}")

else:
    st.info("No tokens yet. Generate a token to get started.")


st.divider()

# Reset queue
st.subheader("🔄 Start a New Session")

st.warning(
    "Resetting starts a new queue session. Previous session "
    "records remain in the database."
)

confirm_reset = st.checkbox("I want to start a new queue session")

if st.button(
    "Reset Queue",
    type="secondary",
    disabled=not confirm_reset
):
    with get_connection() as conn:
        session = get_session(conn)
        conn.execute("""
            UPDATE app_state SET session_id=?
            WHERE id=1
        """, (session + 1,))

    st.success("New queue session started.")
    st.rerun()
