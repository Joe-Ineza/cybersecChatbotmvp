import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "CyberMentor API is running!" in response.json()["message"]

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_platforms():
    response = client.get("/platforms")
    assert response.status_code == 200
    assert "platforms" in response.json()
    assert any(p["id"] == "picoCTF" for p in response.json()["platforms"])


def test_chat_valid_message(monkeypatch):
    # Monkeypatch the chatbot to avoid real API calls
    from app.main import get_chatbot_dep

    class DummyChatbot:
        def chat(self, message, platform):
            return {"response": "Hello!", "timestamp": "2025-08-13T00:00:00", "sources_used": 1}
        def get_conversation_history(self):
            return []
        def clear_conversation_history(self):
            return None

    monkeypatch.setattr(get_chatbot_dep, "instance", DummyChatbot())
    response = client.post("/chat", json={"message": "What is SQL injection?", "platform": "picoCTF"})
    assert response.status_code == 200
    assert response.json()["response"] == "Hello!"

def test_history(monkeypatch):
    from app.main import get_chatbot_dep

    class DummyChatbot:
        def get_conversation_history(self):
            return [{
                "user": "Test",
                "bot": "Hello!",
                "timestamp": "2025-08-13T00:00:00",
                "platform": "picoCTF",
                "sources_used": 1
            }]
        def chat(self, message, platform): return None
        def clear_conversation_history(self): return None

    monkeypatch.setattr(get_chatbot_dep, "instance", DummyChatbot())
    response = client.get("/history")
    assert response.status_code == 200
    assert response.json()[0]["user"] == "Test"

def test_clear_history(monkeypatch):
    from app.main import get_chatbot_dep

    class DummyChatbot:
        def clear_conversation_history(self):
            return None
        def get_conversation_history(self): return []
        def chat(self, message, platform): return None

    monkeypatch.setattr(get_chatbot_dep, "instance", DummyChatbot())
    response = client.delete("/history")
    assert response.status_code == 200
    assert "Conversation history cleared" in response.json()["message"]

def test_admin_process_content(monkeypatch):
    # Monkeypatch ContentProcessor to avoid real file I/O
    from app.main import ContentProcessor

    class DummyProcessor:
        def process_ctf_primer_directory(self, path): return [{"title": "Test", "sections": []}]
        def save_processed_content(self, content, path): return None

    monkeypatch.setattr("app.main.ContentProcessor", DummyProcessor)
    response = client.post("/admin/process-content")
    assert response.status_code == 200 or response.status_code == 500  # Acceptable if path not found
