# -*- coding: utf-8 -*-
"""
Created on Sat Oct 11 22:36:35 2025

@author: supri
"""


"""
jobs/ingest_ideas_daily.py

Idea Agent: Harvests content from multiple sources and creates Ideas in Airtable
Runs for all active clients
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import sys
import os
from urllib.parse import urljoin
# Load environment variables directly
from dotenv import load_dotenv
import os
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.airtable_utils import list_active_clients, create_idea

from requests_html import HTMLSession

def scrape_website(url, max_items=5):
    """
    Scrape a website for ideas using requests_html (JS rendering).
    Mimics Make.com HTML-to-Text behavior.
    """
    ideas = []
    try:
        session = HTMLSession()
        r = session.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/122.0.0.0 Safari/537.36"
        })

        # render JS (like a browser)
        r.html.render(timeout=20, sleep=2)  

        # Grab top headlines (h1, h2, h3)
        headlines = r.html.find("h1, h2, h3")[:max_items]
        for h in headlines:
            headline = h.text.strip()
            if not headline:
                continue

            # Try to grab a following paragraph
            sib = h.element.getnext()
            summary = sib.text.strip() if sib is not None and hasattr(sib, "text") else headline

            ideas.append({
                "headline": headline,
                "summary": summary[:500],
                "image_url": None,
                "source_detail": url,
                "source_type": "Web"
            })

    except Exception as e:
        print(f"  ✗ Error scraping {url}: {e}")

    return ideas


def scrape_fb_page(page_id, access_token):
    """Fetch recent posts from a Facebook page via Graph API."""
    ideas = []
    try:
        url = f"https://graph.facebook.com/v18.0/{page_id}/posts"
        params = {
            "access_token": access_token,
            "fields": "message,created_time,full_picture,permalink_url",
            "limit": 5
        }
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        for post in data.get("data", []):
            message = post.get("message", "")
            if not message:
                continue
            ideas.append({
                "headline": (message[:100] + "...") if len(message) > 100 else message,
                "summary": message,
                "image_url": post.get("full_picture"),
                "source_detail": post.get("permalink_url") or f"FB Page {page_id}",
                "source_type": "Facebook"
            })
    except Exception as e:
        print(f"  ✗ Error fetching FB page {page_id}: {e}")
    return ideas


def harvest_for_client(client):
    """Harvest ideas from all sources for one client."""
    fields = client["fields"]
    all_ideas = []

    # Website sources
    sources_raw = fields.get("Reference URLs", "")
    urls = [s.strip() for s in sources_raw.replace(",", "\n").split("\n") if s.strip()]
    for url in urls:
        if url.startswith("http"):
            print(f"  Scraping website: {url}")
            all_ideas.extend(scrape_website(url))

    # Facebook sources
    page_id = fields.get("FB Page ID")
    token = fields.get("FB Page Token")
    if page_id and token:
        print(f"  Fetching FB page: {page_id}")
        all_ideas.extend(scrape_fb_page(page_id, token))

    return all_ideas


def run_ingest_ideas_daily(dry_run=False):
    """Main job: Harvest for all active clients."""
    print(f"\n{'='*60}")
    print("Idea Agent - Ingestion Job")
    print(f"{'='*60}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n")

    clients = list_active_clients()
    print(f"Found {len(clients)} active client(s)\n")

    total_ideas = 0
    for client in clients:
        client_name = client["fields"].get("Name", client["id"])
        print(f"\n── Processing client: {client_name} ──")
        try:
            ideas = harvest_for_client(client)
            print(f"  Harvested {len(ideas)} ideas")

            for idea in ideas:
                if dry_run:
                    print(f"  [DRY RUN] {idea['headline'][:60]}...")
                else:
                    create_idea(
                        client_id=client["id"],
                        headline=idea["headline"],
                        summary=idea["summary"],
                        source_type=idea["source_type"],
                        image_url=idea.get("image_url"),
                        source_detail=idea["source_detail"],
                        priority="Med"
                    )
                    print(f"  ✓ Created: {idea['headline'][:60]}...")
                total_ideas += 1
        except Exception as e:
            print(f"  ✗ Error processing {client_name}: {e}")
            continue

    print(f"\n{'='*60}")
    print(f"Completed: {total_ideas} idea(s) {'would be created' if dry_run else 'created'}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run_ingest_ideas_daily(dry_run=dry_run)
