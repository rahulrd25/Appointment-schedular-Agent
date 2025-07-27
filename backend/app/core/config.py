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
    APP_NAME: str = "Appointment Agent"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    
    # Email settings
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
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

# Debug: Print loaded values (remove this after testing)
print(f"Loaded GOOGLE_REDIRECT_URI: {settings.GOOGLE_REDIRECT_URI}")
