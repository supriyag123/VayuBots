# -*- coding: utf-8 -*-
"""
Created on Mon Oct 13 19:20:45 2025

@author: supri
"""

# utils.py

import json

REQUIRED_FIELDS = {"idea_id", "caption", "hashtags", "cta", "client_id", "quality_score"}

# agents/marketing/utils.py

import json

def validate_posts_json(raw_output: str) -> dict:
    """
    Minimal validation for agent output.
    Ensures it's JSON and contains a 'posts' list.

    Args:
        raw_output: Raw string returned from the agent

    Returns:
        dict with a "posts" list

    Raises:
        ValueError if JSON is invalid or missing 'posts'
    """
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError:
        raise ValueError("Agent output was not valid JSON")

    if not isinstance(data, dict):
        raise ValueError("Output must be a JSON object")

    if "posts" not in data:
        raise ValueError("Output must contain a 'posts' field")

    if not isinstance(data["posts"], list):
        raise ValueError("'posts' must be a list")

    return data
