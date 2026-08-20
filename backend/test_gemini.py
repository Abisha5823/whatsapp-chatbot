import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ Error: GEMINI_API_KEY not found in .env file")
    exit(1)

print(f"✅ API Key found: {api_key[:10]}...")

try:
    # Configure Gemini
    genai.configure(api_key=api_key)
    
    # List available models
    print("📋 Available models:")
    for model in genai.list_models():
        print(f"  - {model.name}")
    
    # Test with a simple prompt
    print("\n🧪 Testing API with a simple prompt...")
    model = genai.GenerativeModel("gemini-3.6-flash")  # ✅ Latest available # ✅ Changed from gemini-2.0-flash-exp
    response = model.generate_content("Say 'Hello! I am working!' in exactly 10 words.")
    
    print(f"✅ Response: {response.text}")
    print("🎉 Gemini API is working correctly!")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")