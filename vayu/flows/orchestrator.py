from vayu.karna.handlers.whatsapp_router import handle_message as karna_handler
from vayu.flows.session import get_session, set_session, reset_session
from vayu.karna.tools.airtable_utils import get_client_id_from_phone, get_client_config


def vayu_orchestrator(user_id: str, user_name: str, text: str, image_url: str = None) -> str:
    """Vayu orchestrator — delegates work to agents but keeps user-facing control."""
    session = get_session(user_id)
    text_clean = text.strip().lower()
    active_agent = session.get("active_agent")

    # --- Reset greeting ---
    if text_clean in ["hi", "hello", "hey", "start"]:
        reset_session(user_id)
        return (
            f"Good day {user_name}, I’m Vayu – your Lead AI Agent 🤖\n"
            "How can I assist today?\n"
            "1️⃣ Social Media Management\n"
            "2️⃣ Digital Presence\n"
            "3️⃣ Lead Generation\n"
            "4️⃣ Email Campaigns"
        )

    # --- Exit current agent ---
    if text_clean in ["exit", "back"]:
        reset_session(user_id)
        return (
            f"Welcome back, {user_name}! 👋 I’m Vayu again.\n"
            "What would you like to focus on next?\n"
            "1️⃣ Social Media\n"
            "2️⃣ Digital Presence\n"
            "3️⃣ Lead Generation\n"
            "4️⃣ Email Campaign"
        )

    # --- Delegate to existing active agent ---
    if active_agent == "karna":
        try:
            print("Active agent is KARNA")
            karna_reply = karna_handler(user_id, text_clean, image_url=image_url)
            return f"🤖 Karna says:\n{karna_reply}"
        except Exception as e:
            print(f"[ERROR] Karna follow-up failed: {e}")
            return "⚠️ Karna encountered an error. Try again or say 'exit' to return."

    # --- First-time delegation to Karna ---
    elif any(k in text_clean for k in ["1", "social media", "karna", "post", "content", "facebook", "instagram"]):
        set_session(user_id, "karna")
        print("session set - agent KARNA")
        intro = (
            f"💬 No worries, {user_name}. "
            "I’ve called upon Karna — our Social Media Agent — to handle this.\n"
            "You can now directly chat with Karna. Say 'exit' anytime to return to me."
        )
        try:
            karna_reply = karna_handler(user_id, "menu")  # show menu first
            return f"{intro}\n\n{karna_reply}"
        except Exception as e:
            print(f"[ERROR] Karna init failed: {e}")
            return "⚠️ Karna couldn’t be reached right now. Please try again later."

    # --- Other agents placeholders ---
    elif text_clean in ["2", "digital presence"]:
        set_session(user_id, "digital")
        return "🌐 Digital Presence agent coming soon."

    elif text_clean in ["3", "lead generation"]:
        set_session(user_id, "leadgen")
        return "📈 Lead Generation agent coming soon."

    elif text_clean in ["4", "email", "email campaign"]:
        set_session(user_id, "email")
        return "📧 Email Campaign agent coming soon."

    # --- Fallback ---
    else:
        return (
            "🤖 I’m Vayu. Please choose an option:\n"
            "1️⃣ Social Media\n"
            "2️⃣ Digital Presence\n"
            "3️⃣ Lead Generation\n"
            "4️⃣ Email Campaign"
        )
