
import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
from io import StringIO

# ---------------- APP CONFIG ----------------
st.set_page_config(
    page_title="QueueFlow | Smart Queue Manager",
    page_icon="🎟️",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = Path(__file__).with_name("queue.db")
WAIT_MINUTES = 5

# ---------------- CUSTOM DESIGN ----------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}
.stApp {
    background: #f5f7fc;
}
.block-container {
    max-width: 1450px;
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}
.hero {
    padding: 28px 30px;
    border-radius: 20px;
    background: linear-gradient(120deg, #5145d9, #8175fa);
    color: white;
    margin-bottom: 25px;
    box-shadow: 0 10px 30px rgba(81,69,217,.15);
}
.hero h1 {
    color: white;
    font-size: 34px;
    margin: 0;
    font-weight: 800;
}
.hero p {
    color: #eceaff;
    margin: 8px 0 0;
}
.metric-card {
    background: white;
    padding: 20px;
    border-radius: 15px;
    border: 1px solid #e8ebf3;
    min-height: 115px;
}
.metric-label {
    color: #7d8798;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .7px;
}
.metric-value {
    color: #20283a;
    font-size: 30px;
    font-weight: 800;
    margin-top: 9px;
}
.token-card {
    background: white;
    padding: 17px 20px;
    border: 1px solid #e6eaf2;
    border-radius: 13px;
    margin: 8px 0;
}
.token-number {
    color: #5d50dc;
    font-size: 23px;
    font-weight: 800;
}
.status-waiting {
    color: #9a6508;
    background: #fff3d8;
    padding: 5px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
}
.status-serving {
    color: #5749ce;
    background: #eeebff;
    padding: 5px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
}
.status-completed {
    color: #137b58;
    background: #def7eb;
    padding: 5px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
}
.status-other {
    color: #687385;
    background: #edf0f5;
    padding: 5px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
}
section[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #e8ebf3;
}
div.stButton > button {
    border-radius: 10px;
    font-weight: 700;
    min-height: 42px;
}
div[data-testid="stMetric"] {
    background: white;
    padding: 15px;
    border-radius: 13px;
    border: 1px solid #e8ebf3;
}
</style>
""", unsafe_allow_html=True)


# ---------------- DATABASE ----------------
def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


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
    row = conn.execute(
        "SELECT session_id FROM app_state WHERE id=1"
    ).fetchone()
    return row["session_id"]


def get_tokens():
    with get_connection() as conn:
        session_id = get_session(conn)
        rows = conn.execute("""
            SELECT id, token_number, status, created_at
            FROM tokens
            WHERE session_id=?
            ORDER BY token_number
        """, (session_id,)).fetchall()
        return [dict(row) for row in rows]


def token_name(number):
    return f"A{number:03d}"


def set_status(token_id, status):
    with get_connection() as conn:
        session_id = get_session(conn)
        cursor = conn.execute("""
            UPDATE tokens SET status=?
            WHERE id=? AND session_id=?
        """, (status, token_id, session_id))
        return cursor.rowcount > 0


def add_token():
    with get_connection() as conn:
        session_id = get_session(conn)
        next_number = conn.execute("""
            SELECT COALESCE(MAX(token_number), 0) + 1
            FROM tokens WHERE session_id=?
        """, (session_id,)).fetchone()[0]

        conn.execute("""
            INSERT INTO tokens
                (token_number, status, created_at, session_id)
            VALUES (?, 'Waiting', ?, ?)
        """, (
            next_number,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            session_id
        ))
    return next_number


init_db()

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.markdown("## 🎟️ QueueFlow")
    st.caption("Smart Digital Queue Management")
    st.divider()

    page = st.radio(
        "NAVIGATION",
        ["Dashboard", "Manage Queue", "Reports & History"],
        label_visibility="visible"
    )

    st.divider()
    st.markdown("### ⚙️ Queue Settings")
    st.caption(f"Estimated service time: {WAIT_MINUTES} minutes per token")
    if st.button("🔄 Refresh Dashboard", use_container_width=True):
        st.rerun()

    st.divider()
    st.caption("QueueFlow · Digital Queue Simulation")


# ---------------- LOAD QUEUE ----------------
tokens = get_tokens()
serving = next((t for t in tokens if t["status"] == "Serving"), None)
waiting = [t for t in tokens if t["status"] == "Waiting"]
completed = [t for t in tokens if t["status"] == "Completed"]
cancelled = [t for t in tokens if t["status"] == "Cancelled"]
skipped = [t for t in tokens if t["status"] == "Skipped"]
active_tokens = [t for t in tokens if t["status"] not in ("Cancelled", "Skipped")]

# ---------------- HEADER ----------------
st.markdown("""
<div class="hero">
    <h1>QueueFlow Dashboard</h1>
    <p>Manage visitors, track service progress, and reduce waiting time.</p>
</div>
""", unsafe_allow_html=True)


# ---------------- DASHBOARD ----------------
if page == "Dashboard":
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "🔔 Now Serving",
            token_name(serving["token_number"]) if serving else "—"
        )
    with c2:
        st.metric("🟡 Waiting", len(waiting))
    with c3:
        st.metric("✅ Completed", len(completed))
    with c4:
        st.metric("🎟️ Total Tokens", len(tokens))

    st.write("")

    left, right = st.columns([1.25, 1])

    with left:
        st.subheader("📢 Current Service")

        if serving:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">NOW SERVING</div>
                <div class="metric-value" style="color:#5d50dc;font-size:46px">
                    {token_name(serving["token_number"])}
                </div>
                <p style="color:#748095">Service in progress</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("No token is currently being served.")

        st.subheader("⏭️ Next in Line")
        if waiting:
            st.markdown(
                f"### {token_name(waiting[0]['token_number'])}"
            )
            st.caption(f"{len(waiting)} visitor(s) waiting in the queue.")
        else:
            st.write("No visitors are waiting.")

    with right:
        st.subheader("📊 Queue Statistics")
        stats = pd.DataFrame({
            "Status": ["Waiting", "Serving", "Completed", "Cancelled", "Skipped"],
            "Count": [
                len(waiting),
                1 if serving else 0,
                len(completed),
                len(cancelled),
                len(skipped)
            ]
        })
        st.bar_chart(stats.set_index("Status"))

        if waiting:
            st.info(
                f"Approximate wait for the last waiting token: "
                f"{len(waiting) * WAIT_MINUTES} minutes. "
                "This is an estimate, not a guaranteed service time."
            )

    st.subheader("🧾 Recent Tokens")
    if tokens:
        recent = list(reversed(tokens[-5:]))
        for token in recent:
            status = token["status"]
            st.markdown(
                f"**{token_name(token['token_number'])}** · "
                f"`{status}` · {token['created_at']}"
            )
    else:
        st.info("No tokens generated in this session yet.")


# ---------------- MANAGE QUEUE ----------------
elif page == "Manage Queue":
    st.subheader("🛠️ Administrator Controls")
    st.caption("Call, complete, skip, or cancel tokens in the active session.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### ▶ Call Next Token")
        if serving:
            st.warning(
                f"{token_name(serving['token_number'])} is still being served. "
                "Complete it before calling another token."
            )
        elif not waiting:
            st.info("There are no waiting tokens.")
        else:
            st.success(
                f"Next token: {token_name(waiting[0]['token_number'])}"
            )

        if st.button(
            "▶ Call Next",
            type="primary",
            use_container_width=True,
            disabled=bool(serving) or not waiting
        ):
            set_status(waiting[0]["id"], "Serving")
            st.success(
                f"Now serving {token_name(waiting[0]['token_number'])}"
            )
            st.rerun()

    with col2:
        st.markdown("#### ✅ Complete Service")
        if serving:
            st.info(
                f"Current token: {token_name(serving['token_number'])}"
            )
        else:
            st.info("No active token to complete.")

        if st.button(
            "✅ Mark Completed",
            use_container_width=True,
            disabled=not bool(serving)
        ):
            set_status(serving["id"], "Completed")
            st.success("Service completed successfully.")
            st.rerun()

    st.divider()
    st.subheader("🎟️ Generate Visitor Token")

    if st.button("➕ Generate New Token", use_container_width=True):
        number = add_token()
        st.success(f"Token {token_name(number)} generated.")
        st.rerun()

    st.divider()
    st.subheader("🔧 Additional Token Actions")

    actionable = [
        t for t in tokens
        if t["status"] in ("Waiting", "Serving")
    ]

    if actionable:
        labels = {
            f"{token_name(t['token_number'])} — {t['status']}": t
            for t in actionable
        }
        selected_label = st.selectbox(
            "Select a token",
            list(labels.keys())
        )
        selected = labels[selected_label]

        action = st.selectbox(
            "Choose action",
            ["Skip token", "Cancel token"]
        )

        if st.button("Apply Action", use_container_width=True):
            if selected["status"] == "Serving":
                st.error(
                    "Complete the serving token before skipping or cancelling it."
                )
            else:
                new_status = (
                    "Skipped" if action == "Skip token" else "Cancelled"
                )
                set_status(selected["id"], new_status)
                st.success(
                    f"{token_name(selected['token_number'])} marked {new_status}."
                )
                st.rerun()
    else:
        st.info("There are no active tokens to skip or cancel.")

    st.divider()
    st.subheader("🔄 Reset Queue Session")

    st.warning(
        "This starts a new session and resets token numbering. "
        "Previous session records are retained."
    )

    confirm = st.checkbox("Confirm that you want to start a new session")

    if st.button("Reset Queue", disabled=not confirm, use_container_width=True):
        with get_connection() as conn:
            session_id = get_session(conn)
            conn.execute("""
                UPDATE app_state SET session_id=?
                WHERE id=1
            """, (session_id + 1,))

        st.success("A new queue session has started.")
        st.rerun()

    st.divider()
    st.subheader("📋 Active Queue")

    if tokens:
        df = pd.DataFrame(tokens)
        df["Token"] = df["token_number"].apply(token_name)
        df = df.rename(columns={
            "status": "Status",
            "created_at": "Arrival Time"
        })
        st.dataframe(
            df[["Token", "Status", "Arrival Time"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("The queue is empty.")


# ---------------- REPORTS ----------------
elif page == "Reports & History":
    st.subheader("📈 Queue Reports")
    st.caption("Review current-session token records and export them as CSV.")

    report = pd.DataFrame(tokens)

    if report.empty:
        st.info("No records are available in this session.")
    else:
        report["Token"] = report["token_number"].apply(token_name)
        report = report.rename(columns={
            "status": "Status",
            "created_at": "Arrival Time"
        })

        st.dataframe(
            report[["Token", "Status", "Arrival Time"]],
            use_container_width=True,
            hide_index=True
        )

        csv_data = report[
            ["Token", "Status", "Arrival Time"]
        ].to_csv(index=False)

        st.download_button(
            "⬇️ Download Queue Report (CSV)",
            data=csv_data,
            file_name=f"queue_report_{datetime.now():%Y%m%d_%H%M%S}.csv",
            mime="text/csv",
            use_container_width=True
        )

        st.divider()
        st.subheader("📊 Status Breakdown")
        st.bar_chart(report["Status"].value_counts())

st.divider()
st.caption("QueueFlow · Digital Queue Management System")
