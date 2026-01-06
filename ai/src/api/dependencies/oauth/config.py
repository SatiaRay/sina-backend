# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # OAuth Introspection
    OAUTH_INTROSPECTION_URL = os.getenv("OAUTH_INTROSPECTION_URL", "http://sina-idp-service/api/oauth/introspect")
    OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
    OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
    
    # Cache settings
    TOKEN_CACHE_TTL = int(os.getenv("TOKEN_CACHE_TTL", "300"))  # 5 minutes
    TOKEN_CACHE_SIZE = int(os.getenv("TOKEN_CACHE_SIZE", "1000"))

settings = Settings()