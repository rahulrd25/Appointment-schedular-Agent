#!/usr/bin/env python3
"""
Environment Setup Helper for Appointment Agent
This script helps you set up the required environment variables for the AI agent.
"""

import os
import sys
from pathlib import Path

def check_env_vars():
    """Check if required environment variables are set"""
    missing_vars = []
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        missing_vars.append("OPENAI_API_KEY")
    
    return missing_vars

def setup_openai_key():
    """Guide user through setting up OpenAI API key"""
    print("\n🔑 Setting up OpenAI API Key")
    print("=" * 50)
    
    print("\nTo use the AI agent with LLM capabilities, you need an OpenAI API key.")
    print("\nSteps to get your API key:")
    print("1. Go to https://platform.openai.com/api-keys")
    print("2. Sign in or create an account")
    print("3. Click 'Create new secret key'")
    print("4. Copy the generated key")
    
    api_key = input("\nEnter your OpenAI API key (or press Enter to skip): ").strip()
    
    if api_key:
        # Create .env file if it doesn't exist
        env_file = Path(".env")
        if not env_file.exists():
            env_file.write_text(f"OPENAI_API_KEY={api_key}\n")
            print(f"✅ Created .env file with your API key")
        else:
            # Check if OPENAI_API_KEY already exists
            content = env_file.read_text()
            if "OPENAI_API_KEY=" in content:
                # Replace existing key
                lines = content.split('\n')
                new_lines = []
                for line in lines:
                    if line.startswith("OPENAI_API_KEY="):
                        new_lines.append(f"OPENAI_API_KEY={api_key}")
                    else:
                        new_lines.append(line)
                env_file.write_text('\n'.join(new_lines))
                print("✅ Updated existing .env file with new API key")
            else:
                # Append new key
                env_file.write_text(content + f"\nOPENAI_API_KEY={api_key}\n")
                print("✅ Added API key to existing .env file")
        
        print("\n🔒 Your API key has been saved to .env file")
        print("⚠️  Make sure .env is in your .gitignore to keep it secure!")
        
        return True
    else:
        print("\n⚠️  Skipping OpenAI API key setup")
        print("   The AI agent will operate in rule-based mode only")
        return False

def main():
    """Main setup function"""
    print("🚀 Appointment Agent Environment Setup")
    print("=" * 50)
    
    # Check current environment
    missing_vars = check_env_vars()
    
    if not missing_vars:
        print("✅ All required environment variables are set!")
        return
    
    print(f"\n❌ Missing environment variables: {', '.join(missing_vars)}")
    
    # Setup OpenAI key if missing
    if "OPENAI_API_KEY" in missing_vars:
        setup_openai_key()
    
    print("\n🎉 Environment setup complete!")
    print("\nTo start the server with the new environment:")
    print("  cd backend")
    print("  source .env  # Load environment variables")
    print("  uv run uvicorn main:app --reload")

if __name__ == "__main__":
    main() 