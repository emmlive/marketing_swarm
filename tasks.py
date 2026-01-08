from crewai import Task
# Import all agents from your independent agents.py file
from agents import market_analyst, creative_director, proofreader, social_media_manager, vision_inspector

# Task 1: Comprehensive Market Analysis
research_task = Task(
    description=(
        "Research the {service} market within the {industry} industry in {city}. "
        "1. Identify the top 3 local competitors providing {service} and their pricing if available. "
        "2. Find common customer complaints in local reviews (e.g., arrival times, pricing, mess). "
        "3. Identify current weather or seasonal factors in {city} that increase demand for {service}."
    ),
    expected_output=(
        "A detailed report on the {city} {service} market, including a competitor map, "
        "a list of local 'pain points', and 3 seasonal 'hooks' specifically for {service}."
    ),
    agent=market_analyst
)

# Task 2: High-Converting Ad Copy Generation
creative_task = Task(
    description=(
        "Using the research provided, create 3 distinct Facebook ad variations for a {service} business. "
        "Variation 1: Focus on the primary benefit of {service} (e.g., safety, comfort, or convenience). "
        "Variation 2: Focus on 'No Hidden Fees' and 'Upfront Pricing' to build trust. "
        "Variation 3: Urgent seasonal offer based on {city}'s current climate and how it affects {service}. "
        "Include a 'Headline', 'Body Copy', and 'Call to Action' for each."
    ),
    expected_output=(
        "A document containing 3 ready-to-use ad scripts for {service} formatted in Markdown, "
        "optimized for local {city} homeowners."
    ),
    agent=creative_director,
    output_file="marketing_strategy.md"
)

# Task 3: Quality Assurance & Proofreading
review_task = Task(
    description=(
        "Review the 3 Facebook ad variations created for {service} in {city}. "
        "1. Fix any grammar or spelling errors. 2. Remove repetitive phrases. "
        "3. Ensure the tone is empathetic yet professional, suitable for the {industry} industry. "
        "4. Verify that each ad has a clear Headline, Body Copy, and CTA."
    ),
    expected_output="A final, polished version of the 3 {service} Facebook ads in Markdown format.",
    agent=proofreader,
    output_file="final_marketing_strategy.md"
)

# Task 4: 7-Day Social Media Campaign Management
campaign_task = Task(
    description=(
        "Using the final polished ads for {service} in {city}, create a 7-day social media posting schedule. "
        "Day 1, 3, and 5 should use the ad variations provided in the context. "
        "Day 2, 4, 6, and 7 should provide helpful 'Did you know?' tips about {service} "
        "or general {industry} maintenance to build trust with the {city} community. "
        "Each day must include: Day Number, Post Text, and a suggested Image/Video idea."
    ),
    expected_output="A complete 7-day social media calendar for {service} formatted in Markdown.",
    agent=social_media_manager,
    context=[review_task], 
    output_file="full_7day_campaign.md"
)

# Task 5: Vision Inspector - Visual Strategy & Brand-Locked AI Prompts
vision_task = Task(
    description=(
        "Review the polished ads and the social schedule for {service} in {city}. "
        "Your goal is to generate 3 art-directed AI Image Prompts for DALL-E 3 that strictly "
        "adhere to the 'BreatheEasy' Brand Kit. "
        "\n\n"
        "MANDATORY INSTRUCTIONS:\n"
        "1. Apply the primary colors: 'Trust Blue' (#0056b3) and 'Clean White' to every concept.\n"
        "2. Ensure every prompt specifies 'bright, airy, natural high-key daylight'.\n"
        "3. Incorporate {city} suburban aesthetics and visual cues related to {service} "
        "(e.g., clean tools, professional technicians, high-end {industry} fixtures).\n"
        "4. Use technical keywords: 'photorealistic, 8k, commercial photography, bokeh background'.\n"
        "5. Each prompt MUST start with the exact prefix: 'AI Image Prompt: '.\n"
    ),
    expected_output="A visual strategy guide for {service} with 3 consistent, brand-aligned image prompts.",
    agent=vision_inspector,
    context=[review_task, campaign_task], 
    output_file="visual_strategy.md"
)

print("✅ Tasks Created: Swarm is now dynamic across industries and services.")