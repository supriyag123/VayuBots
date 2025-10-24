# whatsapp_messenger.py
"""
Wraps Twilio send + helper messages (menus, previews, etc.)
"""

import os
import logging
from twilio.rest import Client

logger = logging.getLogger(__name__)

class WhatsAppMessenger:
    def __init__(self):
        self.client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        self.from_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

    def send(self, to: str, message: str):
        try:
            self.client.messages.create(from_=self.from_number, to=to, body=message)
            logger.info(f"Sent WhatsApp to {to}")
        except Exception as e:
            logger.error(f"Failed to send WhatsApp: {str(e)}")
