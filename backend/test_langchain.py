#!/usr/bin/env python3
"""
Test LangChain with OpenAI
"""
import os
from langchain_openai import ChatOpenAI

def test_langchain():
    """Test LangChain with OpenAI"""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY not set")
        return
    
    print(f"🔑 API Key: {api_key[:10]}...{api_key[-4:]}")
    
    # Test different models
    test_models = [
        "gpt-4o",
        "gpt-4o-mini", 
        "gpt-4",
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-16k"
    ]
    
    print("\n🧪 Testing LangChain with different models...")
    for model in test_models:
        try:
            print(f"   Testing {model}...")
            llm = ChatOpenAI(
                model=model,
                temperature=0,
                api_key=api_key
            )
            
            # Test a simple completion
            response = llm.invoke("Say hello")
            print(f"   ✅ {model} works: {response.content}")
            break
            
        except Exception as e:
            print(f"   ❌ {model} failed: {str(e)[:80]}...")
    
    # If none work, try to get more info
    print("\n🔍 Checking API access...")
    try:
        # Try to create a client and see what happens
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            api_key=api_key
        )
        
        # Try to get model info
        print("   Trying to get model information...")
        
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    test_langchain() 