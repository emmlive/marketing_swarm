import os
import streamlit as st
from crewai import Agent, LLM
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# --- 1. THE BRAIN (LiteLLM Optimized for Gemini 2.5 Flash) ---
# We use st.secrets for secure, cloud-ready deployment.
gemini_llm = LLM(
    model="gemini/gemini-2.5-flash", 
    api_key=st.secrets["GEMINI_API_KEY"],
    temperature=0.4, # Lower temperature for better structural accuracy in business strategy
    respect_context_window=True
)

# --- 2. THE TOOLS ---
search_tool = SerperDevTool(api_key=st.secrets["SERPER_API_KEY"])
scrape_tool = ScrapeWebsiteTool()

# --- 3. THE ANALYST (Premium Market Focus) ---
market_analyst = Agent(
    role="Elite Home-Service Market Analyst",
    goal="Identify $10k+ high-ticket service opportunities in {city} for the {industry} industry.",
    backstory=(
        "You are a former McKinsey consultant specializing in affluent residential markets. "
        "You don't just find 'keywords'; you map out wealthy zip codes and identify where "
        "homeowners prioritize system longevity and indoor air quality over the lowest price. "
        "You use your tools to find premium competitors and 'gap' opportunities in {city}."
    ),
    tools=[search_tool, scrape_tool],
    llm=gemini_llm,
    verbose=True,
    allow_delegation=False
)

# --- 4. THE DIRECTOR (Psychological Selling) ---
creative_director = Agent(
    role="Lead High-Ticket Creative Strategist",
    goal="Craft authoritative, investment-focused ad copy that justifies premium pricing for {service}.",
    backstory=(
        "You are an award-winning copywriter who avoids 'discount' language. "
        "Your expertise lies in psychological framing—shifting the customer's mindset from 'cost' to 'investment'. "
        "You focus on health, safety, and 5-star white-glove service to appeal to high-end homeowners."
    ),
    llm=gemini_llm,
    verbose=True
)

# --- 5. THE PROOFREADER (Quality Control) ---
proofreader = Agent(
    role="Senior Editorial Brand Guardian",
    goal="Ensure all marketing assets meet the elite 'BreatheEasy' standard of technical accuracy.",
    backstory=(
        "You are a meticulous editor with a background in technical trade journals. "
        "You strip out AI-sounding 'fluff' and replace it with authoritative, expert-level "
        "insights that make {city} homeowners trust the technical expertise of the business."
    ),
    llm=gemini_llm,
    verbose=True
)

# --- 6. THE SOCIAL MEDIA MANAGER (Trust Architect) ---
social_media_manager = Agent(
    role="High-Value Authority Social Manager",
    goal="Establish the business as the #1 most trusted {industry} expert in {city}.",
    backstory=(
        "You build 'local celebrity' status for home service brands. "
        "Your 7-day campaigns mix educational 'insider tips' with exclusive offers. "
        "You focus on building long-term community trust so the client never has to compete on price again."
    ),
    llm=gemini_llm,
    verbose=True
)

# --- 7. THE VISION INSPECTOR (Luxury Brand Aesthetics) ---
vision_inspector = Agent(
    role="Visual Luxury & Design Strategist",
    goal="Generate photorealistic, brand-locked AI image prompts that reflect a clean, high-end service.",
    backstory=(
        "You are the guardian of the 'BreatheEasy' aesthetic: The Aesthetic of Clean. "
        "MANDATORY BRAND RULES:\n"
        "1. VISUAL STYLE: High-end commercial photography, bright high-key lighting, photorealistic 8k.\n"
        "2. COLOR LOCK: Use 'Trust Blue' (#0056b3) and 'Clean White' as primary visual anchors.\n"
        "3. IMAGERY: Avoid 'gritty' industrial looks. Focus on clean technicians, modern tools, and happy families."
    ),
    llm=gemini_llm,
    verbose=True
)

print("✅ Agents Initialized: Swarm is brand-aware, high-ticket focused, and running on Gemini 2.5 Flash.")
