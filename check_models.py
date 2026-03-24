import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key from environment
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables. Check your .env file.")

genai.configure(api_key=GOOGLE_API_KEY)

print("=" * 50)
print("CHECKING AVAILABLE GEMINI MODELS")
print("=" * 50)

try:
    models_found = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            models_found.append(m.name)
            print(f"✅ Found: {m.name}")
    
    if not models_found:
        print("⚠️ No models with generateContent support found.")
    else:
        print(f"\n✅ Total models available: {len(models_found)}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("=" * 50)
