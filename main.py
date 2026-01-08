import os

# 1. Silence telemetry to prevent signal errors in Streamlit
# This MUST be at the very top before crewai imports
os.environ["OTEL_SDK_DISABLED"] = "true"

from crewai import Crew, Process
import agents 
import tasks  

# --- GLOBAL SCOPE: Accessible by app.py ---
# This defines the full 5-agent team for BreatheEasy AI
marketing_crew = Crew(
    agents=[
        agents.market_analyst, 
        agents.creative_director, 
        agents.proofreader,
        agents.social_media_manager,
        agents.vision_inspector
    ],
    tasks=[
        tasks.research_task, 
        tasks.creative_task, 
        tasks.review_task,
        tasks.campaign_task,
        tasks.vision_task
    ],
    process=Process.sequential,
    verbose=True,
    
    # --- STABILIZATION SETTINGS ---
    # memory=False prevents the OpenAI 'insufficient_quota' error (OpenAI Embeddings)
    memory=False, 
    # cache=True allows agents to reuse results if you rerun the same city/service
    cache=True,
    # max_rpm=2 stays within the safe range for Gemini Free Tier
    max_rpm=2 
)
# --------------------------------------------

def main():
    """
    Terminal entry point for manual testing.
    Updated to handle dynamic industry and service variables.
    """
    print("🌬️ Welcome to the BreatheEasy AI Multi-Service Engine!")
    print("✅ Swarm Initialized: Analyst, Director, Editor, Social, & Vision are ready.")

    # Get Dynamic Inputs
    target_industry = input("Enter Industry (e.g., Plumbing, HVAC, Electrical): ") or "HVAC"
    target_service = input("Enter Specific Service (e.g., Drain Cleaning, Air Duct Cleaning): ") or "Air Duct Cleaning"
    target_city = input("Enter Target City (e.g., Naperville, IL): ") or "Naperville, IL"
        
    print(f"\n🚀 Launching Swarm: {target_service} in {target_city} ({target_industry})...\n")

    # UPDATED: Passing the three core variables to the kickoff
    result = marketing_crew.kickoff(inputs={
        'city': target_city,
        'industry': target_industry,
        'service': target_service
    })

    print("\n##############################")
    print("✅ CAMPAIGN COMPLETE!")
    print(f"Marketing assets for {target_service} in {target_city} generated successfully.")
    print("##############################")

if __name__ == "__main__":
    main()