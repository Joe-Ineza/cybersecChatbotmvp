import os
import json
from typing import List, Dict, Optional
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
from datetime import datetime
from dotenv import load_dotenv

# Qdrant imports
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

load_dotenv()

class CybersecurityChatbot:
    def __init__(self):
        self.model_name = os.getenv("LLAMA_MODEL", "meta-llama/Llama-2-7b-chat-hf")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForCausalLM.from_pretrained(self.model_name)
        self.qdrant_client = QdrantClient(host=os.getenv("QDRANT_HOST", "localhost"), port=int(os.getenv("QDRANT_PORT", 6333)))
        self.collection_name = "cybersec_content"
        self.qdrant_client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=qdrant_models.VectorParams(size=1536, distance=qdrant_models.Distance.COSINE)
        )
        self.conversation_history = []
        
    def load_processed_content(self, content_path: str):
        """Load processed content and add to Qdrant vector database"""
        if not os.path.exists(content_path):
            print(f"Content file not found: {content_path}")
            return

        with open(content_path, 'r', encoding='utf-8') as f:
            processed_content = json.load(f)

        points = []
        idx = 0
        for file_data in processed_content:
            for i, section in enumerate(file_data["sections"]):
                if section.get("embedding"):
                    payload = {
                        "title": file_data["title"],
                        "heading": section["heading"],
                        "platform": file_data["metadata"]["platform"],
                        "difficulty": file_data["metadata"]["difficulty"],
                        "topics": file_data["metadata"]["topics"],
                        "word_count": section["word_count"],
                        "file_path": file_data["file_path"]
                    }
                    points.append(qdrant_models.PointStruct(
                        id=f"{file_data['title'].replace(' ', '_')}_{i}",
                        vector=section["embedding"],
                        payload=payload
                    ))
                    idx += 1

        # Upsert in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=points[i:i+batch_size]
            )

        print(f"Loaded {len(points)} sections into Qdrant vector database")

    def create_embedding(self, text: str) -> List[float]:
        """Create embedding for text using a placeholder (Llama does not provide embeddings natively)."""
        print("Warning: Llama does not provide embeddings. Consider using sentence-transformers for embeddings.")
        return [0.0] * 1536
    
    def search_relevant_content(self, query: str, platform: str = None, n_results: int = 5) -> Dict:
        """Search for relevant content based on user query using Qdrant"""
        query_embedding = self.create_embedding(query)
        if not query_embedding:
            return {"documents": [[]], "metadatas": [[]]}

        # Build filter for platform
        filters = None
        if platform:
            filters = qdrant_models.Filter(
                must=[qdrant_models.FieldCondition(
                    key="platform",
                    match=qdrant_models.MatchValue(value=platform)
                )]
            )

        try:
            results = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=n_results,
                with_payload=True,
                filter=filters
            )
            documents = [[hit.payload.get("heading", "") + "\n" + hit.payload.get("title", "") + "\n" + hit.payload.get("file_path", "") for hit in results]]
            metadatas = [[hit.payload for hit in results]]
            return {"documents": documents, "metadatas": metadatas}
        except Exception as e:
            print(f"Error searching content: {e}")
            return {"documents": [[]], "metadatas": [[]]}
    
    def get_platform_context(self, platform: str) -> str:
        """Get platform-specific context"""
        platform_contexts = {
            "picoCTF": "Focus on CTF competition format, educational challenges, and step-by-step problem solving. Emphasize learning fundamentals.",
            "hackthebox": "Emphasize penetration testing methodology, realistic attack scenarios, and professional red team techniques.",
            "tryhackme": "Highlight guided learning paths, structured rooms, and hands-on practice with clear objectives.",
            "general": "Provide general cybersecurity education applicable across different learning platforms and contexts."
        }
        return platform_contexts.get(platform, platform_contexts["general"])
    
    def generate_response(self, query: str, context: Dict, platform: str = None) -> str:
        """Generate a beginner-friendly response using Llama via Hugging Face Transformers"""
        # Build context from search results
        context_sections = []
        if context["documents"] and context["documents"][0]:
            for doc, metadata in zip(context["documents"][0], context["metadatas"][0]):
                context_sections.append(f"**{metadata['heading']}** (from {metadata['title']}):\n{doc}")
        context_text = "\n\n".join(context_sections[:3])  # Limit to top 3 results
        platform_context = self.get_platform_context(platform)
        history_context = ""
        if self.conversation_history:
            recent_history = self.conversation_history[-3:]
            history_context = "\n".join([
                f"User: {h['user']}\nAssistant: {h['bot'][:200]}..." for h in recent_history
            ])
        system_prompt = (
            "You are CyberMentor, a friendly and knowledgeable cybersecurity tutor designed to help beginners learn cybersecurity concepts.\n"
            f"Platform context: {platform_context}\n"
            f"Available knowledge base: {context_text}\n"
            f"Recent conversation context: {history_context}\n"
            "Guidelines: Keep responses under 300 words, use bullet points, encourage, admit if you don't know, relate to practical skills."
        )
        prompt = f"{system_prompt}\nUser: {query}"
        try:
            inputs = self.tokenizer(prompt, return_tensors="pt")
            outputs = self.model.generate(**inputs, max_new_tokens=400, temperature=0.7)
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            response = response.replace(prompt, "").strip()
            return response
        except Exception as e:
            print(f"Error generating response: {e}")
            return "I'm having trouble generating a response right now. Please try again in a moment."
    
    def add_real_world_context(self, topic: str) -> Optional[str]:
        """Add real-world context about recent incidents"""
        # Simple keyword-based matching for MVP
        real_world_examples = {
            "sql": "💡 **Real-world impact**: SQL injection was used in major breaches like Equifax (2017) and continues to be a top web vulnerability.",
            "xss": "💡 **Real-world impact**: Cross-site scripting affects 64% of web applications and was used in attacks against Twitter and Facebook.",
            "buffer": "💡 **Real-world impact**: Buffer overflows were behind major vulnerabilities like Heartbleed and many Windows security patches.",
            "crypto": "💡 **Real-world impact**: Weak cryptography led to breaches at Adobe (2013) and continues to expose sensitive data.",
            "steganography": "💡 **Real-world impact**: Steganography has been used by cybercriminals to hide malware and by nation-state actors for covert communication.",
            "network": "💡 **Real-world impact**: Network attacks like man-in-the-middle were used in major corporate espionage cases."
        }
        
        topic_lower = topic.lower()
        for keyword, example in real_world_examples.items():
            if keyword in topic_lower:
                return example
        
        return None
    
    def chat(self, user_message: str, platform: str = None) -> Dict:
        """Main chat function"""
        # Search for relevant content
        relevant_content = self.search_relevant_content(user_message, platform)
        
        # Generate response
        response = self.generate_response(user_message, relevant_content, platform)
        
        # Add real-world context if available
        real_world_context = self.add_real_world_context(user_message)
        if real_world_context:
            response += f"\n\n{real_world_context}"
        
        # Store conversation
        conversation_entry = {
            "user": user_message,
            "bot": response,
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "sources_used": len(relevant_content["documents"][0]) if relevant_content["documents"] else 0
        }
        
        self.conversation_history.append(conversation_entry)
        
        return {
            "response": response,
            "timestamp": conversation_entry["timestamp"],
            "sources_used": conversation_entry["sources_used"]
        }
    
    def get_conversation_history(self) -> List[Dict]:
        """Get conversation history"""
        return self.conversation_history
    
    def clear_conversation_history(self):
        """Clear conversation history"""
        self.conversation_history = []

# Initialize chatbot (singleton pattern for MVP)
chatbot_instance = None

def get_chatbot():
    """Get or create chatbot instance"""
    global chatbot_instance
    if chatbot_instance is None:
        chatbot_instance = CybersecurityChatbot()
        content_path = os.getenv("CONTENT_PATH", "./content/processed") + "/ctf_primer_processed.json"
        chatbot_instance.load_processed_content(content_path)
    return chatbot_instance