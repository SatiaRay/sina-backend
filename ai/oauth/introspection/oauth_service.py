# oauth_service.py
import httpx
import asyncio
import time
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from .config import settings
from .cache import TokenCache

class OAuthIntrospectionService:
    """Service to handle OAuth token introspection"""
    
    def __init__(self):
        self.cache = TokenCache(max_size=settings.TOKEN_CACHE_SIZE)
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()
    
    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create a shared HTTP client (connection pooling)"""
        async with self._client_lock:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(10.0),
                    limits=httpx.Limits(
                        max_keepalive_connections=5,
                        max_connections=10
                    )
                )
        return self._client
    
    async def introspect_token(self, token: str) -> Dict[str, Any]:
        """
        Introspect a token using the OAuth introspection endpoint
        Returns token info if valid, raises exception otherwise
        """
        # 1. Check cache first
        cached_result = self.cache.get(token)
        if cached_result:
            return cached_result
        
        # 2. Get HTTP client
        client = await self.get_http_client()
        
        # 3. Prepare introspection request
        request_data = {
            "client_id": settings.OAUTH_CLIENT_ID,
            "client_secret": settings.OAUTH_CLIENT_SECRET,
            "token": token
        }
        
        try:
            # 4. Make the request to IDP
            response = await client.post(
                settings.OAUTH_INTROSPECTION_URL,
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            
            # 5. Check for HTTP errors
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token introspection failed"
                )
            
            # 6. Parse response
            token_info = response.json()
            
            # 7. Check if token is active
            if not token_info.get("active", False):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token is not active"
                )
            
            # 8. Cache the result
            # Calculate TTL based on token expiry
            if "exp" in token_info:
                ttl = int(token_info["exp"] - time.time())
                if ttl > 0:
                    # Cache for remaining token life or max cache TTL
                    cache_ttl = min(ttl, settings.TOKEN_CACHE_TTL)
                    self.cache.set(token, token_info, cache_ttl)
            
            return token_info
            
        except httpx.RequestError:
            # If IDP is unavailable, you might want different handling
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable"
            )
    
    async def cleanup(self):
        """Cleanup resources"""
        if self._client:
            await self._client.aclose()
            self._client = None