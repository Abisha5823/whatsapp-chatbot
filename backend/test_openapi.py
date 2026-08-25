import os
from openai import AsyncOpenAI
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def test_openai():
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = await client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": "Say 'Hello! I am working!' in 5 words."}]
    )
    print(f"✅ Response: {response.choices[0].message.content}")

asyncio.run(test_openai())