import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    
    # Security
    SECRET_KEY: str
    
    # Google OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    
    # App settings
    PROJECT_NAME: str = "Appointment Agent"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    
    # Email settings (using Gmail API)
    # SMTP settings removed - using Gmail API only
    # Legacy email fields (kept for backward compatibility but not used)
    email_username: Optional[str] = None
    email_password: Optional[str] = None
    email_host: Optional[str] = None
    email_port: Optional[str] = None
    FRONTEND_URL: str = "http://localhost:8000"
    
    # LLM settings
    LLM_PROVIDER: str = "openai"  # "openai" or "claude"
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Create settings instance
settings = Settings()
