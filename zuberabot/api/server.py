"""
FastAPI Server for Zuberabot.
Exposes the core Agentic features over HTTP REST APIs.
"""

import os
from pathlib import Path
from typing import Dict, Any, List

from fastapi import FastAPI, HTTPException, Body, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from loguru import logger

# Import Core Zuberabot Engine
from zuberabot.agent.loop import AgentLoop
from zuberabot.bus.queue import MessageBus
from zuberabot.providers.openai_provider import OpenAIProvider
from zuberabot.database.postgres import get_db_manager
from zuberabot.ai.retriever import HybridRetriever

# --- Pydantic Models ---
class ChatRequest(BaseModel):
    user_id: str
    message: str
    channel: str = "web"
    session_key: str | None = None

class RAGRequest(BaseModel):
    query: str
    top_k: int = 3

# --- App Setup ---
app = FastAPI(
    title="Zuberabot API",
    description="Agentic Financial Advisor running on FastAPI.",
    version="1.0.0"
)

# Singletons
bus = MessageBus()
db_manager = get_db_manager()

def get_agent_loop() -> AgentLoop:
    """Initialize or reuse the AgentLoop instance."""
    # Assuming .nanobot is the default workspace
    workspace_dir = Path.home() / ".nanobot"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    
    # We define a fast provider for general chat responses over API
    provider = OpenAIProvider(
        api_key=os.getenv("GROQ_API_KEY", "dummy"),
        api_base=os.getenv("GROQ_API_BASE"), # Default will fallback safely using logic in provider
        default_model="groq/llama-3.3-70b-versatile" 
    )

    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace_dir,
        model=provider.default_model,
        max_iterations=10,
    )
    return loop

# --- Routes ---

@app.get("/health")
async def health_check():
    """Simple API healthcheck."""
    db_ok = db_manager.health_check()
    return {"status": "ok", "database_connected": db_ok}

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Direct synchronous chat endpoint utilizing the internal AgentLoop execution engine.
    """
    loop = get_agent_loop()
    
    # Fallback default key structure
    session_key = req.session_key or f"{req.channel}:{req.user_id}"
    
    # Process message synchronously for API
    try:
        logger.info(f"Processing API chat request from {req.user_id}")
        response_text = await loop.process_direct(
            content=req.message,
            session_key=session_key
        )
        
        return {
            "status": "success",
            "user_id": req.user_id,
            "session_key": session_key,
            "response": response_text
        }
    except Exception as e:
        logger.error(f"Chat API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/rag/query")
async def rag_query_endpoint(req: RAGRequest):
    """
    Exposes identical pg_search logic for testing or external queries.
    """
    try:
        with db_manager.get_session() as db_session:
            retriever = HybridRetriever(db_session)
            docs = retriever.retrieve(req.query, top_k=req.top_k)
            
            results = []
            for doc in docs:
                results.append({
                    "id": doc.chunk_id,
                    "content": doc.content,
                    "metadata": doc.metadata
                })
                
            return {
                "status": "success",
                "query": req.query,
                "matches": len(results),
                "results": results
            }
    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
