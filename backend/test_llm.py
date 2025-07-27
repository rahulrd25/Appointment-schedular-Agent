#!/usr/bin/env python3
"""
Test script for LLM integration
"""
import asyncio
import os
from app.services.llm_provider import LLMService

async def test_openai():
    """Test OpenAI integration"""
    print("🧪 Testing OpenAI GPT-3.5 Turbo...")
    
    try:
        llm = LLMService("openai")
        
        # Test intent analysis
        intent_result = await llm.analyze_intent("What's my availability on Monday?")
        print(f"✅ Intent Analysis: {intent_result}")
        
        # Test response generation
        response = await llm.generate_response(
            "What's my availability on Monday?",
            {"available_slots": ["9:00 AM", "2:00 PM", "4:00 PM"]}
        )
        print(f"✅ Response: {response}")
        
    except Exception as e:
        print(f"❌ OpenAI test failed: {e}")

async def test_claude():
    """Test Claude integration"""
    print("\n🧪 Testing Claude 3 Haiku...")
    
    try:
        llm = LLMService("claude")
        
        # Test intent analysis
        intent_result = await llm.analyze_intent("Schedule a meeting with John tomorrow")
        print(f"✅ Intent Analysis: {intent_result}")
        
        # Test response generation
        response = await llm.generate_response(
            "Schedule a meeting with John tomorrow",
            {"available_slots": ["10:00 AM", "3:00 PM"]}
        )
        print(f"✅ Response: {response}")
        
    except Exception as e:
        print(f"❌ Claude test failed: {e}")

async def test_provider_switching():
    """Test switching between providers"""
    print("\n🔄 Testing provider switching...")
    
    try:
        llm = LLMService("openai")
        print(f"✅ Initial provider: {llm.provider_name}")
        
        llm.switch_provider("claude")
        print(f"✅ Switched to: {llm.provider_name}")
        
        llm.switch_provider("openai")
        print(f"✅ Switched back to: {llm.provider_name}")
        
    except Exception as e:
        print(f"❌ Provider switching test failed: {e}")

async def main():
    """Run all tests"""
    print("🚀 Starting LLM Integration Tests...\n")
    
    # Check environment variables
    print("📋 Environment Check:")
    print(f"   OPENAI_API_KEY: {'✅ Set' if os.getenv('OPENAI_API_KEY') else '❌ Not set'}")
    print(f"   ANTHROPIC_API_KEY: {'✅ Set' if os.getenv('ANTHROPIC_API_KEY') else '❌ Not set'}")
    print(f"   LLM_PROVIDER: {os.getenv('LLM_PROVIDER', 'openai')}")
    print()
    
    # Run tests
    if os.getenv('OPENAI_API_KEY'):
        await test_openai()
    else:
        print("⚠️  Skipping OpenAI test - API key not set")
    
    if os.getenv('ANTHROPIC_API_KEY'):
        await test_claude()
    else:
        print("⚠️  Skipping Claude test - API key not set")
    
    await test_provider_switching()
    
    print("\n🎉 LLM Integration Tests Complete!")

if __name__ == "__main__":
    asyncio.run(main()) 