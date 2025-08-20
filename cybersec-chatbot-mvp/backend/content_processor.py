# backend/content_processor.py

import os
import json
import re
from typing import List, Dict, Optional
from pathlib import Path
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

class ContentProcessor:
    def __init__(self):
        self.embedding_model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.embedding_model = SentenceTransformer(self.embedding_model_name)
        
    def process_markdown_file(self, file_path: str) -> Dict:
        """Process a single markdown file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract title (first # heading)
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else Path(file_path).stem
        
        # Split content into sections
        sections = self.split_into_sections(content)
        
        # Extract metadata
        metadata = self.extract_metadata(content, file_path)
        
        return {
            "title": title,
            "file_path": file_path,
            "sections": sections,
            "metadata": metadata,
            "full_content": content
        }

    def split_into_sections(self, content: str) -> List[Dict]:
        """
        Split AsciiDoc content into sections using headings (==, ===, etc.).
        """
        import re
        sections = []
        current_section = ""
        current_heading = None
        lines = content.split('\n')
        for line in lines:
            heading_match = re.match(r'^\s*(==+)\s+(.*)', line)
            if heading_match:
                # Save previous section if it exists
                print(f"Found heading: {heading_match.group(2)}")
                if current_section and current_heading:
                    if current_section.strip():  # Only add non-empty sections
                        sections.append({
                            "heading": current_heading,
                            "content": current_section.strip(),
                            "word_count": len(current_section.split())
                        })
                current_heading = heading_match.group(2).strip()
                current_section = ""
            else:
                current_section += line + '\n'
        # Add the last section
        if current_section and current_heading and current_section.strip():
            sections.append({
                "heading": current_heading,
                "content": current_section.strip(),
                "word_count": len(current_section.split())
            })
        return sections
    def extract_metadata(self, content: str, file_path: str) -> Dict:
        """Extract metadata from content"""
        metadata = {
            "platform": "picoCTF",  # Default for CTF primer
            "difficulty": "beginner",
            "topics": [],
            "examples": []
        }
        
        # Extract topics based on content
        topics_found = []
        topic_keywords = {
            "web_security": ["sql injection", "xss", "csrf", "web", "http", "cookie"],
            "cryptography": ["encryption", "cipher", "crypto", "hash", "rsa", "aes"],
            "reverse_engineering": ["assembly", "disassembly", "binary", "executable"],
            "forensics": ["steganography", "file analysis", "metadata", "recovery"],
            "pwn": ["buffer overflow", "stack", "heap", "memory", "exploit"],
            "networking": ["tcp", "udp", "packet", "wireshark", "network"]
        }
        
        content_lower = content.lower()
        for topic, keywords in topic_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                topics_found.append(topic)
        
        metadata["topics"] = topics_found
        
        # Extract examples (look for code blocks or specific patterns)
        examples = re.findall(r'```[\s\S]*?```', content)
        metadata["examples"] = examples[:3]  # Limit to 3 examples
        
        return metadata
    
    def create_embedding(self, text: str) -> List[float]:
        """Create embedding for text using sentence-transformers locally."""
        try:
            embedding = self.embedding_model.encode(text[:8000], show_progress_bar=False)
            return embedding.tolist()
        except Exception as e:
            print(f"Error creating embedding: {e}")
            return []
    
    def process_ctf_primer_directory(self, primer_path: str) -> List[Dict]:
        """Process all markdown files in CTF primer directory"""
        processed_content = []
        
        # Walk through directory structure
        for root, dirs, files in os.walk(primer_path):
            for file in files:
                if file.endswith('.adoc'):
                    file_path = os.path.join(root, file)
                    print(f"Processing: {file_path}")
                    
                    try:
                        content_data = self.process_markdown_file(file_path)
                        
                        # Create embeddings for each section
                        for section in content_data["sections"]:
                            embedding = self.create_embedding(section["content"])
                            section["embedding"] = embedding
                        
                        processed_content.append(content_data)
                        
                    except Exception as e:
                        print(f"Error processing {file_path}: {e}")
                        continue
        
        return processed_content
    
    def save_processed_content(self, processed_content: List[Dict], output_path: str):
        """Save processed content to JSON file"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(processed_content, f, indent=2, ensure_ascii=False)
        
        print(f"Processed content saved to: {output_path}")

# Usage script
if __name__ == "__main__":
    processor = ContentProcessor()
    
    # Process CTF primer content
    # Replace with your actual CTF primer path
    ctf_primer_path = "./content/raw/ctf-primer"
    
    if os.path.exists(ctf_primer_path):
        processed_content = processor.process_ctf_primer_directory(ctf_primer_path)
        processor.save_processed_content(
            processed_content, 
            "./content/processed/ctf_primer_processed.json"
        )
        print(f"Processed {len(processed_content)} files")
    else:
        print(f"CTF primer path not found: {ctf_primer_path}")
        print("Please clone the CTF primer repository first:")
        print("git clone https://github.com/picoCTF/ctf-primer.git ./content/raw/ctf-primer")