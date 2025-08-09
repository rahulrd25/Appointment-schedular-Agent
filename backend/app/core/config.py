import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "sqlite:///./appointment_agent.db"
    
    # Security - CRITICAL: These must be set in production
    SECRET_KEY: str = "your-secret-key-here"  # Must be overridden in production
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # API
    API_V1_STR: str = "/api/v1"
    
    # App settings
    PROJECT_NAME: str = "Appointment Agent"
    DEBUG: bool = False  # Changed to False for production
    
    # Frontend URL - Must be configured for production
    FRONTEND_URL: str = "http://localhost:8000"
    
    # Google OAuth - Must be configured for production
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    
    # Email settings - Must be configured for production
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    
    # LLM settings - Optional for production
    LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    
    # File upload settings
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5MB
    ALLOWED_IMAGE_TYPES: list = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    
    # Production settings
    ENVIRONMENT: str = "development"  # development, staging, production
    LOG_LEVEL: str = "INFO"
    
    # Security headers
    SECURE_COOKIES: bool = False  # Set to True in production with HTTPS
    SESSION_COOKIE_SECURE: bool = False  # Set to True in production
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "lax"
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Database connection pool settings
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    DB_POOL_TIMEOUT: int = 60
    DB_POOL_RECYCLE: int = 3600
    
    # Security validation
    def validate_security_settings(self):
        """Validate critical security settings"""
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY == "your-secret-key-here":
                raise ValueError("SECRET_KEY must be set in production environment")
            if not self.FRONTEND_URL.startswith("https://"):
                raise ValueError("FRONTEND_URL must use HTTPS in production")
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

# Validate security settings on import
try:
    settings.validate_security_settings()
except ValueError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Security validation failed: {e}")
    if settings.ENVIRONMENT == "production":
        raise
