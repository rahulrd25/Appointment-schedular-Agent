#!/usr/bin/env python3
"""
Custom Q&A Parser for User's Specific Format
Parse Q&A from the user's format: "User: Question Agent: Answer"
"""

import re
import json
from typing import List, Dict, Any

def parse_custom_qa(content: str) -> Dict[str, List[Dict]]:
    """
    Parse Q&A pairs from the user's custom format
    Format: Category headers followed by "User: Question" and "Agent: Answer" on separate lines
    """
    
    knowledge_data = {}
    current_category = "general"
    pending_question = None
    
    # Split content into lines
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Check for category headers (lines without "User:" or "Agent:")
        if not line.startswith('User:') and not line.startswith('Agent:') and ':' not in line:
            # This might be a category header
            if len(line) > 3 and not line.startswith('User') and not line.startswith('Agent'):
                current_category = line.lower().replace(' ', '_').replace('&', 'and').replace(',', '').replace('.', '')
                if current_category not in knowledge_data:
                    knowledge_data[current_category] = []
            continue
        
        # Look for User: Question (single line)
        user_match = re.match(r'User:\s*(.+)', line, re.IGNORECASE)
        if user_match:
            question = user_match.group(1).strip()
            pending_question = question
            continue
        
        # Look for Agent: Answer (single line)
        agent_match = re.match(r'Agent:\s*(.+)', line, re.IGNORECASE)
        if agent_match:
            answer = agent_match.group(1).strip()
            # If we have a pending question, create the Q&A pair
            if pending_question:
                add_qa_pair(knowledge_data, current_category, pending_question, answer)
                pending_question = None
            continue
        
        # Look for User: Question Agent: Answer pattern (same line)
        user_agent_match = re.search(r'User:\s*(.+?)\s*Agent:\s*(.+)', line, re.IGNORECASE)
        if user_agent_match:
            question = user_agent_match.group(1).strip()
            answer = user_agent_match.group(2).strip()
            add_qa_pair(knowledge_data, current_category, question, answer)
            continue
    
    return knowledge_data

def add_qa_pair(knowledge_data: Dict[str, List[Dict]], category: str, question: str, answer: str):
    """Add a Q&A pair to the knowledge base"""
    if category not in knowledge_data:
        knowledge_data[category] = []
    
    # Extract keywords from question and answer
    keywords = extract_keywords(question, answer)
    
    # Determine intent based on keywords
    intent = determine_intent(question, keywords)
    
    qa_item = {
        'question': question,
        'answer': answer,
        'keywords': keywords,
        'intent': intent
    }
    
    knowledge_data[category].append(qa_item)

def extract_keywords(question: str, answer: str) -> List[str]:
    """Extract keywords from question and answer"""
    keywords = []
    
    # Common scheduling keywords
    scheduling_keywords = [
        'schedule', 'book', 'meeting', 'call', 'appointment', 'reserve', 'set up',
        'availability', 'free', 'open', 'time', 'when', 'calendar',
        'reschedule', 'move', 'change', 'postpone', 'cancel', 'delete', 'remove',
        'invite', 'people', 'participants', 'guests', 'team', 'group',
        'confirm', 'proceed', 'block', 'slot'
    ]
    
    # Common time keywords
    time_keywords = [
        'tomorrow', 'today', 'next', 'week', 'month', 'monday', 'tuesday',
        'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
        'morning', 'afternoon', 'evening', 'night', 'am', 'pm',
        'noon', 'lunch', 'hour', 'minute'
    ]
    
    # Common question keywords
    question_keywords = [
        'how', 'what', 'when', 'where', 'why', 'can', 'could', 'would',
        'should', 'help', 'assist', 'guide', 'explain', 'tell', 'show',
        'check', 'see', 'find', 'get'
    ]
    
    # Common action keywords
    action_keywords = [
        'book', 'schedule', 'cancel', 'reschedule', 'move', 'change',
        'add', 'remove', 'invite', 'connect', 'sync', 'share',
        'confirm', 'proceed', 'update', 'notify'
    ]
    
    all_keywords = scheduling_keywords + time_keywords + question_keywords + action_keywords
    
    # Extract keywords from question and answer
    text_lower = (question + " " + answer).lower()
    
    for keyword in all_keywords:
        if keyword in text_lower:
            keywords.append(keyword)
    
    return keywords

def determine_intent(question: str, keywords: List[str]) -> str:
    """Determine intent based on question and keywords"""
    question_lower = question.lower()
    
    # Intent mapping based on keywords and question content
    if any(word in question_lower for word in ['schedule', 'book', 'create', 'set up', 'block']):
        return 'schedule_meeting'
    elif any(word in question_lower for word in ['availability', 'free', 'open', 'when', 'show', 'check']):
        return 'check_availability'
    elif any(word in question_lower for word in ['reschedule', 'move', 'change', 'postpone', 'push']):
        return 'reschedule'
    elif any(word in question_lower for word in ['cancel', 'delete', 'remove']):
        return 'cancel'
    elif any(word in question_lower for word in ['connect', 'google calendar', 'microsoft', 'sync']):
        return 'settings'
    elif any(word in question_lower for word in ['invite', 'add', 'remove', 'attendee', 'guest']):
        return 'attendee_management'
    elif any(word in question_lower for word in ['remind', 'notification', 'confirm']):
        return 'reminders'
    elif any(word in question_lower for word in ['link', 'share', 'public']):
        return 'booking_links'
    elif any(word in question_lower for word in ['how', 'what', 'why', 'help', 'tips']):
        return 'general_query'
    else:
        return 'general_query'

def save_to_json(knowledge_data: Dict[str, List[Dict]], output_file: str):
    """Save knowledge data to JSON file"""
    with open(output_file, 'w', encoding='utf-8') as file:
        json.dump(knowledge_data, file, indent=2, ensure_ascii=False)
    print(f"✅ Saved knowledge base to {output_file}")

def save_to_csv(knowledge_data: Dict[str, List[Dict]], output_file: str):
    """Save knowledge data to CSV file"""
    import csv
    
    with open(output_file, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['category', 'question', 'answer', 'keywords', 'intent'])
        
        for category, qa_list in knowledge_data.items():
            for qa in qa_list:
                keywords_str = ','.join(qa.get('keywords', []))
                writer.writerow([
                    category,
                    qa['question'],
                    qa['answer'],
                    keywords_str,
                    qa['intent']
                ])
    print(f"✅ Saved knowledge base to {output_file}")

def print_stats(knowledge_data: Dict[str, List[Dict]]):
    """Print statistics about parsed knowledge"""
    total_qa = sum(len(qa_list) for qa_list in knowledge_data.values())
    categories = list(knowledge_data.keys())
    
    print(f"\n📊 Parsed Knowledge Base Statistics:")
    print(f"Total Q&A pairs: {total_qa}")
    print(f"Categories: {', '.join(categories)}")
    print(f"Category breakdown:")
    for category, qa_list in knowledge_data.items():
        print(f"  - {category}: {len(qa_list)} Q&A pairs")

def main():
    """Main function to demonstrate usage"""
    print("📝 Custom Q&A Parser for User's Format")
    print("=" * 50)
    
    print("\n📋 Supported format:")
    print("Category Header")
    print("User: Question Agent: Answer")
    print("User: Another question Agent: Another answer")
    
    print("\n📖 Example format:")
    print("""
Booking, Scheduling, and Rescheduling
User: Book a meeting with John tomorrow at 10 AM. Agent: Sure, booking a meeting with John for tomorrow at 10 AM. Confirm?

User: Please set up a 2 PM client call for Friday. Agent: Booking a client call this Friday at 2 PM. Should I proceed?
    """)
    
    print("\n🚀 To use your Q&A file:")
    print("1. Your file is already in the correct format")
    print("2. Use the custom parser to convert to JSON/CSV")
    print("3. Load into your AI agent's knowledge base")
    
    print("\n💡 Features:")
    print("- Automatically detects categories from headers")
    print("- Extracts keywords from questions and answers")
    print("- Determines intent for better matching")
    print("- Handles your specific User/Agent format")

if __name__ == "__main__":
    main() 