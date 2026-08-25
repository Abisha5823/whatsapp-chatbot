import os
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def test_openrouter():
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "google/gemini-3.6-flash")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": "Say 'Hello! I am working!' in 5 words."}
                ]
            }
        )
        response.raise_for_status()
        result = response.json()
        print(f"✅ Response: {result['choices'][0]['message']['content']}")

asyncio.run(test_openrouter())