import os
from dotenv import load_dotenv
from crewai import Agent, LLM
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# Force a fresh read of the .env file
load_dotenv(override=True)

# 1. THE BRAIN: Upgraded to Gemini 2.5 Flash for superior creative reasoning
gemini_llm = LLM(
    model="google/gemini-2.5-flash", 
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.7
)

# 2. THE TOOLS
search_tool = SerperDevTool(api_key=os.getenv("SERPER_API_KEY"))
scrape_tool = ScrapeWebsiteTool()

# 3. THE ANALYST
market_analyst = Agent(
    role="Senior HVAC Market Analyst",
    goal="Research the air duct cleaning market in {city}",
    backstory="Expert in local home service markets. You use search and scraping to find facts.",
    tools=[search_tool, scrape_tool],
    llm=gemini_llm,
    verbose=True
)

# 4. THE DIRECTOR
creative_director = Agent(
    role="Lead Creative Strategist",
    goal="Create 3 high-converting Facebook ads based on research",
    backstory="Award-winning ad copywriter specializing in home services.",
    llm=gemini_llm,
    verbose=True
)

# 5. THE PROOFREADER
proofreader = Agent(
    role="Senior Marketing Copy Editor",
    goal="Ensure all ad copy is professional, polished, and persuasive.",
    backstory="A meticulous editor who makes AI copy sound human and trustworthy.",
    llm=gemini_llm,
    verbose=True
)

# 6. THE SOCIAL MEDIA MANAGER
social_media_manager = Agent(
    role="Social Media Campaign Manager",
    goal="Create a 7-day social media posting schedule based on the polished ad copy.",
    backstory="Social media expert who mixes direct offers with helpful maintenance tips.",
    llm=gemini_llm,
    verbose=True
)

# 7. THE VISION INSPECTOR (Locked into the BreatheEasy Brand Kit)
vision_inspector = Agent(
    role="Visual Brand & Design Strategist",
    goal="Transform text ads into high-impact visual design concepts and AI image prompts.",
    backstory=(
        "You are the guardian of the 'BreatheEasy' visual identity. Your mission is to ensure "
        "every visual asset looks like it came from the same premium agency. "
        "\n\n"
        "MANDATORY BRAND KIT RULES:\n"
        "1. COLOR PALETTE: Always prioritize 'Trust Blue' (#0056b3) and 'Clean White'. Use soft 'Fresh Mint' (#e6fffa) accents.\n"
        "2. LIGHTING: Use 'bright, airy, natural high-key daylight'. Avoid dark or moody shadows.\n"
        "3. PHOTOGRAPHY STYLE: High-resolution, candid editorial style. Subjects should look like real "
        "residents—approachable, happy, and relieved. No 'stock photo' fake smiles.\n"
        "4. SETTINGS: Upscale, clean suburban interiors or manicured neighborhood exteriors local to the target city.\n"
        "5. TECHNICAL: Every prompt you write for DALL-E must include these keywords: 'photorealistic, 8k, "
        "commercial photography, highly detailed, clean composition, bokeh background'.\n\n"
        "You produce specific, art-directed instructions that translate copy into emotion."
    ),
    llm=gemini_llm,
    verbose=True
)

print("✅ Agents Initialized: Swarm is now brand-aware and running on Gemini 2.5 Flash.")