"""
Hybrid session manager (In-memory + Airtable fallback)
------------------------------------------------------
- Keeps fast in-memory access for most messages
- Syncs every update to Airtable (Sessions table)
- Automatically restores sessions after restart
"""

import json, threading
from datetime import datetime, timedelta
from typing import Dict, Any
from vayu.karna.tools.airtable_utils import airtable_client  # your Airtable wrapper

# Airtable config
BASE_ID = "appSzleU4aCL8p0qG"     # ✅ replace with your actual base ID
TABLE = "Sessions"                # ✅ create this in Airtable

# In-memory cache
SESSIONS: Dict[str, Dict[str, Any]] = {}
SESSION_TIMEOUT = 15 * 60  # 15 minutes


# --------------------------------------------------
# Core helpers
# --------------------------------------------------

def get_session(user_id: str) -> Dict[str, Any]:
    """Retrieve session for a user; auto-refresh from Airtable if missing."""
    now = datetime.now()

    # 1️⃣ In-memory fast path
    session = SESSIONS.get(user_id)
    if session and (now - session["timestamp"]).seconds <= SESSION_TIMEOUT:
        return session

    # 2️⃣ Try restoring from Airtable
    try:
        recs = airtable_client.list(BASE_ID, TABLE, filterByFormula=f"{{UserID}}='{user_id}'")
        if recs and recs.get("records"):
            fields = recs["records"][0]["fields"]
            session_data = json.loads(fields.get("SessionJSON", "{}"))
            session_data["timestamp"] = now
            SESSIONS[user_id] = session_data
            return session_data
    except Exception as e:
        print(f"[WARN] get_session Airtable failed: {e}")

    # 3️⃣ Fallback: new empty session
    new_session = {"active_agent": None, "timestamp": now}
    SESSIONS[user_id] = new_session
    return new_session


def set_session(user_id: str, agent: str, extra: Dict[str, Any] = None):
    """Set or update session locally and asynchronously persist to Airtable."""
    session = get_session(user_id)
    session.update({
        "active_agent": agent,
        "timestamp": datetime.now()
    })
    if extra:
        session.update(extra)

    SESSIONS[user_id] = session
    threading.Thread(target=_save_to_airtable, args=(user_id, session), daemon=True).start()
    return session


def reset_session(user_id: str):
    """Clear session locally + in Airtable."""
    SESSIONS[user_id] = {"active_agent": None, "timestamp": datetime.now()}
    threading.Thread(target=_delete_from_airtable, args=(user_id,), daemon=True).start()


# --------------------------------------------------
# Airtable background ops
# --------------------------------------------------

def _save_to_airtable(user_id: str, session: Dict[str, Any]):
    """Background save to Airtable."""
    try:
        recs = airtable_client.list(BASE_ID, TABLE, filterByFormula=f"{{UserID}}='{user_id}'")
        payload = {
            "UserID": user_id,
            "SessionJSON": json.dumps({k: v for k, v in session.items() if k != "timestamp"})
        }

        if recs and recs.get("records"):
            rec_id = recs["records"][0]["id"]
            airtable_client.update(BASE_ID, TABLE, rec_id, payload)
        else:
            airtable_client.create(BASE_ID, TABLE, payload)
    except Exception as e:
        print(f"[WARN] Failed to save session to Airtable for {user_id}: {e}")


def _delete_from_airtable(user_id: str):
    """Background delete session record."""
    try:
        recs = airtable_client.list(BASE_ID, TABLE, filterByFormula=f"{{UserID}}='{user_id}'")
        if recs and recs.get("records"):
            rec_id = recs["records"][0]["id"]
            airtable_client.delete(BASE_ID, TABLE, rec_id)
    except Exception as e:
        print(f"[WARN] Failed to delete session from Airtable: {e}")
