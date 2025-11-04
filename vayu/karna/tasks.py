# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""

"""
agents/marketing/tasks.py

Task definitions for Karna marketing agents
"""

from crewai import Task


def create_idea_curation_task(agent, client_id: str, client_name: str, num_ideas: int = 20):
    """
    Task for curating and scoring content ideas.
    
    Args:
        agent: The idea curation agent
        client_id: Airtable client record ID
        client_name: Client name for context
        num_ideas: Max number of ideas to review
    
    Returns:
        Configured Task
    """
    
    task = Task(
        description=f"""Curate content ideas for {client_name} (ID: {client_id}).

**Your Process:**

1. **Fetch Ideas**: Get up to {num_ideas} new ideas using the 'Fetch New Ideas' tool

2. **Understand Brand**: Use 'Get Client Brand Info' to understand {client_name}'s voice and preferences

3. **Analyze Performance**: Use 'Get Performance History' to see what content works, then use 'Compare Idea to History' to calculate semantic similarity for each idea

4. **Score Each Idea**: Evaluate each idea on:
   - Brand Alignment (35pts)
   - Audience Relevance (25pts)
   - Performance Potential (15pts)
   - Timeliness (15pts)
   - Quality (10pts)
   
   Total score = 0-100
   Priority: High (80+), Medium (50-79), Low (<50)

5. **Update Priorities**: Use 'Update Idea Score' for each idea with:
   - Priority level
   - Quality score
   - Brief Reasoning in the field Curation Notes (1-2 sentences)
   
   CRITICAL: You MUST call the 'Update Idea Score' tool, exactly by that name without adding any character or formatting it 

**Output Requirements:**
Return a summary with:
- Total ideas reviewed
- Number of High/Medim/Low priority
- Top 3 ideas to prioritize
- Any ideas to reject
""",
        
        expected_output="""A structured summary containing:
1. Statistics: Total reviewed, priority breakdown
2. Top Priority Ideas: List of 3-5 best ideas with scores
3. Recommendations: Which ideas to create posts from first
4. Any red flags or ideas to skip

Format as clear, actionable recommendations.""",
        
        agent=agent
    )
    
    return task


def create_post_creation_task(agent, client_id: str, idea_ids: list):
    """
    Task for creating social media posts from curated ideas.
    
    Args:
        agent: The post creation agent
        client_id: Airtable client record ID
        idea_ids: List of idea IDs to convert to posts
    
    Returns:
        Configured Task
    """
    
    ideas_str = ', '.join(idea_ids) if idea_ids else 'Top priority ideas from curation'
    
    task = Task(
        description=f"""Create engaging, data-driven social media posts from curated ideas.

**Client ID:** {client_id}
**Ideas to process:** {ideas_str}

⚠️ IMPORTANT RULES:
- You must ONLY call `Get Idea Details` with one of these valid IDs: {ideas_str}.
- ❌ Do NOT invent or guess idea IDs.
- If unsure, skip the idea rather than making up an ID.

**MANDATORY PROCESS - FOLLOW EXACTLY) in ORDER:**

1. Get brand guidelines for the client using 'Get Brand Guidelines' tool

2. For EACH idea:
   
   a. STEP A: Use 'Get Idea Details' tool to fetch the full idea
   
   b. STEP B: **Get an image (MANDATORY - DO NOT SKIP) using 'Get Post Image' tool:**
      - Pass: idea ID, idea summary, headline, brand_voice (from step 1), and source_url
      - Tool will first check if an image exists in Image URL field, if yes use it
       - Otherwise, try to scrape from source first
      - If no image found, will generate with DALL-E based on brand context
      - Save the returned image_url to use in posts
      
   c. STEP C: Use 'create_post_variants' tool to create 3 variants of the post with different angles:
      - Variant 1: Emotional/storytelling approach
      - Variant 2: Informational/educational approach
      - Variant 3: Urgency/FOMO approach
   
   d. For EACH variant:
      - Use 'Evaluate Post Variant' to get writing quality score
      - Use 'Compare Post to History' to get similarity score
      - Record both scores
   
   e. Choose the variant with highest combined score (60% quality + 40% similarity)
   
   f. CRITICAL: Save the winner using 'Create Social Post' tool:
       - Include ALL parameters: client_id, idea_id, channel, caption, hashtags, cta, image_url, quality_score, similarity_score
       - Use the image_url from step 2b
       - Create for both Facebook and Instagram (2 posts per idea)
       - Wait for confirmation that post was saved successfully
       - If tool returns error, report it immediately
   
      
   g. 
    **CTA and Link Guidelines:**
    - The source_url from the idea is the article/show page that was scraped
    - Use this as the link URL for the post
    - Create a CTA that matches: "Read the full review", "Learn more", "Get details"
    - For ticket sales, note that link goes to the article, not direct ticket purchase

3. Verify each post was saved by checking for post_id in the tool response


### Writing Principles (must follow):
    - **Hook**: Start with emotion, question, or bold statement
    - **Story**: Connect people to the experience or value
    - **Urgency**: Create FOMO when appropriate
    - **Authenticity**: Match the brand voice, never generic
    - **Adaptation**: Adjust tone and style based on client instructions

### Output Requirements:
    
    **Writing rules:**
    - Start with a bold emoji + bold hook line (e.g., "❓ **Ready for…**")
    - Then a story paragraph
    - Then urgency (if relevant)
    - If link_url provided, include a clear **CTA** like:  
          "🎟️ Get your tickets now: <link>"
    - End with hashtags 
    - Separate sections with blank lines (`\\n\\n`)
    - Do NOT output "Hook:", "Story:", etc. labels
    - Use client brand voice
    - Image: From source or AI-generated
    - Post length: 100–150 words (not just 1–2 lines)
    - Format: Use short paragraphs (1–2 sentences each), separated by line breaks
    - Tone: Conversational, warm, and audience-focused



    **Output format requirement:**
    Return exactly this structure:

    {{
      "posts": [
        {{
          "idea_id": "<one of {idea_ids}>",
          "caption": "<full post caption, multi-line, emojis allowed>",
          "hashtags": "#tag1 #tag2 #tag3",
          "cta": "🎟️ Book now: <URL>",
          "client_id": "{client_id}",
          "quality_score": <float 0-10>
        }},
        ...
      ]
    }}

    Rules:
    - Must be valid JSON only.
    - No markdown, no commentary, no explanation.
    - Every object must have all fields.



### Example Post Structure:
        ❓ Hook: Start with a bold emotional question, or interesting announcement
        
        
        📖 Story: Explain the event or value in 2–3 sentences  
        
        
        ⏳ Urgency or importance: Add limited time / don’t miss it phrasing if applicable, or why this post is relevant for our audience 
        
        
        🙌 CTA: Create a CTA that matches: "Read the full review", "Learn more", "Get details" and add the link 
        
        
        #️⃣ Hashtags
        


**ABSOLUTE REQUIREMENTS:**
- You MUST get an image for every post using 'Get Post Image' tool
- You MUST call 'Create Social Post' tool for EVERY post
- You MUST include both quality_score and similarity_score
- You MUST verify each save was successful
- DO NOT just summarize - you must SAVE to Airtable
- If ANY tool call fails, report the error immediately


**VALIDATION:**
Before calling 'Create Social Post', verify you have:
- ✓ image_url from 'Get Post Image' tool
- ✓ quality_score from evaluation
- ✓ similarity_score from comparison
- If missing image_url, GO BACK to Step B

**DO NOT SKIP THE IMAGE STEP**


""",
        
        expected_output="""For EACH idea, you must show:
1. Image obtained (method used: scraped or generated)
2. All 3 variants with their evaluation scores
3. Which variant was chosen and why
4. **CONFIRMATION of Airtable post ID for Facebook post**
5. **CONFIRMATION of Airtable post ID for Instagram post**
6. Any errors encountered

Final summary MUST include:
- List of ALL Airtable post IDs created
- Total posts saved: X
- Images: X scraped, X generated
- Any failures with error messages

If you did not get post IDs, the task is INCOMPLETE.""",
        
        agent=agent
    )
    
    return task


def create_publishing_task(agent, client_id: str = None):
    """
    Task for publishing approved posts to social media platforms.
    
    Args:
        agent: The publishing agent
        client_id: Optional - specific client ID, or None for all clients
    
    Returns:
        Configured Task
    """
    
    client_filter = f"for client {client_id}" if client_id else "for all clients"
    
    task = Task(
        description=f"""Publish approved social media posts to their respective platforms.

**Scope:** {client_filter}

**Your Process:**

1. Use 'Get Posts Ready to Publish' tool to find all approved posts that are ready

2. For EACH post found:
   
   a. Verify it has all required fields:
      - Channel (Facebook/Instagram/LinkedIn)
      - Caption
      - Client ID (for auth tokens)
      - Image URL (if available)
      - Link URL (if available)
   
   b. Use 'Publish Post to Platform' tool with ALL parameters:
      - post_id
      - client_id
      - channel
      - caption
      - hashtags
      - link_url
      - image_url
   
   c. Wait for confirmation that post was published
   
   d. Record the platform post ID returned
   e. Update status to Published

3. Handle any errors gracefully:
   - If credentials missing, report which client needs setup
   - If publishing fails, report the error
   - Continue with remaining posts

**CRITICAL:**
- You MUST call 'Publish Post to Platform' for EVERY post
- Do NOT skip this step
- Do NOT assume posts are published
- Do NOT make up results
- ACTUALLY CALL THE TOOL

**Example:**
If you get 1 post from step 1, you MUST make 1 call to 'Publish Post to Platform' in step 2.
If you get 3 posts, you MUST make 3 calls.

**CRITICAL:**
- Only publish posts with Approval Status = "Approved" or "Auto-Approved"
- Only publish if Scheduled At time has passed (or is blank)
- Update Airtable status after each publish
- Never publish the same post twice
""",
        
        expected_output="""Publishing report with:

1. **Total posts :** X

2. **Successfully published:** (with Platform Post ID)

3. **Failed publishes:**
   - Report failure with Airtable record ID: recZZZZ → Error: Missing Instagram credentials

4. **Next scheduled posts:**
   - X posts scheduled for later times

**Summary:** X published, Y failed, Z pending

If no posts were ready, state "No posts ready to publish at this time." """,
        
        agent=agent
    )
    
    return task

def create_scoring_task(agent, post_ids: list):
    """
    Task for scoring posts against historical performance.
    
    Args:
        agent: The scoring agent
        post_ids: List of post IDs to score
    
    Returns:
        Configured Task
    """
    
    task = Task(
        description=f"""Score these draft posts for predicted performance.

**Posts to score:** {', '.join(post_ids)}

**Your Process:**

1. Retrieve draft posts from Airtable
2. Get historical performance data
3. Generate embeddings for comparison
4. Calculate similarity scores
5. Predict engagement (0-1 scale)
6. Update Impact Score in Airtable

**Scoring Factors:**
- Semantic similarity to high-performing content
- Hashtag effectiveness
- Caption length and structure
- Call-to-action strength
""",
        
        expected_output="""Scoring report with:
1. Each post's predicted impact score (0-1)
2. Comparison to historical averages
3. Confidence level in predictions
4. Recommendations for improvements

All scores saved to Airtable.""",
        
        agent=agent
    )
    
    return task


