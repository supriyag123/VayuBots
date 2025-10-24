# -*- coding: utf-8 -*-
"""
Created on Tue Oct 14 20:45:15 2025

@author: supri
"""

"""
WhatsApp Handler - Message parsing and response formatting for Twilio WhatsApp
"""

import os
import re
import logging
from typing import Tuple, Dict, Optional, Any
from datetime import datetime, timedelta
from twilio.rest import Client

logger = logging.getLogger(__name__)

class WhatsAppHandler:
    """
    Handles WhatsApp message parsing and sending via Twilio
    Manages conversation state and context for multi-turn interactions
    """
    
    def __init__(self):
        self.twilio_client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN")
        )
        self.whatsapp_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
        
        # Conversation state storage (in production, use Redis or database)
        self.conversation_states: Dict[str, Dict[str, Any]] = {}
    
    def parse_message(self, message: str, client_id: str) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Parse incoming WhatsApp message and determine action
        
        Returns:
            (action, context) tuple where:
            - action: string identifier of the action to take
            - context: dictionary with additional parameters
        """
        message = message.lower().strip()
        context = {"client_id": client_id}
        
        # Get conversation state for this client
        state = self.conversation_states.get(client_id, {})
        last_action = state.get("last_action")
        
        # Command patterns
        if message in ["hi", "hello", "hey", "start"]:
            return "greeting", context
            
        elif "social media" in message or "social" in message:
            return "social_media_menu", context
            
        elif "show" in message or "curate" in message or "what you got" in message:
            return "show_posts", context
            
        elif message.startswith("approve"):
            # Extract post ID if provided: "approve 1" or "approve post 1"
            post_match = re.search(r'\d+', message)
            post_id = state.get("last_post_id")
            if post_match:
                post_id = int(post_match.group())
            
            # Check for schedule time: "approve and schedule tomorrow 9am"
            schedule_time = self._parse_schedule_time(message)
            
            context.update({
                "post_id": post_id,
                "schedule_time": schedule_time
            })
            return "approve_post", context
            
        elif "modify" in message or "update" in message or "change" in message:
            # User wants to modify a post
            # Extract what they want to change
            modifications = self._extract_modifications(message)
            context.update({
                "post_id": state.get("last_post_id"),
                "modifications": modifications
            })
            return "modify_post", context
            
        elif "new idea" in message or "generate" in message:
            return "curate_ideas", context
            
        elif "summary" in message or "report" in message:
            return "summary", context
            
        elif message.startswith("first") or message.startswith("1"):
            # User selected first option
            context["selection"] = 1
            if last_action == "show_posts":
                context["post_id"] = state.get("post_options", [None])[0]
                return "post_selected", context
            elif last_action == "show_ideas":
                context["idea_id"] = state.get("idea_options", [None])[0]
                return "idea_selected", context
                
        elif message.startswith("second") or message.startswith("2"):
            context["selection"] = 2
            if last_action == "show_posts":
                context["post_id"] = state.get("post_options", [None, None])[1]
                return "post_selected", context
            elif last_action == "show_ideas":
                context["idea_id"] = state.get("idea_options", [None, None])[1]
                return "idea_selected", context
                
        elif message.startswith("third") or message.startswith("3"):
            context["selection"] = 3
            if last_action == "show_posts":
                context["post_id"] = state.get("post_options", [None, None, None])[2]
                return "post_selected", context
            elif last_action == "show_ideas":
                context["idea_id"] = state.get("idea_options", [None, None, None])[2]
                return "idea_selected", context
        
        # Check if this is a custom post idea with image
        elif "take this idea" in message or "create post" in message:
            # User is providing their own idea
            idea_text = self._extract_idea_text(message)
            image_url = state.get("last_image_url")  # If they uploaded an image recently
            context.update({
                "idea": idea_text,
                "image_url": image_url
            })
            return "create_from_idea", context
        
        # Default: unknown command
        return None, context
    
    def _parse_schedule_time(self, message: str) -> Optional[datetime]:
        """Extract schedule time from message like 'tomorrow 9am' or 'friday 2pm'"""
        now = datetime.now()
        
        # Tomorrow pattern
        if "tomorrow" in message:
            target_date = now + timedelta(days=1)
        # Day of week pattern
        elif any(day in message for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
            days_map = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6
            }
            for day_name, day_num in days_map.items():
                if day_name in message:
                    days_ahead = (day_num - now.weekday()) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    target_date = now + timedelta(days=days_ahead)
                    break
        else:
            return None  # Post immediately
        
        # Extract time (e.g., "9am", "2pm", "14:30")
        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', message)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            period = time_match.group(3)
            
            if period == "pm" and hour < 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0
            
            return target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Default to 9am if time not specified
        return target_date.replace(hour=9, minute=0, second=0, microsecond=0)
    
    def _extract_modifications(self, message: str) -> Dict[str, str]:
        """Extract what the user wants to modify"""
        modifications = {}
        
        if "image" in message or "picture" in message or "photo" in message:
            modifications["image"] = "change_requested"
        
        if "content" in message or "text" in message or "caption" in message or "copy" in message:
            modifications["content"] = "change_requested"
        
        if "hashtag" in message:
            modifications["hashtags"] = "change_requested"
        
        # TODO: Extract specific modification instructions
        # This could be enhanced with NLP to extract actual changes
        
        return modifications
    
    def _extract_idea_text(self, message: str) -> str:
        """Extract the idea/content text from user's message"""
        # Remove command phrases
        idea = message
        for phrase in ["take this idea", "create post", "make a post", "post about"]:
            idea = idea.replace(phrase, "")
        
        return idea.strip()
    
    def send_message(self, to_number: str, message: str):
        """Send a WhatsApp message via Twilio"""
        try:
            self.twilio_client.messages.create(
                from_=self.whatsapp_number,
                body=message,
                to=to_number
            )
            logger.info(f"Sent WhatsApp message to {to_number}")
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {str(e)}")
    
    def send_greeting(self, phone_number: str, client_name: str):
        """Send welcome/greeting message"""
        message = (
            f"Hi {client_name}! 👋\n\n"
            "How can I help you today?\n\n"
            "• 📱 Social Media - manage posts\n"
            "• 🌐 Web - update website\n"
            "• 📊 Business Profile - manage info\n"
            "• 📧 Email Campaign - send emails"
        )
        self.send_message(phone_number, message)
    
    def send_social_media_menu(self, phone_number: str):
        """Send social media options menu"""
        message = (
            "📱 Social Media Management\n\n"
            "What would you like to do?\n\n"
            "• 'Show posts' - see curated posts\n"
            "• 'New idea' - generate new ideas\n"
            "• 'Summary' - recent activity report"
        )
        self.send_message(phone_number, message)
    
    def send_post_options(self, phone_number: str, posts: list, client_id: str):
        """Send top 3 post options for user to choose from"""
        if not posts:
            self.send_message(phone_number, "❌ No posts available right now.")
            return
        
        message = "📝 Here are your top posts for today:\n\n"
        
        post_ids = []
        for i, post in enumerate(posts[:3], 1):
            post_ids.append(post.get("id"))
            message += f"{i}. {post.get('content', '')[:100]}...\n"
            if post.get('image_url'):
                message += f"   🖼️ Image: {post['image_url']}\n"
            message += "\n"
        
        message += "Reply with the number (1, 2, or 3) to select a post!"
        
        # Store post options in conversation state
        self.conversation_states[client_id] = {
            "last_action": "show_posts",
            "post_options": post_ids,
            "timestamp": datetime.now()
        }
        
        self.send_message(phone_number, message)
    
    def send_post_preview(self, phone_number: str, post: dict, client_id: str):
        """Send a preview of a single post for approval"""
        message = (
            f"📱 Post Preview:\n\n"
            f"{post.get('content', '')}\n\n"
        )
        
        if post.get('image_url'):
            message += f"🖼️ Image: {post['image_url']}\n\n"
        
        if post.get('hashtags'):
            message += f"#️⃣ {post['hashtags']}\n\n"
        
        message += (
            "Reply:\n"
            "• 'Approve' to post now\n"
            "• 'Approve and schedule [time]' to schedule\n"
            "• 'Modify [what to change]' to edit"
        )
        
        # Store post ID in conversation state
        self.conversation_states[client_id] = {
            "last_action": "post_preview",
            "last_post_id": post.get("id"),
            "timestamp": datetime.now()
        }
        
        self.send_message(phone_number, message)
    
    def send_modified_post(self, phone_number: str, post: dict, client_id: str):
        """Send modified post for re-approval"""
        message = (
            f"✏️ Modified Post:\n\n"
            f"{post.get('content', '')}\n\n"
        )
        
        if post.get('image_url'):
            message += f"🖼️ Updated Image: {post['image_url']}\n\n"
        
        message += "How about this? Reply 'Approve' to post!"
        
        self.conversation_states[client_id] = {
            "last_action": "post_preview",
            "last_post_id": post.get("id"),
            "timestamp": datetime.now()
        }
        
        self.send_message(phone_number, message)
    
    def send_curated_ideas(self, phone_number: str, ideas: list, client_id: str):
        """Send curated content ideas"""
        if not ideas:
            self.send_message(phone_number, "❌ No ideas available right now.")
            return
        
        message = "💡 Fresh Content Ideas:\n\n"
        
        idea_ids = []
        for i, idea in enumerate(ideas[:3], 1):
            idea_ids.append(idea.get("id"))
            message += f"{i}. {idea.get('title', 'Untitled')}\n"
            message += f"   {idea.get('description', '')[:80]}...\n\n"
        
        message += "Reply with the number to create a post from that idea!"
        
        self.conversation_states[client_id] = {
            "last_action": "show_ideas",
            "idea_options": idea_ids,
            "timestamp": datetime.now()
        }
        
        self.send_message(phone_number, message)
    
    def send_summary(self, phone_number: str, summary: dict):
        """Send activity summary"""
        message = (
            f"📊 Activity Summary\n\n"
            f"Posts this week: {summary.get('posts_this_week', 0)}\n"
            f"Scheduled posts: {summary.get('scheduled_posts', 0)}\n"
            f"Ideas curated: {summary.get('ideas_curated', 0)}\n"
            f"Engagement: {summary.get('engagement_summary', 'N/A')}\n\n"
            f"Keep up the great work! 🚀"
        )
        self.send_message(phone_number, message)
    
    def update_state(self, client_id: str, action: str, data: dict):
        """Update conversation state for a client"""
        self.conversation_states[client_id] = {
            "last_action": action,
            "timestamp": datetime.now(),
            **data
        }
    
    def get_state(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation state for a client"""
        return self.conversation_states.get(client_id)
