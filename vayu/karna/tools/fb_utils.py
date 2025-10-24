# -*- coding: utf-8 -*-
"""
Created on Sat Oct 11 22:36:09 2025

@author: supri
"""

import requests
from datetime import datetime, timedelta

FB_API_BASE = "https://graph.facebook.com/v20.0"

def fetch_fb_posts(page_id: str, page_token: str, since_hours=48, limit=5):
    """Fetch recent posts from a managed FB Page."""
    params = {
        "access_token": page_token,
        "fields": "message,permalink_url,created_time,full_picture",
        "limit": limit,
        "since": int((datetime.utcnow() - timedelta(hours=since_hours)).timestamp()),
    }
    url = f"{FB_API_BASE}/{page_id}/posts"
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("data", [])
    except requests.RequestException:
        return []
