# cache.py
import time
from typing import Dict, Optional, Any

class TokenCache:
    """Simple in-memory token cache"""
    
    def __init__(self, max_size: int = 1000):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.max_size = max_size
    
    def get(self, token: str) -> Optional[Dict[str, Any]]:
        """Get token info from cache if not expired"""
        if token in self.cache:
            cached_data = self.cache[token]
            # Check if cache is still valid
            if cached_data["expires_at"] > time.time():
                return cached_data["data"]
            else:
                # Remove expired entry
                del self.cache[token]
        return None
    
    def set(self, token: str, data: Dict[str, Any], ttl: int = 300):
        """Store token info in cache"""
        # If cache is full, remove oldest entry (simple implementation)
        if len(self.cache) >= self.max_size:
            # Remove first key (FIFO-like behavior)
            self.cache.pop(next(iter(self.cache)))
        
        self.cache[token] = {
            "data": data,
            "expires_at": time.time() + ttl
        }
    
    def clear(self):
        """Clear all cache"""
        self.cache.clear()