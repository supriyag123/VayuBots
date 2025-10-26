# -*- coding: utf-8 -*-
"""
Created on Sun Oct 12 02:01:14 2025

@author: supri
"""

"""
agents/marketing/agents/idea_agent.py

Idea Curation Agent - Reviews and prioritizes content ideas
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
    get_new_ideas,
    get_client_config,
    get_history_for_client,
    _tbl
)


# ============================================================================
# TOOLS FOR IDEA AGENT
# ============================================================================

@tool("Fetch New Ideas")
def fetch_ideas_for_curation(client_id: str, limit: int = 20) -> str:
    """
    Fetch new ideas from Airtable that need review and scoring.
    
    Args:
        client_id: Client's Airtable record ID
        limit: Max ideas to fetch (default: 20)
    
    Returns:
        JSON with ideas list
    """
    try:
        ideas = get_new_ideas(limit=limit, client_id=client_id)
        
        if not ideas:
            return json.dumps({"message": "No new ideas", "ideas": []})
        
        ideas_data = []
        for idea in ideas:
            fields = idea['fields']
            summary = fields.get('Summary', '')
            ideas_data.append({
                'id': idea['id'],
                'headline': fields.get('Headline', ''),
                'summary': summary,
                'source_type': fields.get('Source Type', ''),
                'priority': fields.get('Priority', 'Medium'),
                'has_image': fields.get('Image Provided?', False)
            })
        
        return json.dumps({
            'total': len(ideas_data),
            'client_id': client_id,
            'ideas': ideas_data
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool("Get Client Brand Info")
def get_client_brand_info(client_id: str) -> str:
    """
    Get client's brand voice and preferences.
    
    Args:
        client_id: Client's Airtable record ID
    
    Returns:
        JSON with brand guidelines
    """
    try:
        config = get_client_config(client_id)
        
        return json.dumps({
            'name': config['name'],
            'brand_voice': config['brand_voice'],
            'channels': config['preferred_channels']
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool("Get Performance History")
def get_performance_insights(client_id: str) -> str:
    """
    Get historical post performance to understand what works.
    
    Args:
        client_id: Client's Airtable record ID
    
    Returns:
        JSON with performance insights
    """
    try:
        history = get_history_for_client(client_id, limit=30)
        
        if not history:
            return json.dumps({"message": "No history available"})
        
        posts = []
        total_eng = 0
        has_embeddings = 0
        
        for record in history:
            fields = record['fields']
            likes = fields.get('Likes', 0)
            shares = fields.get('Shares', 0)
            comments = fields.get('Comments', 0)
            eng = likes + (shares * 3) + (comments * 2)
            total_eng += eng
            
            # Check if embedding exists and parse it
            embedding_str = fields.get('Embedding', '')
            has_embedding = False
            
            if embedding_str:
                try:
                    # Parse comma-separated string to list
                    if isinstance(embedding_str, str) and ',' in embedding_str:
                        embedding_list = [float(x.strip()) for x in embedding_str.split(',')]
                        if len(embedding_list) > 100:  # Valid embedding
                            has_embedding = True
                            has_embeddings += 1
                except:
                    pass
            
            posts.append({
                'text': fields.get('Post Text', '')[:80] + '...',
                'engagement': eng,
                'likes': likes,
                'shares': shares,
                'comments': comments,
                'has_embedding': has_embedding
            })
        
        posts.sort(key=lambda x: x['engagement'], reverse=True)
        
        return json.dumps({
            'total_posts': len(history),
            'posts_with_embeddings': has_embeddings,
            'avg_engagement': round(total_eng / len(history), 2) if len(history) > 0 else 0,
            'top_3': posts[:3],
            'bottom_3': posts[-3:],
            'note': f'{has_embeddings}/{len(history)} posts have embeddings for semantic comparison'
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool("Update Idea Score")
def update_idea_score(idea_id: str, priority: str, score: int, notes: str) -> str:
    """
    Update idea with quality score and priority.
    
    Args:
        idea_id: Idea's Airtable record ID
        priority: High/Medium/Low
        score: Quality score 0-100
        notes: Brief reasoning
    
    Returns:
        Success message
    """
    try:
        if priority not in ['High', 'Medium', 'Low']:
            return json.dumps({"error": "Priority must be High/Medium/Low"})
        
        if not (0 <= score <= 100):
            return json.dumps({"error": "Score must be 0-100"})
        
        table = _tbl("Ideas")
        table.update(idea_id, {
            "Priority": priority,
            "Quality Score": score,
            "Curation Notes": notes[:500]
        })
        
        return json.dumps({
            "success": True,
            "idea_id": idea_id,
            "priority": priority,
            "score": score
        })
        
    except Exception as e:
        return json.dumps({"error": str(e)})

from langchain_openai import OpenAIEmbeddings
import numpy as np

@tool("Compare Idea to History")
def compare_idea_to_history(client_id: str, idea_text: str) -> str:
    """
    Compare an idea's content to historical performance using embeddings.
    
    Args:
        client_id: Client's Airtable record ID
        idea_text: The idea text to compare
    
    Returns:
        JSON with similarity scores to top/bottom performing posts
    """
    try:
        # Get history with embeddings
        history = get_history_for_client(client_id, limit=50)
        
        if not history:
            return json.dumps({"message": "No history available"})
        
        # Generate embedding for the idea
        embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")
        idea_embedding = embeddings_model.embed_query(idea_text)
        
        # Calculate similarities
        similarities = []
        
        for record in history:
            fields = record['fields']
            embedding_str = fields.get('Embedding', '')
            
            if not embedding_str:
                continue
            
            try:
                # Parse embedding
                if isinstance(embedding_str, str) and ',' in embedding_str:
                    hist_embedding = [float(x.strip()) for x in embedding_str.split(',')]
                else:
                    continue
                
                # Calculate cosine similarity
                dot_product = np.dot(idea_embedding, hist_embedding)
                norm_idea = np.linalg.norm(idea_embedding)
                norm_hist = np.linalg.norm(hist_embedding)
                similarity = dot_product / (norm_idea * norm_hist)
                
                # Get engagement
                likes = fields.get('Likes', 0)
                shares = fields.get('Shares', 0)
                comments = fields.get('Comments', 0)
                engagement = likes + (shares * 3) + (comments * 2)
                
                similarities.append({
                    'post_text': fields.get('Post Text', '')[:60] + '...',
                    'similarity': round(float(similarity), 3),
                    'engagement': engagement
                })
            except Exception as e:
                continue
        
        if not similarities:
            return json.dumps({"message": "No embeddings found in history"})
        
        # Sort by engagement
        similarities.sort(key=lambda x: x['engagement'], reverse=True)
        
        # Get top performers (high engagement)
        top_performers = similarities[:5]
        
        # Calculate average similarity to top performers
        avg_sim_to_top = sum(p['similarity'] for p in top_performers) / len(top_performers)
        
        return json.dumps({
            'avg_similarity_to_top_posts': round(avg_sim_to_top, 3),
            'most_similar_top_post': top_performers[0] if top_performers else None,
            'comparison_count': len(similarities),
            'interpretation': f"{'High' if avg_sim_to_top > 0.7 else 'Medium' if avg_sim_to_top > 0.5 else 'Low'} similarity to successful content"
        }, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})
# ============================================================================
# AGENT DEFINITION
# ============================================================================

def create_idea_agent():
    """
    Create the Idea Curation Agent.
    
    Returns:
        Agent configured for idea curation
    """
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    
    agent = Agent(
        role="Content Idea Curator",
        
        goal="Review new content ideas, score them for quality and relevance, and UPDATE EACH ONE IN AIRTABLE using the Update Idea Score tool",
        
        backstory="""You're an experienced social media content strategist who evaluates ideas based on:
        
        - Brand Alignment (25pts): Fits the client's voice and values?
        - Audience Relevance (15pts): Will the target audience care?
        - Performance Potential (25pts): Similar to past successful content?
        - Timeliness (15pts): Topical and timely?
        - Quality (20pts): Well-developed and complete?
        
        You provide clear scores (0-100) and set priority levels (High/Medium/Low).
        You're fair but discerning - not every idea deserves high priority.
        
        CRITICAL: You MUST call the 'Update Idea Score' tool, exactly by that name without adding any character or formatting it, for EVERY idea you review. 
        This is not optional. After scoring each idea, immediately update it in Airtable.
        Do not just report scores - actually save them using the tool.
        CRITICAL RULES:
            - For EVERY idea, you MUST call the tool exactly as 'Update Idea Score'.
            - Update one idea at a time (never in batches, never in arrays).
            - The tool input must always be a single JSON dictionary with keys:
                { "idea_id": ..., "priority": "High|Medium|Low", "score": <int>, "notes": "<string>" }
                - Do not wrap inputs in lists or arrays.
                - Do not include extra characters, dashes, or formatting.
                
        
        """,
        
        tools=[
            fetch_ideas_for_curation,
            get_client_brand_info,
            get_performance_insights,
            compare_idea_to_history,
            update_idea_score
        ],
        
        llm=llm,
        verbose=True,
        allow_delegation=False
    )
    
    return agent
