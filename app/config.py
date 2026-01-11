# config.py - COMPLETE UPDATED VERSION WITH GOOGLE OAUTH
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
    DEBUG = config("DEBUG", default=True, cast=bool)
    ENVIRONMENT = config("ENVIRONMENT", default="development")
    
    # Database
    DATABASE_URL = config("DATABASE_URL", default=f"sqlite:///{BASE_DIR}/trading_journal.db")
    FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:8000")

    # Email
    SMTP_HOST = config("SMTP_HOST", default="smtp.gmail.com")
    SMTP_PORT = config("SMTP_PORT", default=587)
    SMTP_USER = config("SMTP_USER", default="")
    SMTP_PASSWORD = config("SMTP_PASSWORD", default="")
    EMAILS_FROM_EMAIL = config("EMAILS_FROM_EMAIL", default="noreply@tradingjournal.com")
    EMAILS_FROM_NAME = config("EMAILS_FROM_NAME", default="MT5 Trading Journal")
    
    # JWT
    ACCESS_TOKEN_EXPIRE_MINUTES = config("ACCESS_TOKEN_EXPIRE_MINUTES", default=30, cast=int)
    REFRESH_TOKEN_EXPIRE_MINUTES = config("REFRESH_TOKEN_EXPIRE_MINUTES", default=60*24*7, cast=int)
    
    # Verification
    VERIFICATION_TOKEN_EXPIRE_HOURS = config("VERIFICATION_TOKEN_EXPIRE_HOURS", default=24, cast=int)
    
    # MT5
    MT5_SERVER = config("MT5_SERVER", default="")
    MT5_LOGIN = config("MT5_LOGIN", default="")
    MT5_PASSWORD = config("MT5_PASSWORD", default="")
    
    # Admin
    ADMIN_EMAIL = config("ADMIN_EMAIL", default="admin@tradingjournal.com")
    ADMIN_PASSWORD = config("ADMIN_PASSWORD", default="admin123")
    
    # Auth
    ARGON2_TIME_COST = config("ARGON2_TIME_COST", default=2, cast=int)
    ARGON2_MEMORY_COST = config("ARGON2_MEMORY_COST", default=102400, cast=int)
    ARGON2_PARALLELISM = config("ARGON2_PARALLELISM", default=2, cast=int)
    ARGON2_HASH_LENGTH = config("ARGON2_HASH_LENGTH", default=32, cast=int)
    ARGON2_SALT_LENGTH = config("ARGON2_SALT_LENGTH", default=16, cast=int)
    
    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
    GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET", default="")
    GOOGLE_REDIRECT_URI = config("GOOGLE_REDIRECT_URI", default="http://127.0.0.1:8000/auth/google/callback")
    
    # OAuth URLs (These are standard Google endpoints)
    GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
    
    # OAuth Scopes
    GOOGLE_OAUTH_SCOPES = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile"
    ]
    
    # OAuth Security
    OAUTH_STATE_SECRET = config("OAUTH_STATE_SECRET", default=SECRET_KEY + "-oauth-state")
    
    # Finnhub API (Market Data & News) - USING YOUR .env VALUES
    FINNHUB_API_KEY = config("FINNHUB_API_KEY", default="d5fqc9hr01qie3lejdag")
    FINNHUB_BASE_URL = config("FINNHUB_BASE_URL", default="https://finnhub.io/api/v1")
    
    # OpenAI API (AI Analysis) - USING YOUR .env VALUES
    OPENAI_API_KEY = config("OPENAI_API_KEY", default="")
    OPENAI_MODEL = config("OPENAI_MODEL", default="gpt-3.5-turbo")
    OPENAI_MAX_TOKENS = config("OPENAI_MAX_TOKENS", default=1000, cast=int)
    OPENAI_TEMPERATURE = config("OPENAI_TEMPERATURE", default=0.7, cast=float)
    
    # News & Market Data Configuration
    NEWS_API_KEY = config("FINNHUB_API_KEY", default="d5fqc9hr01qie3lejdag")  # Alias for backward compatibility
    NEWS_FETCH_INTERVAL = config("NEWS_FETCH_INTERVAL", default=300, cast=int)
    NEWS_MAX_ARTICLES = config("NEWS_MAX_ARTICLES", default=20, cast=int)
    NEWS_DEFAULT_SYMBOLS = config("NEWS_DEFAULT_SYMBOLS", default="AAPL,MSFT,GOOGL,TSLA,BTC-USD,ETH-USD,EUR/USD,GBP/USD")
    
    # Rate Limiting
    FINNHUB_RATE_LIMIT_PER_MINUTE = config("FINNHUB_RATE_LIMIT_PER_MINUTE", default=60, cast=int)
    FINNHUB_RATE_LIMIT_BUFFER = config("FINNHUB_RATE_LIMIT_BUFFER", default=5, cast=int)
    
    # Trading Analysis
    PERFORMANCE_SCORE_WEIGHTS = {
        'win_rate': 0.4,
        'profit_factor': 0.3,
        'consistency': 0.3
    }
    
    # Badge thresholds
    BADGE_WIN_RATE_THRESHOLD = config("BADGE_WIN_RATE_THRESHOLD", default=70, cast=int)  # For Best Trader badge
    BADGE_CONSISTENCY_THRESHOLD = config("BADGE_CONSISTENCY_THRESHOLD", default=60, cast=int)
    BADGE_MIN_TRADES = config("BADGE_MIN_TRADES", default=20, cast=int)
    
    # Upload
    UPLOAD_DIR = BASE_DIR / "uploads"
    MAX_UPLOAD_SIZE = config("MAX_UPLOAD_SIZE", default=10, cast=int)  # MB
    
    # Session
    SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=False, cast=bool)
    SESSION_COOKIE_HTTPONLY = config("SESSION_COOKIE_HTTPONLY", default=True, cast=bool)
    SESSION_COOKIE_SAMESITE = config("SESSION_COOKIE_SAMESITE", default="lax")
    
    # CORS
    CORS_ORIGINS = config("CORS_ORIGINS", default="http://localhost:8000,http://localhost:3000").split(",")
    
    # Security
    PASSWORD_MIN_LENGTH = config("PASSWORD_MIN_LENGTH", default=8, cast=int)
    PASSWORD_REQUIRE_SPECIAL = config("PASSWORD_REQUIRE_SPECIAL", default=True, cast=bool)
    PASSWORD_REQUIRE_NUMBER = config("PASSWORD_REQUIRE_NUMBER", default=True, cast=bool)
    PASSWORD_REQUIRE_UPPERCASE = config("PASSWORD_REQUIRE_UPPERCASE", default=True, cast=bool)
    
    @property
    def news_symbols_list(self):
        """Convert comma-separated symbols to list"""
        return [s.strip() for s in self.NEWS_DEFAULT_SYMBOLS.split(",") if s.strip()]
    
    @property
    def is_development(self):
        """Check if running in development environment"""
        return self.ENVIRONMENT.lower() == "development"
    
    @property
    def is_production(self):
        """Check if running in production environment"""
        return self.ENVIRONMENT.lower() == "production"
    
    @property
    def google_oauth_config(self):
        """Return Google OAuth configuration as a dict"""
        return {
            "client_id": self.GOOGLE_CLIENT_ID,
            "client_secret": self.GOOGLE_CLIENT_SECRET,
            "redirect_uri": self.GOOGLE_REDIRECT_URI,
            "authorize_url": self.GOOGLE_AUTHORIZE_URL,
            "token_url": self.GOOGLE_TOKEN_URL,
            "userinfo_url": self.GOOGLE_USERINFO_URL,
            "scopes": self.GOOGLE_OAUTH_SCOPES
        }
    
    @property
    def is_google_oauth_configured(self):
        """Check if Google OAuth is properly configured"""
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)
    
    @classmethod
    def init_dirs(cls):
        """Create necessary directories"""
        cls.UPLOAD_DIR.mkdir(exist_ok=True)
        
        # Create logs directory
        logs_dir = BASE_DIR / "logs"
        logs_dir.mkdir(exist_ok=True)
        
    @classmethod
    def validate_settings(cls):
        """Validate critical settings"""
        errors = []
        warnings = []
        
        # Check if Finnhub API key is set
        if not cls.FINNHUB_API_KEY or cls.FINNHUB_API_KEY == "d5fqc9hr01qie3lejdag":
            errors.append("FINNHUB_API_KEY is not configured properly in .env file")
        
        # Check if database URL is valid
        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL is not configured")
        
        # Check secret key in production
        if cls.is_production and cls.SECRET_KEY == "your-secret-key-here-change-in-production":
            errors.append("SECRET_KEY must be changed in production")
        
        # Check Google OAuth configuration (optional but recommended)
        if cls.is_production and not cls.is_google_oauth_configured:
            warnings.append("Google OAuth is not configured (optional feature)")
        
        if errors:
            raise ValueError(f"Configuration errors: {'; '.join(errors)}")
        
        if warnings:
            print(f"Configuration warnings: {'; '.join(warnings)}")
    
    @classmethod
    def print_config_summary(cls):
        """Print a summary of the current configuration"""
        print("=" * 60)
        print(f"{cls.APP_NAME} v{cls.VERSION} - Configuration Summary")
        print("=" * 60)
        print(f"Environment: {cls.ENVIRONMENT}")
        print(f"Debug Mode: {cls.DEBUG}")
        print(f"Database: {cls.DATABASE_URL}")
        print(f"Finnhub API Key: {'Configured' if cls.FINNHUB_API_KEY and cls.FINNHUB_API_KEY != 'd5fqc9hr01qie3lejdag' else 'Using default/demo'}")
        print(f"OpenAI API Key: {'Configured' if cls.OPENAI_API_KEY else 'Not configured'}")
        print(f"MT5 Server: {'Configured' if cls.MT5_SERVER else 'Not configured'}")
        print(f"Google OAuth: {'Configured' if cls.is_google_oauth_configured else 'Not configured'}")
        print("=" * 60)

# Initialize settings
settings = Settings()

# Create directories on import
settings.init_dirs()

# Validate settings in production
if settings.is_production:
    try:
        settings.validate_settings()
    except ValueError as e:
        print(f"Configuration Error: {e}")
        print("Please fix your .env file before running in production.")
        raise

# Print summary in development
if settings.is_development:
    settings.print_config_summary()