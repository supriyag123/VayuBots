# -*- coding: utf-8 -*-
"""
Karna WhatsApp Router (Async + GPT Intent + Deterministic Flow)
---------------------------------------------------------------
- Keeps deterministic flow
- Uses GPT only for interpreting natural text → action
- Handles slow post creation gracefully (background task)
"""

import os, json, traceback, threading
from openai import OpenAI
from twilio.twiml.messaging_response import MessagingResponse
from fastapi.responses import PlainTextResponse

from datetime import datetime

# --- Temporary in-memory buffer to hold text/image pairs ---
PENDING_IDEAS = {}

from vayu.karna.handlers.whatsapp_parser import WhatsAppParser
from vayu.karna.handlers.whatsapp_state import get_state, update_state
from vayu.karna.flows import karna_flow
from vayu.karna.tools.airtable_utils import get_client_config

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_posts_list(records):
    """Format Airtable post list nicely."""
    if not records:
        return "❌ No posts."
    lines = []
    for i, rec in enumerate(records, start=1):
        cap = rec["fields"].get("Caption", "")
        preview = (cap[:110] + "…") if len(cap) > 110 else cap
        lines.append(f"{i}. {preview}")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Background worker for long-running post creation
# ---------------------------------------------------------------------------

def _async_create_post(client_id: str, idea_text: str, image_url: str, user_id: str):
    """Run post creation asynchronously and send WhatsApp update after creation."""
    try:
        print(f"[ASYNC] Starting post creation for {client_id}: {idea_text[:50]}...")

        result = karna_flow.submit_client_input(
            client_id=client_id,
            idea_text=idea_text,
            image_url=image_url
        )

        posts_output = result.get("posts") if isinstance(result, dict) else None
        print(f"[DEBUG] posts_output type={type(posts_output)} value={posts_output}")

        # 🧩 Normalize whatever was returned
        post = None
        if isinstance(posts_output, list) and posts_output:
            post = posts_output[0]
        elif isinstance(posts_output, dict):
            post = posts_output
        elif hasattr(posts_output, "output"):  # CrewOutput object
            post = posts_output.output
        elif isinstance(posts_output, str):
            try:
                post = json.loads(posts_output)
            except:
                post = {"fields": {"Caption": posts_output}}

        # ✅ Safeguard: make sure post is a dict
        if not isinstance(post, dict):
            print("[WARN] Could not parse post object, got:", type(post))
            msg_text = "⚠️ Sorry, post creation returned an unexpected result."
        else:
            # ✅ Extract caption and image safely
            fields = post.get("fields", {})
            caption = fields.get("Caption", "[No caption]")
            image = fields.get("Image URL", None)
            post_id = post.get("id", "[Unknown ID]")

            # ✅ Save state for later 'publish'
            update_state(user_id, "post_preview", {"last_post_id": post_id})

            msg_text = f"📝 Draft created:\n{caption}"
            if image:
                msg_text += f"\n🖼️ {image}"
            msg_text += "\n\nSay 'publish' to approve or 'update' to edit."

        # ✅ Use Twilio API to send follow-up message
        from twilio.rest import Client as TwilioClient
        twilio_client = TwilioClient(os.getenv("TWILIO_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        twilio_client.messages.create(
            from_=os.getenv("TWILIO_WHATSAPP_NUMBER"),
            to=f"whatsapp:{user_id}",
            body=msg_text
        )

        print(f"[ASYNC] Post creation completed for {client_id}")

    except Exception as e:
        print(f"[ERROR] Async post creation failed: {e}")
        traceback.print_exc()


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------

def handle_message(user_id: str, text: str, image_url: str = None) -> str:
    """Main WhatsApp message handler for Karna (deterministic + GPT intent)."""
    try:
        state = get_state(user_id)
        client_id = user_id  # already Airtable ID
        text_clean = text.strip().lower()

        client_cfg = get_client_config(client_id)
        brand_voice = client_cfg.get("brand_voice", "professional")
        instructions = client_cfg.get("instructions", "")
        client_name = client_cfg.get("name", "Client")

        # 1️⃣ Parse deterministic command
        action, context = WhatsAppParser.parse_message(text_clean, client_id, state)
        if image_url:
            context["image_url"] = image_url
            update_state(user_id, state.get("last_action", "menu"), {"last_image_url": image_url})
        context["client_id"] = client_id

        # 2️⃣ GPT fallback if no deterministic match
        if not action or action == "unknown":
            system_prompt = f"""
            You are Karna, the Social Media Agent.
            Tone: {brand_voice}
            Instructions: {instructions}
            Understand the user's intent and respond with JSON:
            {{"action": "show_posts" | "curate_ideas" | "analytics" | "approve_post", "idea": "<optional text>"}}
            """

            try:
                gpt_response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ],
                    temperature=0.4
                )
                gpt_out = gpt_response.choices[0].message.content.strip()
                print(f"[GPT KARNA OUTPUT] {gpt_out}")
                parsed = json.loads(gpt_out)
                action = parsed.get("action", "unknown")
                if action == "create_post":
                    text = parsed.get("idea", text)
            except Exception as e:
                print(f"[WARN] GPT fallback failed: {e}")
                action = "unknown"

        # -------------------------------------------------------------------
        # Deterministic action flows
        # -------------------------------------------------------------------

        if action in ("greeting", "social_media_menu") or text_clean == "menu":
            update_state(user_id, "menu")
            return (
                f"👋 Hi {client_name}, Karna here – your Social Media Agent.\n"
                "What would you like to do?\n"
                "show → Show top 3 posts\n"
                "all → Show all pending posts\n"
                "new → Create a new post\n"
                "report → Report engagement\n"
                "analytics → See analytics\n"
                "Say 'exit' anytime to return to Vayu."
                
               
            )

        elif action == "show_posts":
            posts = karna_flow.list_top_posts(client_id=client_id, limit=3)
            if not posts:
                return "❌ No curated posts available right now."
            update_state(user_id, "show_posts", {"post_options": [p["id"] for p in posts]})
            return "📝 Top posts:\n" + _fmt_posts_list(posts) + "\n\nReply 'approve 1/2/3' to choose."

        elif action == "show_all_posts":
            posts = karna_flow.list_all_pending_posts(client_id=client_id, limit=50)
            if not posts:
                return "❌ No pending posts available."
            update_state(user_id, "show_posts", {"post_options": [p["id"] for p in posts]})
            return "📋 All pending posts:\n" + _fmt_posts_list(posts) + "\n\nPick one by number, or say 'none'."

        elif action == "post_selected":
            post_id = context.get("post_id")
            if not post_id:
                return "⚠️ I couldn’t find that selection. Try again with 1/2/3."
            update_state(user_id, "post_selected", {"last_post_id": post_id})
            return f"👍 Selected post {post_id}. Say 'publish' to approve or 'update' to change it."


        # ✅ FIXED approve flow
        elif action == "approve_post":
            selection = context.get("post_id")
            post_id = None

            if isinstance(selection, int):  # if user said "approve 1"
                options = state.get("post_options") or []
                if 1 <= selection <= len(options):
                    post_id = options[selection - 1]
                else:
                    return "⚠️ That number doesn’t match any post. Try 1/2/3 after 'show'."
            else:
                post_id = selection or state.get("last_post_id")

            if not post_id:
                return "⚠️ No post selected. Reply 1/2/3 after 'show posts'."

            try:
                karna_flow.approve_and_publish_post(client_id=client_id, post_id=post_id)
                update_state(user_id, "menu")
                return "✅ Post approved & publish attempted. Check your dashboard."
            except Exception as e:
                print(f"[ERROR] approve_and_publish_post failed: {e}")
                return "⚠️ Couldn’t publish that post. Please try again."

        elif action == "modify_post":
            update_state(user_id, "update_pending", {
                "last_post_id": context.get("post_id") or state.get("last_post_id"),
                "expected_mods": context.get("modifications", {})
            })
            return "✏️ Sure — send new caption text or image URL."

        elif state.get("last_action") == "update_pending":
            post_id = state.get("last_post_id")
            if not post_id:
                return "⚠️ No post selected. Use 'show posts' first."
            text_l = text_clean
            if "http" in text_l and (text_l.endswith(".jpg") or text_l.endswith(".png")):
                karna_flow.update_post_image_url(post_id, text.strip())
                msg = "🖼️ Image updated."
            else:
                karna_flow.update_post_caption(post_id, text)
                msg = "✏️ Caption updated."
            # ✅ Fetch updated post preview to show the user
            try:
                updated_post = karna_flow.get_post_by_id(post_id)
                caption = updated_post.get("fields", {}).get("Caption", "[No caption]")
                image = updated_post.get("fields", {}).get("Image URL", None)
            
                preview = f"{msg}\n\n📝 Updated caption:\n{caption}"
                if image:
                    preview += f"\n🖼️ {image}"
                preview += "\n\nSay 'publish' when ready."
            
                update_state(user_id, "post_selected", {"last_post_id": post_id})
                return preview
            
            except Exception as e:
                print(f"[WARN] Could not fetch updated post: {e}")
                update_state(user_id, "post_selected", {"last_post_id": post_id})
                return f"{msg} Say 'publish' when ready."

        # --- Step 1: Start New Post Flow (ask for idea) ---
        elif action == "curate_ideas":
            update_state(user_id, "awaiting_idea", {"step": "awaiting_idea"})
            print(f"[DEBUG] State set to awaiting_idea for user={user_id}")
            return (
                "💡 Great — let's create something new!\n"
                "Please type your idea or content (e.g., 'Promote my weekend café offer').\n"
                "You can also send an image with it.\n\n"
                "Say 'skip' to go back to menu."
            )
        
        # --- Step 2: Collect idea text or image ---
        elif state.get("last_action") == "awaiting_idea" and text_clean not in ["skip", "menu"]:
            idea_text = text.strip()
            PENDING_IDEAS[user_id] = {"idea_text": idea_text, "timestamp": datetime.now()}
            update_state(user_id, "awaiting_image")
        
            return (
                "📝 Got your idea text!\n"
                "If you want to add an image, please send it now.\n"
                "Otherwise, type 'done' to continue."
            )
        
        # --- Step 3: Handle image or 'done' confirmation ---
        elif state.get("last_action") == "awaiting_image":
            pending = PENDING_IDEAS.get(user_id)
            
            # user confirms no image
            if text_clean == "done":
                idea_text = pending.get("idea_text", "")
                update_state(user_id, "curating")
                del PENDING_IDEAS[user_id]
        
                threading.Thread(
                    target=_async_create_post,
                    args=(client_id, idea_text, None, user_id),
                    daemon=True
                ).start()
                return "⌛ Great — creating your draft post. I’ll notify you once it’s ready!"
        
            # user sends image
            elif image_url:
                idea_text = pending.get("idea_text", "")
                update_state(user_id, "curating")
                del PENDING_IDEAS[user_id]
        
                threading.Thread(
                    target=_async_create_post,
                    args=(client_id, idea_text, image_url, user_id),
                    daemon=True
                ).start()
                return "⌛ Awesome — got your image too! Creating your draft now..."

        elif action == "analytics":
            a = karna_flow.get_analytics(client_id)
            return f"📈 Analytics Summary:\n{a}"

        elif text_clean in ("skip", "none"):
            update_state(user_id, "menu")
            return "👍 No worries. Back to main menu."

        # Default fallback
        return "🤔 Not sure what you mean. Try 'show', 'new', or 'analytics'."

    except Exception as e:
        print(f"[ERROR] Karna Handler: {e}")
        traceback.print_exc()
        return "⚠️ Something went wrong. Please try again later."
