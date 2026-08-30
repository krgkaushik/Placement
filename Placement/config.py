import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key")
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/placement_portal")
