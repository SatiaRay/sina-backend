import json
import uuid
import os
from typing import Dict, Any, Optional
from redis import Redis
from redis.exceptions import RedisError


class RedisBindingManager:
    """
    Manages service bindings in Redis cache to handle async sub-process issues.
    Each WebSocket connection gets a unique binding token.
    """
    
    def __init__(self):
        self.redis_host = os.getenv('REDIS_HOST', '127.0.0.1')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db = int(os.getenv('REDIS_DB', 0))
        self.binding_ttl = int(os.getenv('BINDING_TTL', 7200))  # Default 2 hours TTL
        self._init_redis()
    
    def _init_redis(self) -> None:
        """Initialize Redis connection"""
        try:
            self.redis = Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True
            )
            # Test connection
            self.redis.ping()
        except RedisError as e:
            print(f"Failed to connect to Redis: {e}")
            self.redis = None
    
    def generate_binding_token(self) -> str:
        """Generate a unique token for this WebSocket session"""
        return f"binding_{uuid.uuid4().hex}"
    
    def store_binding(self, binding_token: str, class_name: str, binding_data: Dict[str, Any]) -> bool:
        """
        Store service binding data in Redis.
        
        Args:
            binding_token: Unique token for this WebSocket session
            class_name: Name of the class to bind
            binding_data: Data needed to instantiate the class
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.redis:
            return False
        
        try:
            cache_key = f"service_binding:{binding_token}:{class_name}"
            self.redis.setex(
                cache_key,
                self.binding_ttl,
                json.dumps(binding_data)
            )
            return True
        except (RedisError, json.JSONEncodeError) as e:
            print(f"Error storing binding for {class_name}: {e}")
            return False
    
    def get_binding(self, binding_token: str, class_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve service binding data from Redis.
        
        Args:
            binding_token: Unique token for this WebSocket session
            class_name: Name of the class to retrieve
            
        Returns:
            Dict containing binding data or None if not found
        """
        if not self.redis:
            return None
        
        try:
            cache_key = f"service_binding:{binding_token}:{class_name}"
            cached_data = self.redis.get(cache_key)
            return json.loads(cached_data) if cached_data else None
        except (RedisError, json.JSONDecodeError) as e:
            print(f"Error retrieving binding for {class_name}: {e}")
            return None
    
    def remove_binding(self, binding_token: str, class_name: str) -> bool:
        """
        Remove a specific binding from Redis.
        
        Args:
            binding_token: Unique token for this WebSocket session
            class_name: Name of the class to remove
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.redis:
            return False
        
        try:
            cache_key = f"service_binding:{binding_token}:{class_name}"
            return bool(self.redis.delete(cache_key))
        except RedisError as e:
            print(f"Error removing binding for {class_name}: {e}")
            return False
    
    def remove_all_bindings(self, binding_token: str) -> bool:
        """
        Remove all bindings for a specific WebSocket session.
        
        Args:
            binding_token: Unique token for this WebSocket session
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.redis:
            return False
        
        try:
            pattern = f"service_binding:{binding_token}:*"
            keys = self.redis.keys(pattern)
            if keys:
                return bool(self.redis.delete(*keys))
            return True
        except RedisError as e:
            print(f"Error removing all bindings for token {binding_token}: {e}")
            return False


# Global instance
binding_manager = RedisBindingManager()
