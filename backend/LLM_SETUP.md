# LLM Setup Guide for AI Agent

## Overview

The AI agent in this application can operate in two modes:
1. **Rule-based mode** (default) - Uses pattern matching and predefined rules
2. **LLM-enhanced mode** - Uses OpenAI's GPT models for more intelligent responses

## Setup

### Option 1: Automatic Setup (Recommended)

Run the setup script to configure your environment:

```bash
cd backend
uv run python setup_env.py
```

This will guide you through getting an OpenAI API key and setting it up.

### Option 2: Manual Setup

1. **Get an OpenAI API Key:**
   - Go to https://platform.openai.com/api-keys
   - Sign in or create an account
   - Click "Create new secret key"
   - Copy the generated key

2. **Set the Environment Variable:**
   
   **Option A: Using .env file (Recommended)**
   ```bash
   cd backend
   echo "OPENAI_API_KEY=your_api_key_here" > .env
   ```
   
   **Option B: Export in terminal**
   ```bash
   export OPENAI_API_KEY=your_api_key_here
   ```

3. **Start the server:**
   ```bash
   uv run uvicorn main:app --reload
   ```

## Troubleshooting

### Error: "OPENAI_API_KEY environment variable is required"

**Issue:** The AI agent is trying to use LLM capabilities but can't find the API key.

**Solution:** 
- Set up the OpenAI API key using the setup script: `uv run python setup_env.py`
- Or manually create a `.env` file with your API key

### Error: "'NoneType' object has no attribute 'provider_name'"

**Issue:** This was a bug in the code that has been fixed. The agent now gracefully handles missing API keys.

**Solution:** Update to the latest code version.

### Agent responses seem basic

**Issue:** The agent is operating in rule-based mode only.

**Solution:** 
- Check that your OpenAI API key is set correctly
- Verify the API key is valid by testing it on OpenAI's platform
- Check the logs for any LLM-related errors

## Testing

Run the test script to verify your setup:

```bash
cd backend
uv run python test_llm_fix.py
```

This will test both scenarios:
- Agent operation without API key (rule-based mode)
- Agent operation with API key (LLM-enhanced mode)

## Security Notes

- Never commit your `.env` file to version control
- The `.env` file is already in `.gitignore`
- Keep your API key secure and rotate it regularly
- Monitor your OpenAI usage to avoid unexpected charges

## Cost Considerations

- OpenAI API usage incurs costs based on token usage
- GPT-4o-mini is used by default (cost-effective option)
- Monitor usage in your OpenAI dashboard
- Consider setting usage limits in your OpenAI account

## Fallback Behavior

If the LLM service is unavailable, the agent will:
- Continue operating in rule-based mode
- Provide helpful responses using pattern matching
- Log warnings about LLM unavailability
- Maintain all core scheduling functionality

This ensures the application remains functional even without LLM capabilities. 