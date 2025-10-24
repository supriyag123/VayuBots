# -*- coding: utf-8 -*-
"""
tools/airtable_utils.py

Complete Airtable utilities for Karna
Multi-tenant support with all CRUD operations
"""

from dotenv import load_dotenv
load_dotenv()

import os
import json
from pyairtable import Api
from datetime import datetime
# ============================================================================
# INITIALISE
# ============================================================================

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")

if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
    raise RuntimeError("Set AIRTABLE_API_KEY and AIRTABLE_BASE_ID in your .env file")

api = Api(AIRTABLE_API_KEY)
base = api.base(AIRTABLE_BASE_ID)

# ============================================================================
# SIMPLE CLIENT WRAPPER for backward compatibility
# ============================================================================

class AirtableClientWrapper:
    def list(self, base_id, table_name, filterByFormula=None, max_records=None, sort=None):
        tbl = _tbl(table_name)
        kwargs = {}
        if filterByFormula:
            kwargs["formula"] = filterByFormula
        if max_records:
            kwargs["max_records"] = max_records
        if sort:
            kwargs["sort"] = sort
        return {"records": tbl.all(**kwargs)}

    def create(self, base_id, table_name, fields):
        tbl = _tbl(table_name)
        return tbl.create(fields)

    def update(self, base_id, table_name, record_id, fields):
        tbl = _tbl(table_name)
        return tbl.update(record_id, fields)

    def delete(self, base_id, table_name, record_id):
        tbl = _tbl(table_name)
        return tbl.delete(record_id)

# Instantiate global client
airtable_client = AirtableClientWrapper()


# ============================================================================
# HELPERS
# ============================================================================

def _tbl(table_name: str):
    """Get Airtable table object."""
    return base.table(table_name)


def get_table(table_name: str):
    """Legacy alias for _tbl."""
    return _tbl(table_name)

def get_client_id_from_phone(phone: str):
    table = _tbl("Clients")
    records = table.all(formula=f"{{WhatsApp Phone}} = '{phone}'")
    if records:
        return records[0]["id"]
    return None
# ============================================================================
# CLIENT MANAGEMENT
# ============================================================================

def list_active_clients():
    """Return all active clients."""
    table = _tbl("Clients")
    formula = "{Status}='Active'"
    print(f"[Airtable] Querying Clients: {formula}")
    return table.all(formula=formula)


def get_client(client_id: str):
    """Get a single client by ID."""
    return _tbl("Clients").get(client_id)


def get_client_config(client_id: str):
    """Return client config as dict."""
    client = get_client(client_id)
    fields = client.get("fields", {})

    # Parse JSON auth field if it exists
    auth = fields.get('Auth', {})
    if isinstance(auth, str):
        try:
            auth = json.loads(auth)
        except:
            auth = {}
    
    # If auth is empty, try to build from separate fields
    if not auth:
        auth = {
            'fb_page_id': fields.get('FB Page ID', ''),
            'fb_access_token': fields.get('FB Access Token', ''),
            'ig_business_id': fields.get('IG Business ID', ''),
            'ig_access_token': fields.get('IG Access Token', ''),
            'linkedin_org_id': fields.get('LinkedIn Org ID', ''),
            'linkedin_access_token': fields.get('LinkedIn Access Token', '')
        }
    if isinstance(auth, str):
        try:
            auth = json.loads(auth)
        except Exception:
            auth = {}

    return {
        "id": client["id"],
        "name": fields.get("Name"),
        "status": fields.get("Status"),
        "brand_voice": fields.get("Tone/Style", ""),
        'instructions': fields.get('Instructions', ''),  # ADD THIS
        "preferred_channels": fields.get("Channels", []),
        "approval_mode": fields.get("Approval Mode", "Manager"),
        "approver_emails": fields.get("Owner Email", ""),
        "content_sources": fields.get("Reference URLs", ""),
        "auth": auth,
        "social_handles": {
            "fb_page_id": auth.get("FB Page ID"),
            "ig_business_id": auth.get("IG Business ID"),
            "linkedin_org_id": auth.get("linkedin ID"),
        },
    }


# ============================================================================
# IDEAS MANAGEMENT
# ============================================================================

def create_idea(client_id, headline, summary, source_type="Client Input", image_url=None, source_detail=None, priority="Medium"):
    """
    Create an idea record in Airtable. Supports optional image upload as attachment.
    """
    fields = {
        "Client": [client_id],
        "Headline": headline,
        "Summary": summary,
        "Source Type": source_type,
        "Priority": priority,
    }

    if source_detail:
        fields["Source Detail"] = source_detail

    # ✅ Handle image attachment properly
    if image_url:
        # ✅ Upload image as attachment
        fields["Image"] = [{"url": image_url}]

    table = _tbl("Ideas")
    return table.create(fields)


'''
def get_new_ideas(limit=10, client_id=None):
    """Get unprocessed (New/blank) ideas."""
    table = _tbl("Ideas")
    if client_id:
        formula = (
            "AND("
            "OR({Status}='New',{Status}=BLANK()),"
            f"FIND('{client_id}', ARRAYJOIN({{Client}}))"
            ")"
        )
    else:
        formula = "OR({Status}='New',{Status}=BLANK())"

    print(f"[Airtable] Querying Ideas: {formula} (limit={limit})")
    return table.all(formula=formula, max_records=limit)
'''

def get_new_ideas(limit=10, client_id=None):
    """
    Get ideas that haven't been processed yet.
    
    Args:
        limit: Max number of ideas to return
        client_id: Optional filter by client
    
    Returns:
        List of idea records
    """
    table = _tbl("Ideas")
    
    # Simpler: get all new ideas, then filter in Python if needed
    formula_str = "OR({Status}='New',{Status}='')"
    
    print(f"[DEBUG] Formula: {formula_str}")
    records = table.all(formula=formula_str, max_records=limit)
    print(f"[DEBUG] Found {len(records)} total new ideas")
    
    # Filter by client in Python if needed
    if client_id and records:
        records = [r for r in records if client_id in r['fields'].get('Client', [])]
        print(f"[DEBUG] After client filter: {len(records)} records")
    
    return records

def get_idea(idea_id):
    return _tbl("Ideas").get(idea_id)


def mark_idea_processed(idea_id):
    return _tbl("Ideas").update(idea_id, {"Status": "Processed"})


def mark_idea_error(idea_id, error_msg):
    return _tbl("Ideas").update(idea_id, {"Status": "Error", "Error Message": error_msg})


def update_idea(idea_id, fields):
    return _tbl("Ideas").update(idea_id, fields)


# ============================================================================
# POSTS MANAGEMENT
# ============================================================================

def create_post(client_id, idea_id, channel, caption, hashtags, cta,
                impact_score, source_type, image_url=None, link_url=None, approval_mode="Manager"):
    

    """Create a new post from an idea."""
    
    print(f"\n[DEBUG create_post] Starting post creation...")
    print(f"[DEBUG create_post] Received image_url parameter: {image_url}")
    
    fields = {
        "Client": [client_id],
        "Idea": [idea_id],
        "Channel": channel,
        "Caption": caption,
        "Hashtags": hashtags,
        "CTA": cta,
        "Impact Score": round(impact_score, 4),
        "Source Type": source_type,
        "Publish Status": "Draft"
    }
    
    # Set approval status based on mode
    if approval_mode == "Auto":
        fields["Approval Status"] = "Auto-Approved"
    else:
        fields["Approval Status"] = "Needs Approval"
    
    if image_url:
        print(f"[DEBUG create_post] Image URL exists, preparing attachment format...")
        print(f"[DEBUG create_post] Image URL value: {image_url[:100]}...")
        attachment_data = [{"url": image_url}]
        print(f"[DEBUG create_post] Attachment format: {attachment_data}")
        fields["image_url"] = attachment_data
        print(f"[DEBUG create_post] Added to fields dict")
    else:
        print(f"[DEBUG create_post] No image_url provided (is None or empty)")
        fields["image_url"] = " "
        
    if link_url:
        print(f"[DEBUG create_post] Adding link_url: {link_url}")
        fields["link_url"] = link_url
    
    print(f"\n[DEBUG create_post] Final fields dict keys: {fields.keys()}")
    print(f"[DEBUG create_post] image_url in fields: {'image_url' in fields}")
    
    table = _tbl("Posts")
    
    try:
        print(f"[DEBUG create_post] Calling Airtable API...")
        created_post = table.create(fields)
        print(f"[DEBUG create_post] Post created successfully!")
        print(f"[DEBUG create_post] Returned fields: {created_post['fields'].keys()}")
        print(f"[DEBUG create_post] image_url in response: {'image_url' in created_post['fields']}")
        
        if 'image_url' in created_post['fields']:
            print(f"[DEBUG create_post] Image value: {created_post['fields']['image_url']}")
        else:
            print(f"[DEBUG create_post] WARNING: image_url field NOT in response!")
        
        return created_post
        
    except Exception as e:
        print(f"[ERROR create_post] Airtable API error: {e}")
        import traceback
        traceback.print_exc()
        raise


def get_posts_needing_approval(client_id=None):
    table = _tbl("Posts")
    if client_id:
        formula = (
            "AND({Approval Status}='Needs Approval', "
            f"FIND('{client_id}', ARRAYJOIN({{Client}})))"
        )
    else:
        formula = "{Approval Status}='Needs Approval'"
    return table.all(formula=formula)


def get_draft_posts(client_id=None, limit=10):
    table = _tbl("Posts")
    if client_id:
        formula = (
            "AND({Publish Status}='Draft', "
            f"FIND('{client_id}', ARRAYJOIN({{Client}})))"
        )
    else:
        formula = "{Publish Status}='Draft'"
    return table.all(formula=formula, max_records=limit)


def approve_post(post_id, scheduled_at=None):
    fields = {"Approval Status": "Approved"}
    if scheduled_at:
        fields["Scheduled At"] = scheduled_at
    return _tbl("Posts").update(post_id, fields)


def get_posts_ready_to_publish(now_iso, client_id=None):
    formula = f"""AND(
        OR({{Approval Status}}='Approved', {{Approval Status}}='Auto-Approved'),
        OR({{Publish Status}}='Draft', {{Publish Status}}='Queued'),
        OR({{Scheduled At}}=BLANK(), {{Scheduled At}}<='{now_iso}')
    )"""
    posts = _tbl("Posts").all(formula=formula)

    # 🔒 Enforce client filter
    if client_id:
        posts = [p for p in posts if client_id in p.get("fields", {}).get("Client", [])]

    return posts



def mark_post_published(post_id, platform_post_id, published_at=None):
    """Mark a post as successfully published."""
    print(f"\n[DEBUG] Marking post as published...")
    print(f"  Post ID: {post_id}")
    print(f"  Platform Post ID: {platform_post_id}")
    print(f"  Published At: {published_at}")

    try:
        if not published_at:
            published_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

        table = _tbl("Posts")
        result = table.update(post_id, {
            "Publish Status": "Published",
            "Platform Post ID": platform_post_id,
            "Published At": published_at
        })
        print(f"[DEBUG] ✅ Airtable updated successfully")
        return result
    except Exception as e:
        print(f"[DEBUG] ❌ Airtable update failed: {e}")
        import traceback
        traceback.print_exc()
        raise



def mark_post_error(record_id, error_msg):
    """Mark a post as having a publishing error."""
    print(f"\n[DEBUG] Marking post as error...")
    print(f"  Post ID: {record_id}")
    print(f"  Error: {error_msg}")
    
    try:
        table = _tbl("Posts")
        
        # Just update status, don't try to save error message
        result = table.update(record_id, {
            "Publish Status": "Error"
            # Removed: "Error Message": error_msg  - field doesn't exist
        })
        
        print(f"[DEBUG] ✅ Post marked as Error in Airtable")
        return result
    except Exception as e:
        print(f"[DEBUG] ❌ Failed to mark as error: {e}")
        return None

def update_post(post_id, fields):
    return _tbl("Posts").update(post_id, fields)

# ============================================================================
# EXTRA HELPERS FOR KARNA FLOW
# ============================================================================

def get_posts_for_client(client_id: str, status: str = None, limit: int = 10):
    """
    Fetch posts for a given client.
    - status: filter by Approval Status ("Needs Approval", "Approved", etc.)
    - sorted by Impact Score (descending)
    """
    try:
        tbl = _tbl("Posts")

        # Build formula only for status, skip client filter
        formula = None
        if status:
            formula = f"{{Approval Status}} = '{status}'"

        # Fetch records
        records = tbl.all(formula=formula, max_records=limit*5)  # fetch more, filter later

        # Filter in Python because Client is a linked record (list of IDs)
        filtered = [
            r for r in records
            if client_id in r["fields"].get("Client", [])
        ]

        # Sort by Impact Score
        filtered.sort(key=lambda r: r["fields"].get("Impact Score", 0), reverse=True)

        # Apply limit
        return filtered[:limit]

    except Exception as e:
        print(f"[ERROR] get_posts_for_client failed: {e}")
        return []



def get_summary_for_client(client_id: str, days: int = 7):
    """
    Simple weekly summary: posts created, scheduled, ideas used.
    """
    try:
        from datetime import datetime, timedelta
        tbl = _tbl("Posts")
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        formula = f"AND(FIND('{client_id}', ARRAYJOIN({{Client}})), IS_AFTER({{Created}}, '{cutoff}'))"
        posts = tbl.all(formula=formula)

        total_posts = len(posts)
        scheduled = len([p for p in posts if p["fields"].get("Approval Status") == "Approved"])
        ideas_curated = len([p for p in posts if p["fields"].get("Source Type") == "Idea"])

        return {
            "posts_this_week": total_posts,
            "scheduled_posts": scheduled,
            "ideas_curated": ideas_curated,
            "engagement_summary": "See Analytics for detailed engagement"
        }
    except Exception as e:
        print(f"[ERROR] get_summary_for_client failed: {e}")
        return {
            "posts_this_week": 0,
            "scheduled_posts": 0,
            "ideas_curated": 0,
            "engagement_summary": "N/A"
        }


def get_analytics_for_client(client_id: str, limit: int = 1):
    """
    Fetch latest analytics snapshot for a client.
    Expects a table 'Analytics' in Airtable with metrics per client.
    """
    try:
        tbl = _tbl("Analytics")
        formula = f"FIND('{client_id}', ARRAYJOIN({{Client}}))"
        records = tbl.all(formula=formula, max_records=limit, sort=["-Date"])
        if not records:
            return {"reach": 0, "impressions": 0, "clicks": 0, "ctr": "0%"}

        f = records[0]["fields"]
        return {
            "reach": f.get("Reach", 0),
            "impressions": f.get("Impressions", 0),
            "clicks": f.get("Clicks", 0),
            "ctr": f.get("CTR", "0%")
        }
    except Exception as e:
        print(f"[ERROR] get_analytics_for_client failed: {e}")
        return {"reach": 0, "impressions": 0, "clicks": 0, "ctr": "0%"}

# ============================================================================
# HISTORY MANAGEMENT
# ============================================================================

def create_history_record(client_id, platform, page_handle, post_text,
                          post_url, publish_date, likes=0, shares=0, comments=0,
                          embedding=None):
    fields = {
        "Platform": platform,
        "Page / Handle": page_handle,
        "Post Text": post_text,
        "Post URL": post_url,
        "Publish Date": publish_date,
        "Likes": likes,
        "Shares": shares,
        "Comments": comments,
    }
    if client_id:
        fields["Client"] = [client_id]
    if embedding:
        fields["Embedding"] = json.dumps(embedding)
    return _tbl("History").create(fields)


def get_history_for_client(client_id, limit=100):
    """Get historical posts for a client."""
    table = _tbl("History")
    
    # Simpler formula - get all, then filter in Python
    records = table.all(max_records=limit, sort=["-Publish Date"])
    
    # Filter by client in Python if needed
    if client_id and records:
        records = [r for r in records if client_id in r['fields'].get('Client', [])]
    
    print(f"[DEBUG] Found {len(records)} history records for client {client_id}")
    return records


def get_all_history(limit=100):
    return _tbl("History").all(
        max_records=limit,
        sort=["-Publish Date"]
    )


def get_history_without_embeddings(limit=50):
    formula = "{Embedding}=BLANK()"
    return _tbl("History").all(formula=formula, max_records=limit)


def update_history_embedding(record_id, embedding):
    return _tbl("History").update(record_id, {"Embedding": json.dumps(embedding)})


def update_history_metrics(record_id, likes, shares, comments):
    return _tbl("History").update(record_id, {"Likes": likes, "Shares": shares, "Comments": comments})


# ============================================================================
# BATCH OPS
# ============================================================================

def batch_create(table_name, records, typecast=True):
    return _tbl(table_name).batch_create(records, typecast=typecast)


def batch_update(table_name, updates, typecast=True):
    return _tbl(table_name).batch_update(updates, typecast=typecast)


# ============================================================================
# CONSTANTS
# ============================================================================

CLIENTS_TABLE = "Clients"
IDEAS_TABLE = "Ideas"
POSTS_TABLE = "Posts"
HISTORY_TABLE = "History"

# ======================================================
# JOB MANAGEMENT HELPERS
# ======================================================

def create_job_record(job_type: str, client_id: str = None, metadata: dict = None):
    tbl = _tbl("Jobs")
    fields = {
        "Job Type": job_type,   # ✅ should be plain text
        "Status": "Queued"
    }
    if client_id:
        fields["Client"] = [client_id]   # ✅ must be list of linked record IDs
    if metadata:
        fields["Parameters"] = str(metadata)  # Optional JSON field if you want

    record = tbl.create(fields)
    print(f"[JOBS] Created job {record['id']} for {job_type}")
    return record["id"]



def update_job_status(job_id, status, error=None, result_summary=None):
    """Update job record with new status, error, or result."""
    import json
    from datetime import datetime

    tbl = _tbl("Jobs")
    fields = {"Status": status}
    if status in ["Completed", "Failed"]:
        fields["Completed At"] = datetime.utcnow().isoformat()
    if error:
        fields["Error Message"] = str(error)

    if result_summary:
        try:
            # ✅ Convert non-serializable types to strings
            def safe_json(o):
                try:
                    json.dumps(o)
                    return o
                except Exception:
                    return str(o)

            if isinstance(result_summary, (dict, list)):
                result_summary = json.dumps(result_summary, default=safe_json, indent=2)
            else:
                result_summary = str(result_summary)

            fields["Result Summary"] = result_summary
        except Exception as e:
            print(f"[JOBS] ⚠️ Could not serialize result_summary: {e}")
            fields["Result Summary"] = str(result_summary)

    try:
        tbl.update(job_id, fields)
        print(f"[JOBS] Updated {job_id} → {status}")
    except Exception as e:
        print(f"[JOBS] Failed to update {job_id}: {e}")

