import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

from app.chatbot import get_chatbot
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CyberMentor API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://tutorbuddy-qnxu6dz7m-joe-inezas-projects.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class ChatRequest(BaseModel):
    message: str
    platform: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    timestamp: str
    sources_used: int

class ConversationEntry(BaseModel):
    user: str
    bot: str
    timestamp: str
    platform: Optional[str]
    sources_used: int

# Dependency wrapper for chatbot
class ChatbotWrapper:
    def __init__(self):
        self.chatbot = get_chatbot()

    def chat(self, message, platform):
        return self.chatbot.chat(message, platform)

    def get_conversation_history(self):
        return self.chatbot.get_conversation_history()

    def clear_conversation_history(self):
        return self.chatbot.clear_conversation_history()

def get_chatbot_dep():
    # Singleton pattern: store instance on function attribute
    if not hasattr(get_chatbot_dep, "instance"):
        get_chatbot_dep.instance = ChatbotWrapper()
    return get_chatbot_dep.instance

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "CyberMentor API is running!", "version": "1.0.0"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    chatbot_wrapper: ChatbotWrapper = Depends(get_chatbot_dep)
):
    """Main chat endpoint"""
    try:
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        result = chatbot_wrapper.chat(request.message, request.platform)
        return ChatResponse(
            response=result["response"],
            timestamp=result["timestamp"],
            sources_used=result["sources_used"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")

@app.get("/history", response_model=List[ConversationEntry])
async def get_history(
    chatbot_wrapper: ChatbotWrapper = Depends(get_chatbot_dep)
):
    """Get conversation history"""
    try:
        history = chatbot_wrapper.get_conversation_history()
        return [ConversationEntry(**entry) for entry in history]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting history: {str(e)}")

@app.delete("/history")
async def clear_history(
    chatbot_wrapper: ChatbotWrapper = Depends(get_chatbot_dep)
):
    """Clear conversation history"""
    try:
        chatbot_wrapper.clear_conversation_history()
        return {"message": "Conversation history cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing history: {str(e)}")

@app.get("/platforms")
async def get_platforms():
    """Get supported platforms"""
    return {
        "platforms": [
            {"id": "picoCTF", "name": "picoCTF", "description": "Educational CTF platform"},
            {"id": "hackthebox", "name": "Hack The Box", "description": "Penetration testing platform"},
            {"id": "tryhackme", "name": "TryHackMe", "description": "Guided cybersecurity learning"},
            {"id": "general", "name": "General", "description": "General cybersecurity education"}
        ]
    }

@app.get("/health")
async def health_check(
    chatbot_wrapper: ChatbotWrapper = Depends(get_chatbot_dep)
):
    """Health check for monitoring"""
    return {
        "status": "healthy",
        "chatbot_initialized": chatbot_wrapper is not None,
        "version": "1.0.0"
    }


from content_processor import ContentProcessor
@app.post("/admin/process-content")
async def process_content():
    """Admin endpoint to process and embed new content."""
    try:
        processor = ContentProcessor()
        ctf_primer_path = "./content/raw/ctf-primer"
        output_path = "./content/processed/ctf_primer_processed.json"
        if not os.path.exists(ctf_primer_path):
            return {"error": f"CTF primer path not found: {ctf_primer_path}"}
        processed_content = processor.process_ctf_primer_directory(ctf_primer_path)
        processor.save_processed_content(processed_content, output_path)
        return {
            "message": f"Processed {len(processed_content)} files",
            "output_path": output_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing content: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)