#!/usr/bin/env python3
"""
Load Q&A file into AI Agent's Knowledge Base
This script can be used to load the user's Q&A file into the AI agent
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import get_db
from app.services.agent.knowledge_base_service import KnowledgeBaseService

def load_qa_to_agent(qa_file_path: str = "q&a_for_agent.md"):
    """
    Load Q&A file into AI agent's knowledge base
    
    Args:
        qa_file_path (str): Path to the Q&A file (default: q&a_for_agent.md)
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        print(f"🔄 Loading Q&A file: {qa_file_path}")
        
        # Get database session
        db = next(get_db())
        
        # Initialize knowledge base
        kb = KnowledgeBaseService(db)
        
        # Load Q&A file
        success = kb.load_knowledge_from_custom_qa(qa_file_path)
        
        if success:
            total_qa = sum(len(qa_list) for qa_list in kb.scheduling_qa.values())
            categories = list(kb.scheduling_qa.keys())
            
            print(f"✅ Successfully loaded Q&A file into AI agent!")
            print(f"📊 Total Q&A pairs: {total_qa}")
            print(f"📂 Categories: {len(categories)}")
            print(f"🎯 AI agent now has access to {total_qa} Q&A pairs")
            print(f"💡 The agent can now provide more accurate and contextual responses")
            
            return True
        else:
            print("❌ Failed to load Q&A file")
            return False
            
    except Exception as e:
        print(f"❌ Error loading Q&A file: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function"""
    print("🤖 AI Agent Q&A Loader")
    print("=" * 40)
    
    # Check if Q&A file exists
    qa_file = "q&a_for_agent.md"
    if not os.path.exists(qa_file):
        print(f"❌ Q&A file not found: {qa_file}")
        print("Please make sure the Q&A file exists in the backend directory")
        return False
    
    # Load Q&A into agent
    success = load_qa_to_agent(qa_file)
    
    if success:
        print("\n🚀 Your AI agent is now ready with enhanced knowledge!")
        print("💬 Try asking questions like:")
        print("  - 'How do I schedule a meeting?'")
        print("  - 'Can you help me book a call?'")
        print("  - 'What's my availability this week?'")
        print("  - 'How do I cancel a meeting?'")
    
    return success

if __name__ == "__main__":
    main() 