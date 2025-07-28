#!/usr/bin/env python3
"""
Test OpenAI API key
"""
import os
import openai

async def test_api_key():
    """Test OpenAI API key"""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY not set")
        return
    
    print(f"🔑 API Key: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        client = openai.AsyncOpenAI(api_key=api_key)
        
        # Try to list models
        print("\n📋 Trying to list models...")
        try:
            models = await client.models.list()
            print(f"✅ Models API call successful")
            if models and models.data:
                print(f"   Found {len(models.data)} models")
                for model in models.data[:5]:  # Show first 5
                    print(f"   - {model.id}")
            else:
                print("   No models returned")
        except Exception as e:
            print(f"❌ Models API error: {e}")
        
        # Try a simple completion
        print("\n🧪 Trying simple completion...")
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Say hello"}],
                max_tokens=10
            )
            print(f"✅ Completion successful: {response.choices[0].message.content}")
        except Exception as e:
            print(f"❌ Completion error: {e}")
            
            # Try alternative models
            alternative_models = ["gpt-4o-mini", "gpt-4o", "gpt-4", "gpt-3.5-turbo"]
            print("\n🔄 Trying alternative models...")
            for model in alternative_models:
                try:
                    response = await client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": "Say hello"}],
                        max_tokens=10
                    )
                    print(f"✅ {model} works: {response.choices[0].message.content}")
                    break
                except Exception as e:
                    print(f"❌ {model} failed: {str(e)[:100]}...")
        
    except Exception as e:
        print(f"❌ General error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_api_key()) 