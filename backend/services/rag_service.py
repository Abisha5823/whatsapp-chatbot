import os
from typing import List, Dict, Any, Optional
import logging
from pathlib import Path
import json

# LangChain imports
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from core.config import settings

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self):
        self.vectorstore = None
        self.embeddings = None
        self.pdf_dir = "data/knowledge/"
        self.chunk_size = 1000
        self.chunk_overlap = 200
        
        # Create directory if it doesn't exist
        os.makedirs(self.pdf_dir, exist_ok=True)
    
    async def initialize(self):
        """Initialize RAG with PDF documents"""
        try:
            # Initialize embeddings
            if settings.USE_GEMINI:

                self.embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-2",  # ✅ Available from your list
        google_api_key=settings.GEMINI_API_KEY,
        task_type="retrieval_document"
    )
            else:
                self.embeddings = OpenAIEmbeddings(
                    api_key=settings.OPENAI_API_KEY,
                    model="text-embedding-3-small"
                )
            
            # Load PDFs
            documents = await self.load_documents()
            
            if documents:
                # Split into chunks
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=self.chunk_size,
                    chunk_overlap=self.chunk_overlap,
                    length_function=len,
                    separators=["\n\n", "\n", " ", ""]
                )
                
                chunks = text_splitter.split_documents(documents)
                logger.info(f"Created {len(chunks)} chunks from documents")
                
                # Create vector store
                self.vectorstore = FAISS.from_documents(
                    chunks, 
                    self.embeddings
                )
                logger.info("Vector store initialized successfully")
            else:
                logger.warning("No documents found in knowledge directory")
                # Create empty vectorstore
                self.vectorstore = FAISS.from_documents(
                    [Document(page_content="No documents loaded")],
                    self.embeddings
                )
                
        except Exception as e:
            logger.error(f"RAG initialization error: {str(e)}")
            self.vectorstore = None
    
    async def load_documents(self) -> List[Document]:
        """Load all documents from knowledge directory"""
        documents = []
        
        if not os.path.exists(self.pdf_dir):
            os.makedirs(self.pdf_dir)
            return documents
        
        for filename in os.listdir(self.pdf_dir):
            filepath = os.path.join(self.pdf_dir, filename)
            try:
                if filename.endswith(".pdf"):
                    loader = PyPDFLoader(filepath)
                    docs = loader.load()
                    documents.extend(docs)
                    logger.info(f"Loaded PDF: {filename}")
                elif filename.endswith(".txt"):
                    loader = TextLoader(filepath, encoding='utf-8')
                    docs = loader.load()
                    documents.extend(docs)
                    logger.info(f"Loaded Text: {filename}")
            except Exception as e:
                logger.error(f"Error loading {filename}: {str(e)}")
        
        return documents
    
    async def query(self, query: str, k: int = 3) -> str:
        """Query the RAG system"""
        if not self.vectorstore:
            logger.warning("Vectorstore not initialized")
            return ""
        
        try:
            docs = self.vectorstore.similarity_search(query, k=k)
            context = "\n\n---\n\n".join([
                f"Content {i+1}:\n{doc.page_content}" 
                for i, doc in enumerate(docs)
            ])
            return context
        except Exception as e:
            logger.error(f"RAG query error: {str(e)}")
            return ""
    
    async def query_with_scores(self, query: str, k: int = 3) -> List[Dict]:
        """Query RAG with relevance scores"""
        if not self.vectorstore:
            return []
        
        try:
            docs = self.vectorstore.similarity_search_with_score(query, k=k)
            results = []
            for doc, score in docs:
                results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "relevance_score": float(score)
                })
            return results
        except Exception as e:
            logger.error(f"RAG query with scores error: {str(e)}")
            return []
    
    async def ingest_pdf(self, filepath: str) -> bool:
        """Ingest a new PDF into the vector store"""
        try:
            if not os.path.exists(filepath):
                logger.error(f"File not found: {filepath}")
                return False
            
            loader = PyPDFLoader(filepath)
            docs = loader.load()
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap
            )
            chunks = text_splitter.split_documents(docs)
            
            if self.vectorstore:
                self.vectorstore.add_documents(chunks)
            else:
                self.vectorstore = FAISS.from_documents(chunks, self.embeddings)
            
            logger.info(f"PDF ingested successfully: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"PDF ingestion error: {str(e)}")
            return False
    
    async def save_vectorstore(self, path: str = "vectorstore_index"):
        """Save vectorstore to disk"""
        if self.vectorstore:
            self.vectorstore.save_local(path)
            logger.info(f"Vectorstore saved to {path}")
    
    async def load_vectorstore(self, path: str = "vectorstore_index"):
        """Load vectorstore from disk"""
        try:
            if os.path.exists(path):
                self.vectorstore = FAISS.load_local(
                    path, 
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                logger.info(f"Vectorstore loaded from {path}")
                return True
        except Exception as e:
            logger.error(f"Error loading vectorstore: {str(e)}")
        return False