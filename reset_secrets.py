import os
import streamlit_authenticator as stauth

# 1. Define your new plain-text password
new_password = "admin123" 

# 2. Corrected Hashing syntax for version 0.3.x
hashed_pw = stauth.Hasher.hash(new_password)

# 3. Define the secrets content
secrets_content = f"""
OPENAI_API_KEY = "YOUR_REAL_OPENAI_KEY_HERE"

[credentials]
usernames = {{ admin = {{ email = "admin@email.com", name = "Admin", password = "{hashed_pw}" }} }}

[cookie]
expiry_days = 30
key = "super_secret_cookie_key"
name = "marketing_swarm_cookie"

[preauthorized]
emails = []
"""

# 4. Write it
os.makedirs('.streamlit', exist_ok=True)
with open('.streamlit/secrets.toml', 'w', encoding='utf-8') as f:
    f.write(secrets_content.strip())

print("--- SUCCESS ---")
print(f"Login as 'admin' with password: {new_password}")