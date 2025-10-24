# -*- coding: utf-8 -*-
"""
Created on Sat Oct 11 22:35:14 2025

@author: supri
"""

import re
import hashlib
import requests
from bs4 import BeautifulSoup

USER_AGENT = "KarnaBot/1.0 (+https://example.com) requests"

def split_sources_field(raw: str):
    """Split comma/newline separated URLs into list."""
    if not raw:
        return []
    parts = re.split(r"[\n,]+", raw)
    return [p.strip() for p in parts if p.strip()]

def fetch_url(url: str, timeout: int = 15):
    """Fetch URL and return HTML text."""
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        if r.status_code >= 400:
            return None
        return r.text
    except requests.RequestException:
        return None

def extract_metadata(html: str):
    """Extract title, summary, image from HTML."""
    soup = BeautifulSoup(html, "html.parser")

    def meta(name): 
        tag = soup.find("meta", attrs={"name": name})
        return tag.get("content") if tag else None

    def prop(p): 
        tag = soup.find("meta", attrs={"property": p})
        return tag.get("content") if tag else None

    title = prop("og:title") or (soup.title.string.strip() if soup.title else None) or "Untitled"
    summary = prop("og:description") or meta("description") or ""
    image = prop("og:image") or prop("twitter:image")

    return title.strip(), re.sub(r"\s+", " ", summary).strip(), image

def dedup_key_for(client_id: str, source: str):
    """Stable dedup key from client+source (URL, FB id, etc)."""
    raw = f"{client_id}|{source}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
