from crewai import Task
# Import all agents from your independent agents.py file
from agents import market_analyst, creative_director, proofreader, social_media_manager, vision_inspector

class MarketingTasks:
    # Task 1: Comprehensive Market Analysis
    def research_task(self, agent, city, industry, service, premium):
        premium_focus = (
            f"Focus on high-net-worth neighborhoods in {city}. "
            f"Analyze ROI and value-proposition for premium {industry} equipment and white-glove service standards. "
            "Identify affluent customer expectations for quality over price."
            if premium else 
            "Focus on general market competitors and local pricing trends for standard service demand."
        )
        
        return Task(
            description=(
                f"Research the {service} market within the {industry} industry in {city}. "
                f"1. {premium_focus} "
                f"2. Identify the top 3 local competitors providing {service} and their pricing strategy. "
                f"3. Find common customer complaints in local reviews (arrival times, mess, etc.). "
                f"4. Identify specific local factors in {city} (weather, local regulations, or utility costs) "
                f"that increase demand for {service}."
            ),
            expected_output=(
                f"A detailed report on the {city} {service} market, including a competitor map, "
                "a list of local 'pain points', and 3 specific marketing 'hooks' for the target demographic."
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
                f"Use H2 subheaders, target {city} local keywords, and focus on health, safety, and property value."
            )

        return Task(
            description=(
                f"Using the research provided, create 3 distinct Facebook ad variations for a {service} business in {city}. "
                f"The tone must be {tone}. Maintain high industry standards for {industry}. "
                "Variation 1: Focus on Safety/Peace of Mind. Variation 2: Focus on Professionalism/Transparency. "
                f"Variation 3: Urgent seasonal offer based on {city}'s current conditions. {blog_instruction}"
            ),
            expected_output="3 ready-to-use ad scripts AND a 1,000-word SEO blog (if requested), formatted in Markdown.",
            agent=agent
        )

    # Task 3: Quality Assurance & Proofreading
    def review_task(self, agent, city, industry, service):
        return Task(
            description=(
                f"Review and polish the marketing assets for {service} in {city}. "
                "1. Fix any grammar or spelling errors. 2. Ensure high-ticket professional terminology. "
                f"3. Verify technical accuracy for the {industry} sector. "
                "4. Ensure the content sounds like a local expert, not a generic AI."
            ),
            expected_output="A final, polished version of the marketing strategy and blog in Markdown format.",
            agent=agent,
            output_file="final_marketing_strategy.md"
        )

    # Task 4: 7-Day Social Media Campaign
    def campaign_task(self, agent, city, industry, service, context_task):
        return Task(
            description=(
                f"Using the polished results for {service} in {city}, create a 7-day social media schedule. "
                "Each day must include: 1. Post Text 2. A specific 'BreatheEasy' Visual Concept 3. 3-5 local hashtags."
            ),
            expected_output="A complete 7-day social media calendar formatted as a Markdown table.",
            agent=agent,
            context=[context_task]
        )

    # Task 5: Vision Inspector - AI Prompts (Refined for Multi-Industry Specifics)
    def vision_task(self, agent, city, industry, service, context_tasks):
        # Dynamic equipment/scenario suggestions based on industry
        industry_specific_visuals = {
            "HVAC": "modern heat pumps, technicians maintaining air ducts, happy families enjoying climate-controlled homes",
            "Plumbing": "clean, professional plumbers with advanced leak detection tools, sparkling new water heaters, pristine bathrooms after repiping",
            "Restoration": "before-and-after scenes of restored homes, state-of-the-art dehumidifiers, technicians in protective gear cleaning up damage",
            "Roofing": "drone shots of newly installed roofs, close-ups of durable shingles, technicians safely repairing storm damage",
            "Solar": "sleek solar panels on rooftops, glowing battery storage units, happy homeowners looking at energy monitors",
            "Custom": f"visuals representing cutting-edge {service} in {industry}, highlighting professional service and client satisfaction"
        }
        
        visual_suggestions = industry_specific_visuals.get(industry, industry_specific_visuals["Custom"])

        return Task(
            description=(
                f"Review the total marketing strategy for {service} in {city}. "
                f"Generate 3 distinct DALL-E 3 Image Prompts brand-locked to 'BreatheEasy'. "
                f"MANDATORY: Each prompt MUST start with 'AI Image Prompt: ' and be between 50-80 words. "
                f"Aesthetics: Photorealistic 8k, vibrant natural lighting, cinematic composition. "
                f"Theme: Show clean, professional scenes that convey trust, expertise, and homeowner satisfaction. "
                f"Include specific visuals related to {visual_suggestions}. "
                f"Brand Color: Emphasize 'Trust Blue' (#0056b3) subtly in professional uniforms or equipment."
            ),
            expected_output="A visual strategy guide with 3 consistent, highly detailed, brand-aligned image prompts.",
            agent=agent,
            context=context_tasks
        )

print("✅ Tasks Created: Swarm is now dynamic across all industries and services.")
