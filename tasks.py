from crewai import Task
# Import all agents from your independent agents.py file
from agents import market_analyst, creative_director, proofreader, social_media_manager, vision_inspector

class MarketingTasks:
    # Task 1: Comprehensive Market Analysis
    def research_task(self, agent, city, industry, service, premium):
        premium_focus = (
            "Focus on high-net-worth neighborhoods and premium equipment brands like Lennox, Trane, and Bosch. "
            "Analyze the ROI of high-efficiency systems for affluent homeowners."
            if premium else 
            "Focus on general market competitors and local pricing trends for standard service demand."
        )
        
        return Task(
            description=(
                f"Research the {service} market within the {industry} industry in {city}. "
                f"1. {premium_focus} "
                f"2. Identify the top 3 local competitors providing {service} and their pricing. "
                f"3. Find common customer complaints in local reviews (arrival times, mess, etc.). "
                f"4. Identify current seasonal factors in {city} that increase demand for {service}."
            ),
            expected_output=(
                f"A detailed report on the {city} {service} market, including a competitor map, "
                "a list of local 'pain points', and 3 seasonal 'hooks' specifically for premium customers."
            ),
            agent=agent
        )

    # Task 2: High-Converting Ad Copy & Blog Generation
    def creative_task(self, agent, city, industry, service, premium, blog):
        tone = "sophisticated, authoritative, and investment-focused" if premium else "friendly, helpful, and value-driven"
        
        blog_instruction = ""
        if blog:
            blog_instruction = (
                f"\n\nEXTRA MANDATORY TASK: Write a 1,000-word SEO-optimized blog post titled: "
                f"'The Ultimate {city} Homeowner's Guide to {service}: Why Quality is a Long-Term Investment'. "
                f"Use H2 subheaders, target {city} local keywords, and focus on health, efficiency, and home value."
            )

        return Task(
            description=(
                f"Using the research, create 3 distinct Facebook ad variations for a {service} business in {city}. "
                f"The tone must be {tone}. "
                "Variation 1: Focus on Safety/Comfort. Variation 2: Focus on Transparency. "
                f"Variation 3: Urgent seasonal offer based on local climate. {blog_instruction}"
            ),
            expected_output="3 ready-to-use ad scripts AND a 1,000-word SEO blog (if requested), formatted in Markdown.",
            agent=agent,
            output_file="marketing_strategy.md"
        )

    # Task 3: Quality Assurance & Proofreading
    def review_task(self, agent, city, industry, service):
        return Task(
            description=(
                f"Review the marketing strategy and blog created for {service} in {city}. "
                "1. Fix any grammar or spelling errors. 2. Ensure high-ticket professional terminology. "
                f"3. Ensure the tone is professional, suitable for the {industry} industry. "
                "4. Verify that the SEO blog (if present) uses correct H1, H2, and H3 tags."
            ),
            expected_output="A final, polished version of the marketing strategy and blog in Markdown format.",
            agent=agent,
            output_file="final_marketing_strategy.md"
        )

    # Task 4: 7-Day Social Media Campaign
    def campaign_task(self, agent, city, industry, service, context_task):
        return Task(
            description=(
                f"Using the polished ads for {service} in {city}, create a 7-day social media schedule. "
                "Include: Day Number, Post Text, and a suggested Image/Video idea."
            ),
            expected_output="A complete 7-day social media calendar for {service} formatted in Markdown.",
            agent=agent,
            context=[context_task], 
            output_file="full_7day_campaign.md"
        )

    # Task 5: Vision Inspector - AI Prompts
    def vision_task(self, agent, city, industry, service, context_tasks):
        return Task(
            description=(
                f"Review the strategy for {service} in {city}. "
                "Generate 3 DALL-E 3 Image Prompts brand-locked to 'BreatheEasy'. "
                "Use 'Trust Blue' (#0056b3) and photorealistic 8k aesthetics. "
                "Each prompt MUST start with: 'AI Image Prompt: '."
            ),
            expected_output="A visual strategy guide with 3 consistent, brand-aligned image prompts.",
            agent=agent,
            context=context_tasks, 
            output_file="visual_strategy.md"
        )

# This message will appear in your console when the app starts
print("✅ Tasks Created: Swarm is now dynamic across industries and services.")
