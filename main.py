import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# Force a fresh read of the .env file
load_dotenv(override=True)

def run_marketing_swarm(inputs):
    """
    Inputs dictionary expects: 
    {'city': str, 'industry': str, 'service': str}
    """
    
    # 1. THE BRAIN: Define the Gemini 2.0 Flash model
    gemini_llm = LLM(
        model="google/gemini-2.0-flash", 
        api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.7
    )

    # 2. THE TOOLS
    search_tool = SerperDevTool(api_key=os.getenv("SERPER_API_KEY"))
    scrape_tool = ScrapeWebsiteTool()

    # 3. THE AGENTS (Your specific team)
    market_analyst = Agent(
        role=f"Senior {inputs['industry']} Market Analyst",
        goal=f"Research the {inputs['service']} market in {inputs['city']}",
        backstory="Expert in local home service markets. You use search and scraping to find facts and competitor gaps.",
        tools=[search_tool, scrape_tool],
        llm=gemini_llm,
        verbose=True,
        allow_delegation=False
    )

    creative_director = Agent(
        role="Lead Creative Strategist",
        goal="Create 3 high-converting Facebook ads based on research",
        backstory="Award-winning ad copywriter specializing in home services. You turn data into emotional hooks.",
        llm=gemini_llm,
        verbose=True,
        allow_delegation=False
    )

    proofreader = Agent(
        role="Senior Marketing Copy Editor",
        goal="Ensure all ad copy is professional, polished, and persuasive.",
        backstory="A meticulous editor who makes AI copy sound human, trustworthy, and brand-aligned.",
        llm=gemini_llm,
        verbose=True,
        allow_delegation=False
    )

    social_media_manager = Agent(
        role="Social Media Campaign Manager",
        goal="Create a 7-day social media posting schedule based on the polished ad copy.",
        backstory="You are a social media expert who knows how to pace content and mix offers with value.",
        llm=gemini_llm,
        verbose=True,
        allow_delegation=False
    )

    vision_inspector = Agent(
        role="Visual Brand & Design Strategist",
        goal="Transform text ads into high-impact visual design concepts and AI image prompts.",
        backstory="You specialize in visual psychology for home services, using trust-building colors and detailed prompts.",
        llm=gemini_llm,
        verbose=True,
        allow_delegation=False
    )

    # 4. THE TASKS
    research_task = Task(
        description=f"Analyze the {inputs['service']} competition and demand in {inputs['city']}. Identify 3 local pain points.",
        agent=market_analyst,
        expected_output="A detailed market research summary with competitor analysis."
    )

    copy_task = Task(
        description="Using the research, write 3 distinct Facebook Ads (Hook, Body, CTA).",
        agent=creative_director,
        expected_output="Three high-converting ad drafts."
    )

    edit_task = Task(
        description="Review the ads for grammar, flow, and high-ticket persuasion. Remove 'AI-sounding' words.",
        agent=proofreader,
        expected_output="Polished, ready-to-publish ad copy."
    )

    calendar_task = Task(
        description="Create a 7-day posting schedule (Day 1-7) using the ads and educational tips.",
        agent=social_media_manager,
        expected_output="A full 7-day social media content calendar."
    )

    visual_task = Task(
        description="For each of the 3 ads, create a detailed AI image generation prompt (DALL-E/Midjourney style).",
        agent=vision_inspector,
        expected_output="A visual identity guide with 3 detailed AI image prompts."
    )

    # 5. THE CREW: Assemble and Execute
    # We use Sequential process so the Proofreader can see the Director's work, etc.
    breatheeasy_crew = Crew(
        agents=[market_analyst, creative_director, proofreader, social_media_manager, vision_inspector],
        tasks=[research_task, copy_task, edit_task, calendar_task, visual_task],
        process=Process.sequential,
        verbose=True
    )

    return breatheeasy_crew.kickoff()

# Confirmation
print("✅ Agents and Tasks defined in main.py: Ready for Swarm Launch.")
