import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'devworkspace.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Path & Storage Isolations
    STORAGE_ROOT = BASE_DIR / "storage"
    USERS_DIR = STORAGE_ROOT / "Users"
    BACKUP_ROOT = BASE_DIR / "backups"
    EXECUTION_TEMP_DIR = BASE_DIR / "execution_temp"
    
    # Cryptographic Key Setup
    ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")
    
    # Execution Limits
    CODE_EXECUTION_TIMEOUT = int(os.environ.get("CODE_EXECUTION_TIMEOUT", 5)) # seconds
    MAX_OUTPUT_SIZE = 10000 # bytes
    MAX_UPLOAD_SIZE = 16 * 1024 * 1024 # 16 MB

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}