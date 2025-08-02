# AI Agent Services

This folder contains all AI agent related services and utilities for the Appointment Agent application.

## 📁 File Structure

### Core Services
- **`intelligent_agent_service.py`** - Main orchestration service for the AI agent
- **`advanced_ai_agent_service.py`** - NLP engine for intent recognition and entity extraction
- **`knowledge_base_service.py`** - Manages the knowledge base with Q&A pairs

### Parsers & Utilities
- **`custom_qa_parser.py`** - Parser for custom Q&A format (User: Question Agent: Answer)
- **`md_knowledge_parser.py`** - Parser for Markdown Q&A format
- **`load_qa_to_agent.py`** - Script to load Q&A files into the agent
- **`test_load_qa.py`** - Test script for Q&A loading functionality

### Package
- **`__init__.py`** - Makes this directory a Python package with clean imports

## 🚀 Usage

### Import Agent Services
```python
from app.services.agent import IntelligentAgentService, KnowledgeBaseService
```

### Load Q&A into Agent
```python
# From command line
uv run python app/services/agent/load_qa_to_agent.py

# From code
from app.services.agent.knowledge_base_service import KnowledgeBaseService
kb = KnowledgeBaseService(db)
kb.load_knowledge_from_custom_qa('q&a_for_agent.md')
```

### Test Agent Functionality
```python
# Test Q&A loading
uv run python app/services/agent/test_load_qa.py
```

## 📊 Current Knowledge Base

- **Total Q&A Pairs**: 153
- **Categories**: 40
- **Coverage**: Comprehensive scheduling scenarios
- **Formats Supported**: Custom Q&A, Markdown, JSON, CSV

## 🔧 Features

- **Intent Recognition**: Understands scheduling, cancellation, availability, etc.
- **Keyword Extraction**: Automatically extracts relevant keywords
- **Contextual Responses**: Provides accurate answers based on knowledge base
- **Multi-Format Support**: Handles various Q&A input formats
- **LLM Integration**: Optional OpenAI integration for enhanced responses

## 📝 Supported Q&A Formats

### Custom Format (User's Format)
```
Category Header
User: Question Agent: Answer
User: Another question Agent: Another answer
```

### Markdown Format
```markdown
### Category
Q: Question? A: Answer
**Q:** Question? **A:** Answer
## Question? Answer
```

## 🎯 Agent Capabilities

- Schedule meetings and appointments
- Check availability and free slots
- Reschedule and cancel bookings
- Manage attendees and guests
- Handle booking links and sharing
- Provide calendar integration help
- Answer general scheduling questions
- Handle edge cases and conflicts 