# -*- coding: utf-8 -*-
"""
flows/karna_flow.py

Wrapper functions around KarnaMarketingCrew to provide a consistent API
for CLI, web, or messaging (WhatsApp/Slack/etc).
"""


from vayu.karna.karna import KarnaMarketingCrew
from vayu.karna.tools.airtable_utils import (
    create_idea,
    get_posts_for_client,
    update_post,
    get_summary_for_client,
    get_analytics_for_client,
)
from datetime import datetime


# ================================================================
# Core Wrappers
# ================================================================

def curate_only(client_id: str, num_ideas: int = 20, verbose: bool = True):
    """Run idea curation only for a single client."""
    crew = KarnaMarketingCrew(verbose=verbose)
    return crew.run_idea_curation(client_id, num_ideas=num_ideas)


def create_posts_only(client_id: str, idea_ids=None, num_posts: int = 3, verbose: bool = True):
    """Run post creation for client (either for given idea_ids or top ideas)."""
    crew = KarnaMarketingCrew(verbose=verbose)
    return crew.run_post_creation(client_id, idea_ids=idea_ids, num_ideas=num_posts)


def publish_only(client_id: str, verbose: bool = True):
    """Run publishing of approved posts for a client."""
    crew = KarnaMarketingCrew(verbose=verbose)
    return crew.run_publishing(client_id)


def full_workflow(client_id: str, num_ideas: int = 20, num_posts: int = 3, verbose: bool = True):
    """Run full workflow (curate → create posts → publish) for a client."""
    crew = KarnaMarketingCrew(verbose=verbose)
    return crew.run_full_workflow(client_id, num_ideas=num_ideas, num_posts=num_posts)


# ================================================================
# Special wrapper for client-provided raw input (WhatsApp, Web form, etc.)
# ================================================================

def submit_client_input(
    client_id: str,
    idea_text: str,
    image_url: str = None,
    channel: str = "Facebook",
    source_detail: str = None,
    verbose: bool = True
):
    crew = KarnaMarketingCrew(verbose=verbose)

    # Step 1: Save idea (with attachment if provided)
    idea = create_idea(
        client_id=client_id,
        headline=idea_text[:50],
        summary=idea_text,
        source_type="Client Input",
        image_url=image_url,
        source_detail=source_detail,
        priority="High"
    )
    idea_id = idea["id"]

    # Step 2: Run post creation on this idea
    post_result = crew.run_post_creation(client_id, idea_ids=[idea_id], num_ideas=1)

    # ✅ Handle CrewOutput safely
    try:
        if hasattr(post_result, "output"):
            posts_data = post_result.output  # CrewAI v0.3+
        elif isinstance(post_result, dict):
            posts_data = post_result
        else:
            posts_data = str(post_result)
    except Exception as e:
        print(f"[WARN] Unexpected post_result format: {e}")
        posts_data = {}

    return {
        "idea_id": idea_id,
        "idea_text": idea_text,
        "image_url": image_url,
        "posts": posts_data
    }


# ================================================================
# Multi-client batch flows (optional)
# ================================================================

def curate_all_clients(max_clients: int = None, verbose: bool = True):
    return KarnaMarketingCrew(verbose=verbose).run_curation_for_all_clients(max_clients)


def create_posts_all_clients(num_posts: int = 3, max_clients: int = None, verbose: bool = True):
    return KarnaMarketingCrew(verbose=verbose).run_post_creation_for_all_clients(num_posts, max_clients)


def full_workflow_all_clients(max_clients: int = None, num_ideas: int = 20, num_posts: int = 3, verbose: bool = True):
    return KarnaMarketingCrew(verbose=verbose).run_full_workflow_for_all_clients(max_clients, num_ideas, num_posts)


# ================================================================
# Post listing / editing / reporting wrappers for WhatsApp router
# ================================================================

def list_top_posts(client_id: str, limit: int = 3):
    """
    Return top pending posts for a client (sorted by Impact Score desc).
    Each item is the raw Airtable record dict.
    """
    return get_posts_for_client(client_id, status="Needs Approval", limit=limit)

def list_all_pending_posts(client_id: str, limit: int = 50):
    """Return all pending posts (Needs Approval) for a client."""
    return get_posts_for_client(client_id, status="Needs Approval", limit=limit)

def update_post_caption(post_id: str, new_caption: str):
    """Update only the caption/content of a post."""
    return update_post(post_id, {"Caption": new_caption})

def update_post_image_url(post_id: str, image_url: str):
    """
    Update the post image. Accepts either a direct string URL or Airtable attachment format.
    We’ll send as attachment array, consistent with your create_post logic.
    """
    attachment = [{"url": image_url}] if image_url else []
    return update_post(post_id, {"image_url": attachment})

def get_report(client_id: str):
    """Weekly posting summary for a client."""
    return get_summary_for_client(client_id)

def get_analytics(client_id: str):
    """Recent analytics snapshot for a client."""
    return get_analytics_for_client(client_id)

def approve_and_publish_post(client_id: str, post_id: str, schedule_time: datetime | None = None):
    """
    Approve ONE post (now or at a scheduled time) and trigger the publisher flow
    only for that client. Returns the publisher report.
    """
    when_iso = None
    if schedule_time:
        # naive -> ISO; your publisher checks <= now_iso
        when_iso = schedule_time.replace(microsecond=0).isoformat() + "Z"

    # Mark approved (and optionally scheduled)
    fields = {"Approval Status": "Approved"}
    if when_iso:
        fields["Scheduled At"] = when_iso
    update_post(post_id, fields)

    # Run publisher for that client
    crew = KarnaMarketingCrew(verbose=False)
    return crew.run_publishing(client_id)

def get_post_by_id(post_id: str):
    """Fetch a single post record from Airtable by ID."""
    from vayu.karna.tools.airtable_utils import _tbl
    table = _tbl("Posts")
    return table.get(post_id)
