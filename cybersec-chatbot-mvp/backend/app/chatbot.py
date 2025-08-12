# backend/app/chatbot.py
import os
import json
import chromadb
from typing import List, Dict, Optional
import openai
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class CybersecurityChatbot:
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.chroma_client = chromadb.PersistentClient(path=os.getenv("CHROMA_DB_PATH", "./data/chromadb"))
        self.collection_name = "cybersec_content"
        
        # Initialize or get collection
        try:
            self.collection = self.chroma_client.get_collection(name=self.collection_name)
        except:
            self.collection = self.chroma_client.create_collection(name=self.collection_name)
        
        self.conversation_history = []
        
    def load_processed_content(self, content_path: str):
        """Load processed content and add to vector database"""
        if not os.path.exists(content_path):
            print(f"Content file not found: {content_path}")
            return
        
        with open(content_path, 'r', encoding='utf-8') as f:
            processed_content = json.load(f)
        
        # Add each section to the vector database
        documents = []
        embeddings = []
        metadatas = []
        ids = []
        
        for file_data in processed_content:
            for i, section in enumerate(file_data["sections"]):
                if section.get("embedding"):  # Only add sections with embeddings
                    documents.append(section["content"])
                    embeddings.append(section["embedding"])
                    
                    metadata = {
                        "title": file_data["title"],
                        "heading": section["heading"],
                        "platform": file_data["metadata"]["platform"],
                        "difficulty": file_data["metadata"]["difficulty"],
                        "topics": ",".join(file_data["metadata"]["topics"]),
                        "word_count": section["word_count"],
                        "file_path": file_data["file_path"]
                    }
                    metadatas.append(metadata)
                    ids.append(f"{file_data['title'].replace(' ', '_')}_{i}")
        
        # Add to collection in batches
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch_end = min(i + batch_size, len(documents))
            
            self.collection.add(
                documents=documents[i:batch_end],
                embeddings=embeddings[i:batch_end],
                metadatas=metadatas[i:batch_end],
                ids=ids[i:batch_end]
            )
        
        print(f"Loaded {len(documents)} sections into vector database")
    
    def create_embedding(self, text: str) -> List[float]:
        """Create embedding for text using OpenAI"""
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=text[:8000]
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error creating embedding: {e}")
            return []
    
    def search_relevant_content(self, query: str, platform: str = None, n_results: int = 5) -> Dict:
        """Search for relevant content based on user query"""
        query_embedding = self.create_embedding(query)
        
        if not query_embedding:
            return {"documents": [[]], "metadatas": [[]]}
        
        # Build where clause for filtering
        where_clause = {}
        if platform:
            where_clause["platform"] = platform
        
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_clause if where_clause else None
            )
            return results
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
        """Generate a beginner-friendly response using OpenAI"""
        
        # Build context from search results
        context_sections = []
        if context["documents"] and context["documents"][0]:
            for doc, metadata in zip(context["documents"][0], context["metadatas"][0]):
                context_sections.append(f"**{metadata['heading']}** (from {metadata['title']}):\n{doc}")
        
        context_text = "\n\n".join(context_sections[:3])  # Limit to top 3 results
        
        # Get platform-specific context
        platform_context = self.get_platform_context(platform)
        
        # Build conversation history context
        history_context = ""
        if self.conversation_history:
            recent_history = self.conversation_history[-3:]  # Last 3 exchanges
            history_context = "\n".join([
                f"User: {h['user']}\nAssistant: {h['bot'][:200]}..."
                for h in recent_history
            ])
        
        system_prompt = f"""You are CyberMentor, a friendly and knowledgeable cybersecurity tutor designed to help beginners learn cybersecurity concepts.

Your personality:
- Encouraging and supportive
- Enthusiastic about cybersecurity
- Patient with beginners
- Use analogies and real-world examples
- Avoid overwhelming technical jargon

Platform context: {platform_context}

Your teaching approach:
1. Start with a simple, clear explanation
2. Use analogies when helpful (like comparing buffer overflows to overfilling a cup)
3. Connect concepts to real-world cybersecurity incidents
4. Provide practical next steps for learning
5. Encourage hands-on practice

Available knowledge base:
{context_text}

Recent conversation context:
{history_context}

Guidelines:
- Keep responses under 300 words for better readability
- Use bullet points for lists or steps
- Include encouragement and motivation
- If you don't know something, admit it and suggest how to find out
- Always relate concepts back to practical cybersecurity skills"""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.7,
                max_tokens=400
            )
            
            return response.choices[0].message.content
            
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
        
        # Load processed content
        content_path = os.getenv("CONTENT_PATH", "./content/processed") + "/ctf_primer_processed.json"
        chatbot_instance.load_processed_content(content_path)
    
    return chatbot_instance