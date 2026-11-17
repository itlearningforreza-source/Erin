from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # App
    APP_NAME: str = "ERIN API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    
    # App Environment (from .env)
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_WORKERS: int = 2
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production-min-32-chars")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORD_MIN_LENGTH: int = 12
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_NUMBERS: bool = True
    PASSWORD_REQUIRE_SYMBOLS: bool = True
    
    # Database
    SQLITE_PATH: str = os.path.expanduser("~/.erin/data/erin.db")
    DUCKDB_PATH: str = os.path.expanduser("~/.erin/data/erin_analytics.duckdb")
    PARQUET_DIR: str = os.path.expanduser("~/.erin/data/parquet")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
    ]
    
    # Data Providers
    OPENBB_BASE_URL: str = os.getenv("OPENBB_BASE_URL", "http://localhost:6900")
    OPENBB_API_KEY: str = os.getenv("OPENBB_API_KEY", "")
    YFINANCE_ENABLED: bool = True
    FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")
    ALPHA_VANTAGE_API_KEY: str = os.getenv("ALPHA_VANTAGE_API_KEY", "")
    POLYGON_API_KEY: str = os.getenv("POLYGON_API_KEY", "")
    TWELVE_DATA_API_KEY: str = os.getenv("TWELVE_DATA_API_KEY", "")
    FINNHUB_API_KEY: str = os.getenv("FINNHUB_API_KEY", "")
    IEX_CLOUD_API_KEY: str = os.getenv("IEX_CLOUD_API_KEY", "")
    SEC_EDGAR_USER_AGENT: str = os.getenv("SEC_EDGAR_USER_AGENT", "ERIN/0.1.0 (contact@erin.local)")
    
    # AI/LLM
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
    OPENAI_MAX_TOKENS: int = 4096
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229")
    ANTHROPIC_MAX_TOKENS: int = 4096
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3:8b")
    
    # Embeddings
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    EMBEDDING_DIMENSION: int = 384
    
    # Vector DB
    LANCE_DB_PATH: str = os.path.expanduser("~/.erin/data/lancedb")
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE: str = os.path.expanduser("~/.erin/logs/erin.log")
    
    # Tauri Desktop
    TAURI_DEV_SERVER_URL: str = os.getenv("TAURI_DEV_SERVER_URL", "http://localhost:1420")
    TAURI_DIST_DIR: str = os.getenv("TAURI_DIST_DIR", "../dist")
    
    # Feature Flags
    ENABLE_AI_FEATURES: bool = True
    ENABLE_REALTIME_QUOTES: bool = True
    ENABLE_BACKTESTING: bool = True
    ENABLE_PAPER_TRADING: bool = False
    ENABLE_ADVANCED_CHARTS: bool = True
    
    # Rate Limiting
    RATE_LIMIT_DEFAULT: int = 100
    RATE_LIMIT_BURST: int = 200
    RATE_LIMIT_HEAVY: int = 10
    
    # Resource Limits
    MAX_MEMORY_MB: int = 6000
    MAX_CPU_PERCENT: int = 80
    MAX_CONCURRENT_JOBS: int = 2
    
    # Password Policy
    PASSWORD_MIN_LENGTH: int = 12
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_NUMBERS: bool = True
    PASSWORD_REQUIRE_SYMBOLS: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"

settings = Settings()
