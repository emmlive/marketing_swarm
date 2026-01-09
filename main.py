import os

# 1. Silence telemetry to prevent signal errors in Streamlit
os.environ["OTEL_SDK_DISABLED"] = "true"

from crewai import Crew, Process
import agents 
from tasks import MarketingTasks  # Import the Class, not just the file

# Instantiate the Task Factory
tasks = MarketingTasks()

def create_marketing_crew(city, industry, service, premium, blog):
    """
    Dynamically assembles the Crew based on user inputs.
    This ensures variables like 'premium' and 'blog' are injected into the task descriptions.
    """
    
    # Define Tasks using the factory class and passing variables
    # We pass the specific agent to each task function
    t1 = tasks.research_task(agents.market_analyst, city, industry, service, premium)
    t2 = tasks.creative_task(agents.creative_director, city, industry, service, premium, blog)
    t3 = tasks.review_task(agents.proofreader, city, industry, service)
    t4 = tasks.campaign_task(agents.social_media_manager, city, industry, service, t3) # t3 is context
    t5 = tasks.vision_task(agents.vision_inspector, city, industry, service, [t3, t4]) # t3/t4 are context

    return Crew(
        agents=[
            agents.market_analyst, 
            agents.creative_director, 
            agents.proofreader,
            agents.social_media_manager,
            agents.vision_inspector
        ],
        tasks=[t1, t2, t3, t4, t5],
        process=Process.sequential,
        verbose=True,
        memory=False, 
        cache=True,
        max_rpm=2 
    )

# --- GLOBAL WRAPPER FOR app.py ---
def run_marketing_swarm(inputs):
    """
    This is the function app.py calls.
    It unpacks the inputs and initializes the dynamic crew.
    """
    crew_instance = create_marketing_crew(
        city=inputs.get('city'),
        industry=inputs.get('industry'),
        service=inputs.get('service'),
        premium=inputs.get('premium', True),
        blog=inputs.get('blog', True)
    )
    return crew_instance.kickoff()

# --------------------------------------------

def main():
    """Terminal entry point for manual testing."""
    print("🌬️ BreatheEasy AI: High-Ticket Engine Initialized.")

    # Manual Inputs for Testing
    target_industry = input("Industry: ") or "HVAC"
    target_service = input("Service: ") or "Full System Replacement"
    target_city = input("City: ") or "Naperville, IL"
    is_premium = input("Premium Focus? (y/n): ").lower() == 'y'
    is_blog = input("Include Blog? (y/n): ").lower() == 'y'

    inputs = {
        'city': target_city,
        'industry': target_industry,
        'service': target_service,
        'premium': is_premium,
        'blog': is_blog
    }

    print(f"\n🚀 Launching Swarm for {target_city}...")
    result = run_marketing_swarm(inputs)

    print("\n##############################")
    print("✅ CAMPAIGN COMPLETE!")
    print("##############################")

if __name__ == "__main__":
    main()
