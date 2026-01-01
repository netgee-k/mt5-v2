import os
from pathlib import Path
from decouple import config
from datetime import timedelta

BASE_DIR = Path(__file__).parent.parent

class Settings:
    # App
    APP_NAME = "MT5 Trading Journal"
    VERSION = "2.0.0"
    SECRET_KEY = config("SECRET_KEY", default="your-secret-key-here-change-in-production")
    
    # Database
    DATABASE_URL = config("DATABASE_URL", default=f"sqlite:///{BASE_DIR}/trading_journal.db")
    
    # Email
    SMTP_HOST = config("SMTP_HOST", default="smtp.gmail.com")
    SMTP_PORT = config("SMTP_PORT", default=587)
    SMTP_USER = config("SMTP_USER", default="")
    SMTP_PASSWORD = config("SMTP_PASSWORD", default="")
    EMAILS_FROM_EMAIL = config("EMAILS_FROM_EMAIL", default="noreply@tradingjournal.com")
    EMAILS_FROM_NAME = config("EMAILS_FROM_NAME", default="MT5 Trading Journal")
    
    # JWT
    ACCESS_TOKEN_EXPIRE_MINUTES = config("ACCESS_TOKEN_EXPIRE_MINUTES", default=30, cast=int)
    REFRESH_TOKEN_EXPIRE_MINUTES = config("REFRESH_TOKEN_EXPIRE_MINUTES", default=60*24*7, cast=int)  # 7 days
    
    # Verification
    VERIFICATION_TOKEN_EXPIRE_HOURS = config("VERIFICATION_TOKEN_EXPIRE_HOURS", default=24, cast=int)
    
    # MT5
    MT5_SERVER = config("MT5_SERVER", default="")
    MT5_LOGIN = config("MT5_LOGIN", default="")
    MT5_PASSWORD = config("MT5_PASSWORD", default="")
    
    # Admin
    ADMIN_EMAIL = config("ADMIN_EMAIL", default="admin@tradingjournal.com")
    ADMIN_PASSWORD = config("ADMIN_PASSWORD", default="admin123")
   #auth 
    ARGON2_TIME_COST = 2           # Lower for dev, 3-4 for production
    ARGON2_MEMORY_COST = 102400    # ~100MB, increase for production
    ARGON2_PARALLELISM = 2         # Number of threads
    ARGON2_HASH_LENGTH = 32        # Hash length in bytes
    ARGON2_SALT_LENGTH = 16        # Salt length in bytes

    # Upload
    UPLOAD_DIR = BASE_DIR / "uploads"
    
    @classmethod
    def init_dirs(cls):
        """Create necessary directories"""
        cls.UPLOAD_DIR.mkdir(exist_ok=True)

settings = Settings()