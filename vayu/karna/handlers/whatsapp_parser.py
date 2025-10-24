"""
Parses incoming WhatsApp messages into (action, context)
-------------------------------------------------------
- Lightweight deterministic rules for fast routing
- Lets GPT handle complex, free-form text
- Supports numeric selections (approve 1/2/3)
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any


class WhatsAppParser:
    @staticmethod
    def parse_message(message: str, client_id: str, state: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        msg = message.lower().strip()

        context = {"client_id": client_id}
        last_action = state.get("last_action")
        
        

        # --- Greetings / Menu ---
        if msg in ["hi", "hello", "hey", "start", "menu"]:
            return "greeting", context
        
        # --- Done / Skip confirmation ---
        elif msg in ["done", "skip", "no", "that's all"]:
            return "done", context

        # --- Go to Social Media menu ---
        elif msg in ["1", "social media", "karna"]:
            return "social_media_menu", context

        # --- Show posts (top 3) ---
        elif any(kw in msg for kw in ["show", "see posts", "show me", "pending posts"]):
            return "show_posts", context

        # --- Show ALL posts ---
        elif any(kw in msg for kw in ["all", "show all", "all posts"]):
            return "show_all_posts", context

        # --- Create new idea ---
        elif any(kw in msg for kw in ["new", "create new", "new idea", "generate"]):
            return "curate_ideas", context

        # --- Modify / Update existing post ---
        elif any(kw in msg for kw in ["update", "edit", "change", "modify"]):
            modifications = WhatsAppParser._extract_modifications(msg)
            context.update({
                "post_id": state.get("last_post_id"),
                "modifications": modifications
            })
            return "modify_post", context

        # --- Approve / Publish post ---
        elif msg.startswith("approve") or msg == "publish":
            post_match = re.search(r'\d+', msg)
            post_index = int(post_match.group()) if post_match else None
            schedule_time = WhatsAppParser._parse_schedule_time(msg)
            context.update({"post_id": post_index, "schedule_time": schedule_time})
            return "approve_post", context

        # --- Selections after showing posts ---
        elif msg in ["1", "2", "3", "first", "second", "third"]:
            index = 0 if msg.startswith("1") or "first" in msg else 1 if msg.startswith("2") or "second" in msg else 2
            return WhatsAppParser._handle_selection(last_action, state, index, context)

        # --- Analytics / Summary / Report ---
        elif "analytics" in msg:
            return "analytics", context
        elif any(kw in msg for kw in ["summary", "report", "performance"]):
            return "summary", context

        # --- Skip / None ---
        elif msg in ["skip", "none"]:
            return "skip", context
        
        # --- If user is already mid-creation and sends free text ---
        if state.get("last_action") in ["awaiting_idea", "awaiting_image"]:
            # If they type 'done' or 'skip', handle elsewhere
            if msg in ["done", "skip", "menu"]:
                return msg, context
            # Otherwise treat it as new content for idea/image step
            if state.get("last_action") == "awaiting_idea":
                context.update({"idea_text": message.strip()})
                return "idea_text", context
            elif state.get("last_action") == "awaiting_image":
                # If they send an image, it will be attached separately
                context.update({"extra_note": message.strip()})
                return "image_note", context


        # --- If message contains creative or idea-like text ---
        elif any(kw in msg for kw in ["post about", "idea", "create post", "make a post"]):
            idea_text = WhatsAppParser._extract_idea_text(msg)
            image_url = state.get("last_image_url")
            context.update({"idea": idea_text, "image_url": image_url})
            return "create_from_idea", context

        # --- Fallback ---
        # Return None — will be passed to GPT for interpretation
        return None, context


    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _handle_selection(last_action: str, state: Dict, index: int, context: Dict) -> Tuple[str, Dict]:
        if last_action == "show_posts":
            post_options = state.get("post_options", [])
            if index < len(post_options):
                context["post_id"] = post_options[index]
                return "post_selected", context
        elif last_action == "show_ideas":
            idea_options = state.get("idea_options", [])
            if index < len(idea_options):
                context["idea_id"] = idea_options[index]
                return "idea_selected", context
        return None, context


    @staticmethod
    def _parse_schedule_time(message: str) -> Optional[datetime]:
        now = datetime.now()
        target_date = None
        if "tomorrow" in message:
            target_date = now + timedelta(days=1)
        else:
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            for i, day in enumerate(days):
                if day in message:
                    days_ahead = (i - now.weekday()) % 7 or 7
                    target_date = now + timedelta(days=days_ahead)
                    break
        if not target_date:
            return None

        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', message)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            period = time_match.group(3)
            if period == "pm" and hour < 12: hour += 12
            if period == "am" and hour == 12: hour = 0
            return target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return target_date.replace(hour=9, minute=0, second=0, microsecond=0)


    @staticmethod
    def _extract_modifications(message: str) -> Dict[str, str]:
        mods = {}
        if "image" in message or "photo" in message:
            mods["image"] = "change_requested"
        if any(kw in message for kw in ["content", "caption", "text"]):
            mods["content"] = "change_requested"
        if "hashtag" in message:
            mods["hashtags"] = "change_requested"
        return mods


    @staticmethod
    def _extract_idea_text(message: str) -> str:
        for phrase in ["take this idea", "create post", "make a post", "post about", "idea for"]:
            message = message.replace(phrase, "")
        return message.strip()
