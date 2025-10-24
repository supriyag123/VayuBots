# -*- coding: utf-8 -*-
"""
agents/marketing/agents/publisher_agent.py

Publishing Agent - Publishes approved posts to social media platforms
"""

from dotenv import load_dotenv
load_dotenv()

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from crewai import Agent
from crewai.tools import tool
from langchain_openai import ChatOpenAI
import json
from datetime import datetime

from vayu.karna.tools.airtable_utils import (
    get_posts_ready_to_publish,
    mark_post_published,
    mark_post_error,
    get_client_config,
    _tbl
)

from vayu.karna.tools.social_publishers import (
    publish_to_facebook,
    publish_to_instagram,
    publish_to_linkedin
)


# ============================================================================
# TOOLS FOR PUBLISHER AGENT
# ============================================================================
@tool("Get Posts Ready to Publish")
def get_ready_posts(client_id: str = None) -> str:
    """Get all approved posts ready to be published (optionally filtered by client)."""
    try:
        now_iso = datetime.utcnow().isoformat() + 'Z'
        posts = get_posts_ready_to_publish(now_iso, client_id=client_id)

        if not posts:
            return json.dumps({
                "message": "No posts ready to publish",
                "count": 0
            })

        posts_data = []
        for post in posts:
            fields = post['fields']

            # Extract image URL from attachment
            image_field = fields.get('image_url')
            image_url = ""

            if image_field:
                if isinstance(image_field, list) and len(image_field) > 0:
                    first_attachment = image_field[0]
                    if isinstance(first_attachment, dict) and 'url' in first_attachment:
                        image_url = first_attachment['url']
                        print(f"[DEBUG] Extracted image URL: {image_url[:80]}...")
                elif isinstance(image_field, str):
                    image_url = image_field

            if not image_url:
                print(f"[WARNING] Post {post['id']} has no image URL!")

            posts_data.append({
                'record_id': post['id'],
                'channel': fields.get('Channel'),
                'caption': fields.get('Caption', ''),
                'hashtags': fields.get('Hashtags', ''),
                'link_url': fields.get('link_url', ''),
                'image_url': image_url,
                'client_id': fields.get('Client', [None])[0] if fields.get('Client') else None
            })

        return json.dumps({
            'count': len(posts_data),
            'posts': posts_data
        }, indent=2)

    except Exception as e:
        import traceback
        return json.dumps({
            "error": str(e),
            "traceback": traceback.format_exc()
        })


# ========================================================================
# Helper: Fix surrogate emoji encoding
# ========================================================================
def safe_text(text: str) -> str:
    """
    Clean up text so surrogate pairs (e.g. \\ud83c\\udf9f) become valid UTF-8.
    Keeps emojis intact instead of stripping them.
    """
    if not text:
        return ""
    try:
        return text.encode("utf-16", "surrogatepass").decode("utf-16", "ignore")
    except Exception:
        return str(text)


# ========================================================================
# Tool: Publish Post to Platform
# ========================================================================
@tool("Publish Post to Platform")
def publish_post(record_id: str,  channel: str, caption: str,
                hashtags: str, link_url: str, image_url: str, client_id: str) -> str:
    """
    Publish a post to the specified social media platform.
    
    Args:
        record_id: Post record ID (Airtable)
        client_id: Client record ID (Airtable)
        channel: Facebook/Instagram/LinkedIn
        caption: Post text
        hashtags: Hashtags
        link_url: Link URL
        image_url: Image URL
    
    Returns:
        JSON result with platform post ID or error
    """
    try:
        print(f"\n{'='*60}")
        print(f"[DEBUG PUBLISH_POST] Tool called with:")
        print(f"{'='*60}")
        print(f"post_id: {record_id}")
        print(f"channel: {channel}")
        print(f"caption type: {type(caption)}")
        print(f"caption repr: {repr(caption[:100])}")  # Shows surrogates if present
        print(f"hashtags: {repr(hashtags)}")
        
        # Try to detect surrogates
        try:
            caption.encode('utf-8')
            print("✓ Caption has valid UTF-8")
        except UnicodeEncodeError as e:
            print(f"✗ Caption has encoding issue: {e}")
            
        
        # --- 1. Get client auth tokens ---
        config = get_client_config(client_id)
        auth = config.get('auth', {})

        # --- 2. Combine caption + hashtags ---
        # --- 2. Clean and format ---
        from vayu.karna.tools.social_publishers import clean_text, format_for_platform, normalize_text

        caption = normalize_text(caption)
        hashtags = normalize_text(hashtags) if hashtags else ""
        #link_url = normalize_text(link_url) if link_url else None
        
        # Check if hashtags are already in the caption
        if hashtags and hashtags not in caption:
            full_text = f"{caption}\n\n{hashtags}"
        else:
            # Hashtags already in caption, don't duplicate
            full_text = caption
        
        print(f"\nAfter cleaning:")
        print(f"caption: {caption[:100]}...")
        print(f"hashtags: {hashtags}")
        print(f"full_text: {full_text[:150]}...")
        
        # ✅ Convert markdown (bold/italics) into platform-safe text

        full_text = format_for_platform(full_text, channel)

        print(f"After formatting: {repr(full_text[:100])}")
        print(f"{'='*60}\n")
        
        # Extract final image_url (string only)
        actual_image_url = None
        if image_url:
            if isinstance(image_url, list) and len(image_url) > 0:
                if isinstance(image_url[0], dict) and 'url' in image_url[0]:
                    actual_image_url = image_url[0]['url']
                else:
                    actual_image_url = str(image_url[0])
            elif isinstance(image_url, str):
                actual_image_url = image_url

        # --- BAD IMAGE DETECTION ---
        def looks_like_bad_image(url: str) -> bool:
            if not url:
                return True
            url_lower = url.lower()
            bad_keywords = ["favicon", "logo", "placeholder", "default"]
            return any(bad in url_lower for bad in bad_keywords)
        
        # Check image validity
        if not actual_image_url or looks_like_bad_image(actual_image_url):
            print("[DEBUG publish_post] Bad or missing image detected, generating AI image...")
            from tools.ai_image_generator import create_post_image
            actual_image_url = create_post_image(caption)
            print(f"[DEBUG publish_post] AI-generated image: {actual_image_url}")   


        # Publish
        result = None
        if channel == "Facebook":
            fb_page_id = auth.get('fb_page_id')
            fb_token = auth.get('fb_access_token')
            if not fb_page_id or not fb_token:
                return json.dumps({"success": False, "error": "Facebook credentials not configured"})
            result = publish_to_facebook(
                page_id=auth.get('fb_page_id'),
                access_token=auth.get('fb_access_token'),
                message=full_text,
                link=link_url,
                image_url=actual_image_url
            )
            print(f"[DEBUG publish_post] FB publish result: {result}")

        elif channel == "Instagram":
            ig_user_id = auth.get('ig_business_id')
            ig_token = auth.get('ig_access_token')
            if not ig_user_id or not ig_token:
                return json.dumps({"success": False, "error": "Instagram credentials not configured"})
            result = publish_to_instagram(
                ig_user_id=auth.get('ig_business_id'),
                access_token=auth.get('ig_access_token'),
                caption=full_text,
                image_url=actual_image_url,
                link=link_url
            )

        elif channel == "LinkedIn":
            linkedin_urn = auth.get('linkedin_org_id')
            linkedin_token = auth.get('linkedin_access_token')
            if not linkedin_urn or not linkedin_token:
                return json.dumps({"success": False, "error": "LinkedIn credentials not configured"})
            result = publish_to_linkedin(
                person_urn=auth.get('linkedin_org_id'),
                access_token=auth.get('linkedin_access_token'),
                text=full_text,
                link=link_url,
                image_url=actual_image_url
            )

        else:
            return json.dumps({
                "success": False,
                "record_id": record_id,
                "error": f"Unsupported channel: {channel}"
            })

        # Handle response
        if result.get("success") and result.get("post_id"):
            published_at = datetime.utcnow().isoformat() + 'Z'
            mark_post_published(record_id, result["post_id"], published_at)
            return json.dumps({
                "success": True,
                "record_id": record_id,                 # Airtable record ID
                "platform_post_id": result["post_id"], # Real platform ID
                "channel": channel
            })
        else:
            mark_post_error(record_id, result.get("error", "Unknown error"))
            return json.dumps({
                "success": False,
                "record_id": record_id,
                "error": result.get("error", "Unknown error"),
                "full_response": result
            })

    except Exception as e:
        import traceback
        mark_post_error(record_id, str(e))
        return json.dumps({
            "success": False,
            "record_id": record_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })


# ============================================================================
# AGENT DEFINITION
# ============================================================================

def create_publisher_agent():
    """
    Create the Publishing Agent.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)

    agent = Agent(
        role="Social Media Publisher",
        goal="Publish approved social media posts to the correct platforms at the scheduled time",
        backstory="""You're the publishing coordinator who ensures posts go live on schedule.

Your responsibilities:
- Check for approved posts ready to publish
- Route each post to the correct platform (Facebook/Instagram/LinkedIn)
- Handle platform-specific requirements
- Update status after publishing
- Log any errors for review

You understand that:
- Only publish posts with Approval Status = "Approved" or "Auto-Approved"
- Check scheduled time before publishing. If it is blank you can publish now. If it has value you should honour that.
- Each platform has different APIs and requirements
- Always update Airtable after publishing""",
        tools=[
            get_ready_posts,
            publish_post
        ],
        llm=llm,
        verbose=True,
        allow_delegation=False
    )

    return agent
