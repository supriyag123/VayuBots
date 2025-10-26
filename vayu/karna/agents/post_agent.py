# -*- coding: utf-8 -*-
"""
agents/marketing/agents/post_agent.py

Post Creation Agent - Creates engaging social media posts from curated ideas
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

from vayu.karna.tools.airtable_utils import (
    get_idea,
    get_client_config,
    create_post,
    mark_idea_processed,
    _tbl,
    get_posts_for_client,
    update_post,
    get_summary_for_client,
    get_analytics_for_client
)



# ============================================================================
# TOOLS FOR POST AGENT
# ============================================================================

@tool("Get Idea Details")
def get_idea_details(idea_id: str) -> str:
    """
    Get full details of an idea to create posts from.
    
    Args:
        idea_id: Idea's Airtable record ID
    
    Returns:
        JSON with idea details
    """
    try:
        idea = get_idea(idea_id)
        fields = idea['fields']
        
        return json.dumps({
            'id': idea['id'],
            'headline': fields.get('Headline', ''),
            'summary': fields.get('Summary', ''),
            'source_type': fields.get('Source Type', ''),
            'source_detail': fields.get('Source Details', ''),  # CHANGED to Source Details (plural)
            'priority': fields.get('Priority', ''),
            'quality_score': fields.get('Quality Score', 0),
            'has_image': fields.get('Image Provided?', False),
            'image_url': fields.get('Image URL', ''),
            'curation_notes': fields.get('Curation Notes', '')
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})

@tool("Get Brand Guidelines")
def get_brand_guidelines(client_id: str) -> str:
    """
    Get client's brand voice and preferred channels.
    
    Args:
        client_id: Client's Airtable record ID
    
    Returns:
        JSON with brand info
    """
    try:
        config = get_client_config(client_id)
        
        return json.dumps({
            'name': config['name'],
            'brand_voice': config['brand_voice'],
            'preferred_channels': config['preferred_channels'],
            'approval_mode': config['approval_mode'],
            'instructions' : config['instructions']
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool("Evaluate Post Variant")
def evaluate_post_variant(caption: str, hashtags: str, cta: str, brand_voice: str, instructions: str = "") -> str:
    """
    Evaluate a post variant for writing quality.
    
    Args:
        caption: The post caption text
        hashtags: Space-separated hashtags
        cta: Call to action
        brand_voice: Brand voice to evaluate against
        instructions: Additional client instructions
    
    Returns:
        JSON with quality score and evaluation breakdown
    """
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
        
        instructions_section = f"\nCLIENT INSTRUCTIONS: {instructions}" if instructions else ""
        
        prompt = f"""Evaluate this social media post for a company, referring to brand voice and instructions:

CAPTION: {caption}
HASHTAGS: {hashtags}
CTA: {cta}
BRAND VOICE: {brand_voice}{instructions_section}

Score the post on these criteria (0-10 each):
1. Hook Strength: Does it grab attention in first 5 words?
2. Emotional Appeal: Does it create excitement and connection?
3. Clarity: Is the message clear and concise?
4. CTA Effectiveness: Does it drive action?
5. Brand Alignment: Does it match the brand voice and follow any instructions?

Calculate total_score as average of all 5 scores.

Return ONLY valid JSON in this exact format:
{{
  "hook_score": 8,
  "emotion_score": 7,
  "clarity_score": 9,
  "cta_score": 6,
  "brand_score": 8,
  "total_score": 7.6,
  "strengths": "Brief description of what works well",
  "weaknesses": "Brief description of what could improve"
}}"""
        
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        # Clean markdown if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        # Validate it's JSON
        parsed = json.loads(content)
        
        return json.dumps(parsed, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool("Compare Post to History")
def compare_post_to_history(client_id: str, caption: str) -> str:
    """
    Compare a post caption to historical high-performing posts using embeddings.
    
    Args:
        client_id: Client's Airtable record ID
        caption: Post caption to evaluate
    
    Returns:
        JSON with similarity score to top performing posts
    """
    try:
        from langchain_openai import OpenAIEmbeddings
        import numpy as np
        from vayu.karna.tools.airtable_utils import get_history_for_client
        
        # Get history
        history = get_history_for_client(client_id, limit=50)
        
        if not history:
            return json.dumps({
                "message": "No history to compare against", 
                "similarity_score": 0.5,
                "interpretation": "Unknown - no historical data"
            })
        
        # Generate embedding for caption
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        caption_emb = embeddings.embed_query(caption)
        
        # Get posts with embeddings and engagement
        comparable_posts = []
        
        for record in history:
            fields = record['fields']
            likes = fields.get('Likes', 0)
            shares = fields.get('Shares', 0)
            comments = fields.get('Comments', 0)
            engagement = likes + (shares * 3) + (comments * 2)
            embedding_str = fields.get('Embedding', '')
            
            if not embedding_str or engagement == 0:
                continue
            
            try:
                # Parse embedding
                if isinstance(embedding_str, str) and ',' in embedding_str:
                    hist_emb = [float(x.strip()) for x in embedding_str.split(',')]
                else:
                    continue
                
                # Calculate cosine similarity
                dot_product = np.dot(caption_emb, hist_emb)
                norm_caption = np.linalg.norm(caption_emb)
                norm_hist = np.linalg.norm(hist_emb)
                similarity = dot_product / (norm_caption * norm_hist)
                
                comparable_posts.append({
                    'similarity': float(similarity),
                    'engagement': engagement,
                    'text': fields.get('Post Text', '')[:60] + '...'
                })
            except Exception as e:
                continue
        
        if not comparable_posts:
            return json.dumps({
                "message": "No embeddings found in history", 
                "similarity_score": 0.5,
                "interpretation": "Unknown - no embedding data"
            })
        
        # Sort by engagement to get top performers
        comparable_posts.sort(key=lambda x: x['engagement'], reverse=True)
        
        # Take top 5 performers
        top_performers = comparable_posts[:min(5, len(comparable_posts))]
        
        # Calculate average similarity to top performers
        avg_similarity = sum(p['similarity'] for p in top_performers) / len(top_performers)
        
        # Interpretation
        if avg_similarity > 0.75:
            interpretation = "High - Very similar to top posts"
        elif avg_similarity > 0.65:
            interpretation = "Medium-High - Good alignment with successful content"
        elif avg_similarity > 0.55:
            interpretation = "Medium - Moderately similar to top posts"
        else:
            interpretation = "Low - Different from typical successful content"
        
        return json.dumps({
            'similarity_score': round(avg_similarity, 3),
            'interpretation': interpretation,
            'most_similar_top_post': {
                'text': top_performers[0]['text'],
                'engagement': top_performers[0]['engagement'],
                'similarity': round(top_performers[0]['similarity'], 3)
            } if top_performers else None,
            'comparison_count': len(top_performers),
            'note': f'Compared to top {len(top_performers)} performing posts'
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})
    

@tool("Create Social Post")
def create_social_post(
    client_id: str, 
    idea_id: str, 
    channel: str, 
    caption: str, 
    hashtags: str, 
    cta: str,
    image_url: str,           # This now matters (from get_post_image)
    quality_score: float, 
    similarity_score: float
    ) -> str:
    """
    Save a post to Airtable with evaluation scores.

    Args:
        client_id: Client's Airtable record ID
        idea_id: Source idea's record ID
        channel: Facebook/Instagram/LinkedIn
        caption: Post text
        hashtags: Space-separated hashtags
        cta: Call to action
        image_url: Image URL for the post (from Get Post Image if possible)
        quality_score: Writing quality score (0-10)
        similarity_score: Historical similarity score (0-1)

    Returns:
        Success message with post ID
    """  
    try:
        idea = get_idea(idea_id)
        idea_fields = idea['fields']

        source_type = idea_fields.get('Source Type', 'Other')
        link_url = idea_fields.get('Source Details', '')  # note plural "Details"

        # Fallback to Airtable image only if none provided
        if not image_url:
            image_url = idea_fields.get('Image URL', '')

        # Get client config for approval mode and fallback link
        config = get_client_config(client_id)
        approval_mode = config['approval_mode']

        if not link_url:
            link_url = config.get('website_url', '')

        # Combined impact score
        impact_score = (quality_score / 10 * 0.6) + (similarity_score * 0.4)

        # Actually create the post in Airtable
        post = create_post(
            client_id=client_id,
            idea_id=idea_id,
            channel=channel,
            caption=caption,
            hashtags=hashtags,
            cta=cta,
            impact_score=impact_score,
            source_type=source_type,
            image_url=image_url,      # ← now respected
            link_url=link_url,
            approval_mode=approval_mode
        )

        print(f"[DEBUG] Post created successfully, checking returned fields...")

        # Extract returned image attachment
        image_attachments = post['fields'].get('image_url', [])
        returned_image = None
        if isinstance(image_attachments, list) and len(image_attachments) > 0:
            returned_image = image_attachments[0].get('url')
        elif isinstance(image_attachments, str):
            returned_image = image_attachments

        # Mark idea as processed
        mark_idea_processed(idea_id)

        return json.dumps({
            'success': True,
            'post_id': post['id'],
            'channel': channel,
            'link_url': link_url,
            'image_url': returned_image,
            'impact_score': round(impact_score, 3),
            'quality_score': quality_score,
            'similarity_score': similarity_score,
            'approval_status': post['fields'].get('Approval Status'),
            'caption_preview': caption[:50] + '...'
        })

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[ERROR] Failed to create post: {str(e)}")
        print(error_details)
        return json.dumps({
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": error_details
        })


@tool("Get Post Image")
def get_post_image(idea_summary: str, headline: str, brand_voice: str, source_url: str = "") -> str:
    """
    Get an appropriate image for a social media post.
    Tries multiple methods: web scraping, stock images, or AI generation.
    
    Args:
        idea_summary: The content summary
        headline: Post headline
        brand_voice: Client's brand description/industry
        source_url: Original article URL (optional)
    
    Returns:
        JSON with image URL
    """
    try:
        from openai import OpenAI
        import os
        import requests
        from bs4 import BeautifulSoup
        
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Method 1: Try to get image from source URL
        if source_url and source_url.startswith('http'):
            try:
                print(f"[DEBUG] Attempting to fetch image from source: {source_url}")
                
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(source_url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Try OpenGraph image first
                og_image = soup.find('meta', property='og:image')
                if og_image and og_image.get('content'):
                    image_url = og_image['content']
                    print(f"[DEBUG] Found OpenGraph image: {image_url[:80]}...")
                    return json.dumps({
                        'success': True,
                        'image_url': image_url,
                        'method': 'scraped_og_image',
                        'note': 'Featured image from article'
                    })
                
                # Try Twitter image
                twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
                if twitter_image and twitter_image.get('content'):
                    image_url = twitter_image['content']
                    print(f"[DEBUG] Found Twitter image: {image_url[:80]}...")
                    return json.dumps({
                        'success': True,
                        'image_url': image_url,
                        'method': 'scraped_twitter_image',
                        'note': 'Featured image from article'
                    })
                
            except Exception as e:
                print(f"[DEBUG] Scraping failed: {e}")
        
        # Method 2: Generate with DALL-E
        print(f"[DEBUG] Generating image with DALL-E...")
        
        # Create a generic prompt based on brand voice
        prompt = f"""Create a vibrant, professional image for a social media post.

Brand/Industry: {brand_voice}
Post Topic: {headline}
Content Context: {idea_summary[:300]}

Style: Modern, engaging, professional imagery that reflects the brand's identity and the content topic.
Bold colors, clean composition. Suitable for Instagram/Facebook.
NO text or words in the image.

The image should visually represent the topic and appeal to the target audience."""
        
        dalle_response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1
        )
        
        image_url = dalle_response.data[0].url
        
        print(f"[DEBUG] Generated DALL-E image: {image_url[:80]}...")
        
        return json.dumps({
            'success': True,
            'image_url': image_url,
            'method': 'dalle_generated',
            'note': 'AI-generated image. Download and upload to permanent storage if needed.'
        })
        
    except Exception as e:
        import traceback
        print(f"[ERROR] Image retrieval failed: {e}")
        return json.dumps({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        })
    


def get_top_posts(client_id: str, limit: int = 3):
    """Fetch the top curated posts waiting for approval for a client."""
    posts = get_posts_for_client(client_id, status="Needs Approval", limit=limit)
    return [
        {
            "id": p["id"],
            "content": p["fields"].get("Caption", ""),
            "image_url": p["fields"].get("image_url", ""),
            "hashtags": p["fields"].get("Hashtags", ""),
            "status": p["fields"].get("Approval Status", "Needs Approval")
        }
        for p in posts
    ]



def get_all_posts(client_id: str):
    """Fetch all pending posts for a client."""
    posts = get_posts_for_client(client_id, status="Needs Approval")
    return [
        {
            "id": p["id"],
            "content": p["fields"].get("Caption", ""),
            "image_url": p["fields"].get("image_url", ""),
            "hashtags": p["fields"].get("Hashtags", ""),
            "status": p["fields"].get("Approval Status", "Needs Approval")
        }
        for p in posts
    ]



def update_post_content(post_id: str, new_content: str):
    """
    Update only the caption/content of a post.
    """
    try:
        updated = update_post(post_id, {"Caption": new_content})
        return {
            "id": updated["id"],
            "content": updated["fields"].get("Caption", ""),
            "image_url": updated["fields"].get("image_url", ""),
        }
    except Exception as e:
        print(f"[ERROR] update_post_content failed: {e}")
        return None


def update_post_image(post_id: str, new_image_url: str):
    """
    Update only the image of a post.
    """
    try:
        updated = update_post(post_id, {"image_url": new_image_url})
        return {
            "id": updated["id"],
            "content": updated["fields"].get("Caption", ""),
            "image_url": updated["fields"].get("image_url", ""),
        }
    except Exception as e:
        print(f"[ERROR] update_post_image failed: {e}")
        return None


def get_report(client_id: str):
    """
    Get weekly posting summary for a client (posts, scheduled, curated ideas).
    """
    try:
        return get_summary_for_client(client_id)
    except Exception as e:
        print(f"[ERROR] get_report failed: {e}")
        return {
            "posts_this_week": 0,
            "scheduled_posts": 0,
            "ideas_curated": 0,
            "engagement_summary": "N/A"
        }


def get_analytics(client_id: str):
    """
    Get recent analytics data (reach, impressions, clicks, etc.).
    """
    try:
        return get_analytics_for_client(client_id)
    except Exception as e:
        print(f"[ERROR] get_analytics failed: {e}")
        return {
            "reach": 0,
            "impressions": 0,
            "clicks": 0,
            "ctr": "0%"
        }
# ============================================================================
# AGENT DEFINITION
# ============================================================================

def create_post_agent():
    """
    Create the Post Creation Agent.
    
    Returns:
        Agent configured for post creation
    """
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
    
    agent = Agent(
        role="Social Media Copywriter",
        
        goal="Transform curated marketing ideas into engaging, structured, and audience-ready social media posts, that will perform well based on both writing quality and historical performance",
        
        backstory="""You are a skilled social media copywriter who knows how to turn raw ideas into posts that grab attention and drive engagement. You never write dull or generic captions.

**Your approach:**
You combine creative writing skills with data-driven decision making. For every post, you:
1. Create multiple variants exploring different angles
2. Evaluate each variant's writing quality
3. Compare each variant to historical top-performing content
4. Choose the variant with the best combined score


### Writing Principles (must follow):
    - **Hook**: Start with emotion, question, or bold statement
    - **Story**: Connect people to the experience or value
    - **Urgency**: Create FOMO when appropriate
    - **Authenticity**: Match the brand voice, never generic
    - **Adaptation**: Adjust tone and style based on client instructions
    
### Output Formatting Rules (MUST FOLLOW)
    - Use **bold headers** for **Hook**
    - Put a blank line between sections (use `\n\n`).
    - Never collapse everything into one paragraph.
    - Each section can be 1–3 sentences maximum.
    - Caption must be suitable for direct posting (no extra commentary).
    - Image: From source or AI-generated
    - Post length: 100–150 words (not just 1–2 lines)

    - Tone: Conversational, warm, and audience-focused
    - Always include hashtags (3–5, varied and relevant)
    - If link_url provided, include a clear **CTA** like:  
          "🎟️ Get your tickets now: <link>"

    

### Example Structure:
        ❓ Hook: Start with a bold emotional question, or interesting announcement
        
        
        📖 Story: Explain the event or value in 2–3 sentences  
        
        
        ⏳ Urgency or importance: Add limited time / don’t miss it phrasing if applicable, or why this post is relevant for our audience  
        
        
        🙌 CTA: Create a CTA that matches: "Read the full review", "Learn more", "Get details" and add the link 
        
        
        #️⃣ Hashtags

**Evaluation criteria:**
- Writing Quality (60%): Hook, emotion, clarity, CTA, brand alignment
- Historical Performance (40%): Similarity to past successful posts

You MUST evaluate every variant before choosing, and you MUST use the 'Create Social Post' tool to save the winner with both scores.""",
        
        tools=[
            get_idea_details,
            get_brand_guidelines,
            evaluate_post_variant,
            compare_post_to_history,
            create_social_post,
            get_post_image
        ],
        
        llm=llm,
        verbose=True,
        allow_delegation=False
    )
    
    return agent
