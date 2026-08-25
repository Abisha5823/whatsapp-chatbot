import asyncio
from services.rag_service import RAGService

async def test_rag():
    rag = RAGService()
    await rag.initialize()
    
    if rag.vectorstore:
        result = await rag.query("Where is your Madurai branch?")
        print(f"📚 RAG Response: {result}")
    else:
        print("❌ Vectorstore not initialized")

asyncio.run(test_rag())