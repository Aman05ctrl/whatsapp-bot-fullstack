"""Diagnostic: shows exactly what fields the CRM /api/crm/leads endpoint returns."""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

backend_url = os.getenv('BACKEND_URL', 'http://127.0.0.1:8000')
email = os.getenv('BOT_CLIENT_EMAIL')
password = os.getenv('BOT_CLIENT_PASSWORD')

# 1. Login (same way main.py does)
print("Logging in...")
login_resp = requests.post(
    f"{backend_url}/api/auth/login",
    json={"email": email, "password": password},
    timeout=10
)
if login_resp.status_code != 200:
    print(f"❌ Login failed: {login_resp.status_code} — {login_resp.text[:200]}")
    raise SystemExit(1)

token = login_resp.json().get("access_token")
print(f"✅ Got token: {token[:20]}...\n")

# 2. Fetch your lead by phone
phone = "918470911526"
print(f"Fetching lead for phone={phone}...")
leads_resp = requests.get(
    f"{backend_url}/api/crm/leads?phone={phone}",
    headers={"Authorization": f"Bearer {token}"},
    timeout=10
)
print(f"Status: {leads_resp.status_code}\n")
print("Response JSON:")
print(json.dumps(leads_resp.json(), indent=2, default=str))