#!/usr/bin/env python3
"""
Check available OpenAI models
"""
import os
import openai

async def check_models():
    """Check available models"""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY not set")
        return
    
    try:
        client = openai.AsyncOpenAI(api_key=api_key)
        
        # List available models
        models = await client.models.list()
        
        print("📋 Available OpenAI Models:")
        if models and models.data:
            for model in models.data:
                if "gpt" in model.id:
                    print(f"   ✅ {model.id}")
        else:
            print("   No models found")
        
        # Test specific models
        test_models = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview"]
        
        print("\n🧪 Testing Model Access:")
        for model_name in test_models:
            try:
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": "Hello"}],
                    max_tokens=10
                )
                print(f"   ✅ {model_name} - Accessible")
            except Exception as e:
                print(f"   ❌ {model_name} - {str(e)[:100]}...")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_models()) 