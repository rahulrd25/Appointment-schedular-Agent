#!/usr/bin/env python3
"""
List all available models
"""
import os
import openai

def list_all_models():
    """List all available models"""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY not set")
        return
    
    print(f"🔑 API Key: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        client = openai.OpenAI(api_key=api_key)
        
        print("\n📋 Getting all models...")
        try:
            models = client.models.list()
            print(f"✅ Models API call successful")
            if models and models.data:
                print(f"   Found {len(models.data)} models:")
                for model in models.data:
                    print(f"   - {model.id}")
                    if hasattr(model, 'created'):
                        print(f"     Created: {model.created}")
                    if hasattr(model, 'owned_by'):
                        print(f"     Owned by: {model.owned_by}")
                    print()
            else:
                print("   No models returned")
                
                # Try to get more info about the account
                print("\n🔍 Checking account info...")
                try:
                    # Try to get billing info or account info
                    print("   Trying to get account information...")
                except Exception as e:
                    print(f"   Error getting account info: {e}")
                    
        except Exception as e:
            print(f"❌ Models API error: {e}")
            
            # Try different API endpoints
            print("\n🔄 Trying different approaches...")
            
            # Try with different base URL
            try:
                print("   Trying with default endpoint...")
                client2 = openai.OpenAI(api_key=api_key, base_url="https://api.openai.com/v1")
                models2 = client2.models.list()
                print(f"   ✅ Default endpoint works")
            except Exception as e2:
                print(f"   ❌ Default endpoint failed: {e2}")
        
    except Exception as e:
        print(f"❌ General error: {e}")

if __name__ == "__main__":
    list_all_models() 