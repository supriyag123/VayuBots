# -*- coding: utf-8 -*-
"""
Created on Sat Oct 11 23:41:54 2025

@author: supri
"""

# config/settings.py

"""
config/settings.py

Configuration settings for Karna
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Get the root directory (karna folder)
ROOT_DIR = Path(__file__).resolve().parent.parent

# Load .env file
env_path = ROOT_DIR / '.env'
load_dotenv(dotenv_path=env_path, override=True)

class Settings:
    # Airtable
    AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
    AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
    
    # OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Social Media
    FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN', '')
    IG_ACCESS_TOKEN = os.getenv('IG_ACCESS_TOKEN', '')
    LINKEDIN_ACCESS_TOKEN = os.getenv('LINKEDIN_ACCESS_TOKEN', '')

settings = Settings()

# Validate
if not settings.AIRTABLE_API_KEY or not settings.AIRTABLE_BASE_ID:
    raise ValueError("AIRTABLE_API_KEY and AIRTABLE_BASE_ID must be set in .env file")

print(f"✓ Settings loaded successfully")
print(f"  API Key: {settings.AIRTABLE_API_KEY[:15]}...")
print(f"  Base ID: {settings.AIRTABLE_BASE_ID}")
