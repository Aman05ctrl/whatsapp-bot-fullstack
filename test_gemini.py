import google.generativeai as genai
import time

genai.configure(api_key="AIzaSyAqpAxLf7nMIIVEGVvMCEd5PK-N77lRzos")

model = genai.GenerativeModel("gemini-2.5-flash-lite")

print("Testing...")

start = time.time()

try:
    response = model.generate_content(
        "Say hello",
        request_options={"timeout": 10}   # 🔥 hang avoid
    )
    
    print("✅", response.text)
    print("Time:", round(time.time() - start, 2), "sec")

except Exception as e:
    print("❌ Error:", e)