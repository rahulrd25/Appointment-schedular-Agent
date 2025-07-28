#!/usr/bin/env python3
"""
Simple OpenAI test
"""
import os
import openai

def test_simple():
    """Simple test"""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY not set")
        return
    
    print(f"🔑 API Key: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        client = openai.OpenAI(api_key=api_key)
        
        # Try to get models
        print("\n📋 Getting models...")
        try:
            models = client.models.list()
            print(f"✅ Models API call successful")
            if models and models.data:
                print(f"   Found {len(models.data)} models")
                for model in models.data:
                    print(f"   - {model.id}")
            else:
                print("   No models returned")
        except Exception as e:
            print(f"❌ Models API error: {e}")
        
        # Try a simple completion with different models
        test_models = [
            "gpt-4o-mini",
            "gpt-4o", 
            "gpt-4",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k"
        ]
        
        print("\n🧪 Testing models...")
        for model in test_models:
            try:
                print(f"   Testing {model}...")
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Say hello"}],
                    max_tokens=10
                )
                print(f"   ✅ {model} works: {response.choices[0].message.content}")
                break
            except Exception as e:
                print(f"   ❌ {model} failed: {str(e)[:80]}...")
        
    except Exception as e:
        print(f"❌ General error: {e}")

if __name__ == "__main__":
    test_simple() 