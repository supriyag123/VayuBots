# -*- coding: utf-8 -*-
"""
tools/social_publishers.py

Social media publishing utilities for Facebook, Instagram, LinkedIn
"""

from dotenv import load_dotenv
load_dotenv()

import requests
import json

import re



def format_for_platform(text: str, platform: str) -> str:
    """
    Format caption for platform: strip ONLY section labels, keep ALL emojis.
    """
    
    # Only remove section labels IF they exist, but keep the emoji
    text = re.sub(r"Hook:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Story:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Urgency:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"CTA:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Hashtags:\s*", "", text, flags=re.IGNORECASE)
    
    # Remove markdown bold/italic
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # **bold** → text
    text = re.sub(r'\*(.+?)\*', r'\1', text)      # *italic* → text
    
    # That's it! Don't touch emojis at all
    return text.strip()

def clean_text(text: str) -> str:
    """Clean text but keep emojis and valid UTF-8 characters."""
    if not text:
        return ""
    result = []
    for char in text:
        try:
            char.encode("utf-8")
            result.append(char)
        except UnicodeEncodeError:
            # Skip broken surrogates
            continue
    return "".join(result)


def normalize_text(text: str) -> str:
    """Convert surrogate pairs to real emojis + clean invalid chars."""
    if not text:
        return ""
    # Fix surrogate pairs by encoding/decoding
    text = text.encode("utf-16", "surrogatepass").decode("utf-16", "surrogatepass")
    
    # Now run through your clean_text filter to drop any leftovers
    return clean_text(text)


# ===============================================================
# Facebook Publisher
# ===============================================================

def get_page_token(user_token: str, page_id: str) -> str:
    """Exchange a long-lived user token for a page access token."""
    url = "https://graph.facebook.com/v18.0/me/accounts"
    resp = requests.get(url, params={"access_token": user_token})
    data = resp.json()
    print(f"[DEBUG FB] /me/accounts response: {data}")
    for page in data.get("data", []):
        if page["id"] == page_id:
            return page["access_token"]
    raise Exception("Page token not found for this page. Make sure user token has pages_manage_posts.")


def publish_to_facebook(page_id: str, access_token: str, message: str,
                        link: str = None, image_url: str = None) -> dict:
    """Publish a post to Facebook Page."""
    try:
        print(f"\n[DEBUG FB] Publishing to Facebook...")
        print(f"  Page ID: {page_id}")
        print(f"  Message: {message[:60]}...")
        print(f"  Link: {link}")
        print(f"  Image URL: {image_url if image_url else 'None'}")

        if not page_id or not access_token:
            return {"success": False, "error": "Missing Facebook credentials"}

        # Always exchange the user token for a Page token
        try:
            page_token = get_page_token(access_token, page_id)
        except Exception as e:
            return {"success": False, "error": f"Failed to get page token: {str(e)}"}

        # Decide endpoint based on presence of image
        if image_url:
            url = f"https://graph.facebook.com/v18.0/{page_id}/photos"
            params = {"url": image_url, "caption": message, "access_token": page_token}
            if link:
                params["link"] = link
            print("[DEBUG FB] Using photos endpoint")
        else:
            url = f"https://graph.facebook.com/v18.0/{page_id}/feed"
            params = {"message": message, "access_token": page_token}
            if link:
                params["link"] = link
            print("[DEBUG FB] Using feed endpoint")

        response = requests.post(url, data=params)
        
        print(f"[DEBUG FB] Raw status: {response.status_code}")
        print(f"[DEBUG FB] Raw text: {response.text}")

        try:
            response.raise_for_status()
        except Exception:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}

        result = response.json()
        print(f"[DEBUG FB] Parsed JSON: {result}")  

        if "id" in result:
            print(f"[DEBUG FB] ✅ Success! Post ID: {result['id']}")
            return {"success": True, "post_id": result["id"], "platform": "Facebook"}
        else:
            error_msg = result.get("error", {}).get("message", "Unknown error")
            return {"success": False, "error": error_msg, "full_response": result}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}



# ===============================================================
# Instagram Publisher
# ===============================================================

def publish_to_instagram(ig_user_id: str, access_token: str, caption: str,
                         image_url: str, link: str = None) -> dict:
    """
    Publish a post to Instagram Business Account.
    Instagram requires an image.
    """
    try:
        print(f"\n[DEBUG IG] Publishing to Instagram...")
        print(f"  User ID: {ig_user_id}")
        print(f"  Caption: {caption[:60]}...")
        print(f"  Image URL: {image_url if image_url else 'None'}")

        if not ig_user_id or not access_token:
            return {"success": False, "error": "Missing Instagram credentials"}
        if not image_url:
            return {"success": False, "error": "Instagram posts require an image"}

        # Step 1: Create media container
        create_url = f"https://graph.facebook.com/v18.0/{ig_user_id}/media"
        create_params = {"image_url": image_url, "caption": caption, "access_token": access_token}
        create_response = requests.post(create_url, data=create_params)
        print(f"[DEBUG IG] Media create response: {create_response.text}")

        try:
            create_response.raise_for_status()
        except Exception:
            return {"success": False, "error": f"Failed to create media: {create_response.text}"}

        create_result = create_response.json()
        container_id = create_result.get("id")
        if not container_id:
            return {"success": False, "error": create_result.get("error", {}).get("message", "No container created")}

        # Step 2: Publish container
        publish_url = f"https://graph.facebook.com/v18.0/{ig_user_id}/media_publish"
        publish_params = {"creation_id": container_id, "access_token": access_token}
        publish_response = requests.post(publish_url, data=publish_params)
        print(f"[DEBUG IG] Media publish response: {publish_response.text}")

        try:
            publish_response.raise_for_status()
        except Exception:
            return {"success": False, "error": f"Failed to publish media: {publish_response.text}"}

        publish_result = publish_response.json()
        if "id" in publish_result:
            return {"success": True, "post_id": publish_result["id"], "platform": "Instagram"}
        else:
            return {"success": False, "error": publish_result.get("error", {}).get("message", "Failed to publish")}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


# ===============================================================
# LinkedIn Publisher
# ===============================================================

def publish_to_linkedin(person_urn: str, access_token: str, text: str,
                        link: str = None, image_url: str = None) -> dict:
    """
    Publish a post to LinkedIn.
    Currently supports text + optional link. 
    Image upload requires asset registration (not included here).
    """
    try:
        print(f"\n[DEBUG LI] Publishing to LinkedIn...")
        print(f"  Author URN: {person_urn}")
        print(f"  Text: {text[:60]}...")
        print(f"  Link: {link}")

        if not person_urn or not access_token:
            return {"success": False, "error": "Missing LinkedIn credentials"}

        url = "https://api.linkedin.com/v2/ugcPosts"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        post_data = {
            "author": person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }

        if link:
            post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "ARTICLE"
            post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [{
                "status": "READY",
                "originalUrl": link
            }]

        response = requests.post(url, headers=headers, json=post_data)
        print(f"[DEBUG LI] Raw status: {response.status_code}")
        print(f"[DEBUG LI] Raw text: {response.text}")

        try:
            response.raise_for_status()
        except Exception:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}

        result = response.json()
        if response.status_code == 201 and "id" in result:
            return {"success": True, "post_id": result.get("id"), "platform": "LinkedIn"}
        else:
            return {"success": False, "error": result.get("message", "Unknown error"), "full_response": result}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}
