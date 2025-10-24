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
    _tbl
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
            'source_detail': fields.get('Source Detail', ''),
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
            'approval_mode': config['approval_mode']
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool("Evaluate Post Variant")
def evaluate_post_variant(caption: str, hashtags: str, cta: str, brand_voice: str) -> str:
    """
    Evaluate a post variant for writing quality.
    
    Args:
        caption: The post caption text
        hashtags: Space-separated hashtags
        cta: Call to action
        brand_voice: Brand voice to evaluate against
    
    Returns:
        JSON with quality score and evaluation breakdown
    """
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
        
        prompt = f"""Evaluate this social media post for a theatre company:

CAPTION: {caption}
HASHTAGS: {hashtags}
CTA: {cta}
BRAND VOICE: {brand_voice}

Score the post on these criteria (0-10 each):
1. Hook Strength: Does it grab attention in first 5 words?
2. Emotional Appeal: Does it create excitement about theatre?
3. Clarity: Is the message clear and concise?
4. CTA Effectiveness: Does it drive action (tickets, engagement)?
5. Brand Alignment: Does it match the brand voice?

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
        from tools.airtable_utils import get_history_for_client
        
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
def create_social_post(client_id: str, idea_id: str, channel: str, 
                       caption: str, hashtags: str, cta: str, 
                       quality_score: float, similarity_score: float) -> str:
    """
    Save a post to Airtable with evaluation scores.
    
    Args:
        client_id: Client's Airtable record ID
        idea_id: Source idea's record ID
        channel: Facebook/Instagram/LinkedIn
        caption: Post text (max 500 chars)
        hashtags: Space-separated hashtags
        cta: Call to action
        quality_score: Writing quality score (0-10)
        similarity_score: Historical similarity score (0-1)
    
    Returns:
        Success message with post ID
    """
    try:
        # Validate inputs
        if channel not in ['Facebook', 'Instagram', 'LinkedIn']:
            return json.dumps({"error": "Channel must be Facebook/Instagram/LinkedIn"})
        
        if len(caption) > 500:
            return json.dumps({"error": "Caption too long (max 500 chars)"})
        
        # Get idea details for source_type and image
        idea = get_idea(idea_id)
        idea_fields = idea['fields']
        source_type = idea_fields.get('Source Type', 'Other')
        image_url = idea_fields.get('Image URL')
        
        # Get client config for approval mode
        config = get_client_config(client_id)
        approval_mode = config['approval_mode']
        
        # Calculate combined impact score (weighted average)
        # Quality: 60%, Similarity: 40%
        impact_score = (quality_score / 10 * 0.6) + (similarity_score * 0.4)
        
        # Create post
        post = create_post(
            client_id=client_id,
            idea_id=idea_id,
            channel=channel,
            caption=caption,
            hashtags=hashtags,
            cta=cta,
            impact_score=impact_score,
            source_type=source_type,
            image_url=image_url,
            approval_mode=approval_mode
        )
        
        # Mark idea as processed
        mark_idea_processed(idea_id)
        
        return json.dumps({
            'success': True,
            'post_id': post['id'],
            'channel': channel,
            'impact_score': round(impact_score, 3),
            'quality_score': quality_score,
            'similarity_score': similarity_score,
            'approval_status': post['fields'].get('Approval Status'),
            'caption_preview': caption[:50] + '...'
        })
        
    except Exception as e:
        return json.dumps({"error": str(e)})


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
        
        goal="Create engaging, data-driven social media posts that will perform well based on both writing quality and historical performance",
        
        backstory="""You're a skilled social media copywriter specializing in arts and theatre content.

**Your approach:**
You combine creative writing skills with data-driven decision making. For every post, you:
1. Create multiple variants exploring different angles
2. Evaluate each variant's writing quality
3. Compare each variant to historical top-performing content
4. Choose the variant with the best combined score

**Writing principles for theatre content:**
- Hook: Start with emotion, question, or bold statement
- Story: Connect people to the experience
- Urgency: Limited tickets, closing soon, don't miss
- Community: Celebrate local theatre culture
- Authenticity: Passionate but not salesy

**Evaluation criteria:**
- Writing Quality (60%): Hook, emotion, clarity, CTA, brand alignment
- Historical Performance (40%): Similarity to past successful posts

You MUST evaluate every variant before choosing, and you MUST use the 'Create Social Post' tool to save the winner with both scores.""",
        
        tools=[
            get_idea_details,
            get_brand_guidelines,
            evaluate_post_variant,
            compare_post_to_history,
            create_social_post
        ],
        
        llm=llm,
        verbose=True,
        allow_delegation=False
    )
    
    return agent