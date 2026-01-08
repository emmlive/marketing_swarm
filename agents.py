import os
import streamlit as st
from crewai import Agent, LLM
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# --- 1. THE BRAIN (SaaS Cloud Optimized) ---
# We use st.secrets directly to bypass os.getenv issues on Streamlit Cloud.
# NOTE: The "gemini/" prefix is mandatory for LiteLLM to route correctly.
gemini_llm = LLM(
    model="gemini/gemini-2.5-flash", 
    api_key=st.secrets["GEMINI_API_KEY"],
    temperature=0.7
)

# --- 2. THE TOOLS ---
# Ensure Serper key is also pulled from Streamlit Secrets
search_tool = SerperDevTool(api_key=st.secrets["SERPER_API_KEY"])
scrape_tool = ScrapeWebsiteTool()

# --- 3. THE ANALYST ---
market_analyst = Agent(
    role="Senior HVAC Market Analyst",
    goal="Research the air duct cleaning market in {city}",
    backstory="Expert in local home service markets. You use search and scraping to find facts.",
    tools=[search_tool, scrape_tool],
    llm=gemini_llm,
    verbose=True,
    allow_delegation=False # Good for performance on Gemini
)

# --- 4. THE DIRECTOR ---
creative_director = Agent(
    role="Lead Creative Strategist",
    goal="Create 3 high-converting Facebook ads based on research",
    backstory="Award-winning ad copywriter specializing in home services.",
    llm=gemini_llm,
    verbose=True
)

# --- 5. THE PROOFREADER ---
proofreader = Agent(
    role="Senior Marketing Copy Editor",
    goal="Ensure all ad copy is professional, polished, and persuasive.",
    backstory="A meticulous editor who makes AI copy sound human and trustworthy.",
    llm=gemini_llm,
    verbose=True
)

# --- 6. THE SOCIAL MEDIA MANAGER ---
social_media_manager = Agent(
    role="Social Media Campaign Manager",
    goal="Create a 7-day social media posting schedule based on the polished ad copy.",
    backstory="Social media expert who mixes direct offers with helpful maintenance tips.",
    llm=gemini_llm,
    verbose=True
)

# --- 7. THE VISION INSPECTOR ---
vision_inspector = Agent(
    role="Visual Brand & Design Strategist",
    goal="Transform text ads into high-impact visual design concepts and AI image prompts.",
    backstory=(
        "You are the guardian of the 'BreatheEasy' visual identity. "
        "MANDATORY BRAND KIT RULES:\n"
        "1. COLOR PALETTE: Prioritize 'Trust Blue' (#0056b3) and 'Clean White'.\n"
        "2. LIGHTING: Bright, airy, natural daylight.\n"
        "3. STYLE: Commercial photography, photorealistic, 8k, highly detailed."
    ),
    llm=gemini_llm,
    verbose=True
)

print("✅ Agents Initialized: Swarm is now brand-aware and running on Gemini 2.5 Flash.")