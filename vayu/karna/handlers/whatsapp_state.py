"""
Conversation state storage for WhatsApp sessions.
Now with optional Airtable persistence for continuity.
"""

import json
from datetime import datetime
from typing import Dict, Any
from vayu.karna.tools.airtable_utils import airtable_client

STATE: Dict[str, Dict[str, Any]] = {}
SESSION_TIMEOUT = 15 * 60  # 15 minutes
BASE_ID = "appSzleU4aCL8p0qG"
TABLE = "WhatsAppState"

# -------------------------------------------------------
# Core in-memory functions
# -------------------------------------------------------

def get_state(client_id: str) -> Dict[str, Any]:
    now = datetime.now()
    session = STATE.get(client_id)

    # 1️⃣ In-memory fast path
    if session and (now - session["timestamp"]).seconds <= SESSION_TIMEOUT:
        return session

    # 2️⃣ Try restore from Airtable (optional)
    try:
        recs = airtable_client.list(BASE_ID, TABLE, filterByFormula=f"{{ClientID}}='{client_id}'")
        if recs and recs.get("records"):
            fields = recs["records"][0]["fields"]
            state_data = json.loads(fields.get("StateJSON", "{}"))
            state_data["timestamp"] = now
            STATE[client_id] = state_data
            return state_data
    except Exception as e:
        print(f"[WARN] get_state Airtable failed: {e}")

    # 3️⃣ Default empty
    new_state = {"last_action": None, "timestamp": now}
    STATE[client_id] = new_state
    return new_state


def update_state(client_id: str, action: str, data: Dict[str, Any] = None):
    state_data = {
        "last_action": action,
        "timestamp": datetime.now(),
        **(data or {})
    }
    STATE[client_id] = state_data
    _save_to_airtable(client_id, state_data)


# -------------------------------------------------------
# Persistence helper
# -------------------------------------------------------

def _save_to_airtable(client_id: str, state_data: Dict[str, Any]):
    try:
        # remove or convert datetime objects
        safe_data = {
            k: (v.isoformat() if isinstance(v, datetime) else v)
            for k, v in state_data.items()
        }

        recs = airtable_client.list(BASE_ID, TABLE, filterByFormula=f"{{ClientID}}='{client_id}'")
        fields = {
            "ClientID": client_id,
            "StateJSON": json.dumps(safe_data),
            "LastUpdated": datetime.utcnow().isoformat() + "Z"
        }
        if recs and recs.get("records"):
            rec_id = recs["records"][0]["id"]
            airtable_client.update(BASE_ID, TABLE, rec_id, fields)
        else:
            airtable_client.create(BASE_ID, TABLE, fields)
    except Exception as e:
        print(f"[WARN] Failed to persist WhatsApp state for {client_id}: {e}")
