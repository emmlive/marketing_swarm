import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("GEMINI_API_KEY")

if key:
    print(f"✅ Success! Found API Key starting with: {key[:5]}...")
else:
    print("❌ Error: Could not find GEMINI_API_KEY in .env file.")
