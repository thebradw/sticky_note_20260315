# test_api.py - Fixed syntax
import os
from dotenv import load_dotenv
import anthropic

# Load environment variables
load_dotenv()

# Get API key
api_key = os.getenv('ANTHROPIC_API_KEY')

if not api_key:
    print("❌ No API key found! Check your .env file")
    exit()

print("✅ API key loaded successfully")
print(f"Key starts with: {api_key[:20]}...")

# Test connection and find current models
try:
    client = anthropic.Anthropic(api_key=api_key)
    
    # First, let's see what models are available
    print("🔍 Finding available models...")
    
    # Try the newest Claude 4 models first
    possible_models = [
        "claude-sonnet-5",           # Current Sonnet (replaced retired claude-sonnet-4-20250514)
        "claude-opus-4-8",           # Current Opus fallback
        "claude-4-sonnet-20250514",  # RETIRED 2026-06-15 (kept for diagnostics)
        "claude-sonnet-4-20250514",  # RETIRED 2026-06-15 (kept for diagnostics)
        "claude-3-5-sonnet-20241202",  # Recent Claude 3.5
        "claude-3-5-sonnet-latest",   # Generic latest
        "claude-3-sonnet-20240229"   # Fallback
    ]
    
    working_model = None
    
    for model in possible_models:
        try:
            print(f"Testing model: {model}")
            message = client.messages.create(
                model=model,
                max_tokens=20,
                messages=[{
                    "role": "user",
                    "content": "Say 'working!'"
                }]
            )
            
            working_model = model
            print(f"✅ Found working model: {model}")
            print(f"🚀 Claude says: {message.content[0].text}")
            break
            
        except Exception as e:
            print(f"❌ {model} failed: {str(e)[:50]}...")
            continue
    
    if working_model:
        print("✅ API connection working perfectly!")
        print(f"📝 Use this model name: {working_model}")
    else:
        print("❌ No working models found")
        
except Exception as e:
    print("❌ General API connection failed:", e)