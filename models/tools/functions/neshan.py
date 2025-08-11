import requests
import json
import os
from typing import Dict, Any, Optional
from redis import Redis
from redis.exceptions import RedisError


class Neshan:
    def __init__(self, api_key, city_lat, city_long) -> None:
        self.api_key = api_key
        self.city_lat = city_lat
        self.city_long = city_long
        self.redis_host = os.getenv("REDIS_HOST", "127.0.0.1")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.redis_db = int(os.getenv("REDIS_DB", 0))
        self.cache_ttl = int(os.getenv("CACHE_TTL", 3600))  # Default 1 hour TTL
        self._init_redis()

    def _init_redis(self) -> None:
        """Initialize Redis connection"""
        try:
            self.redis = Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True,
            )
            # Test connection
            self.redis.ping()
        except RedisError as e:
            print(f"Failed to connect to Redis: {e}")
            self.redis = None

    def _get_cache_key(self, endpoint: str, payload: Dict[str, Any]) -> str:
        """Generate a unique cache key for the request"""
        return f"neshan.org:{endpoint}:{json.dumps(payload, sort_keys=True)}"

    def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Get data from Redis cache"""
        if not self.redis:
            return None

        try:
            cached_data = self.redis.get(cache_key)
            return json.loads(cached_data) if cached_data else None
        except (RedisError, json.JSONDecodeError) as e:
            print(f"Error reading from cache: {e}")
            return None

    def _set_cache(self, cache_key: str, data: Dict) -> None:
        """Store data in Redis cache"""
        if not self.redis:
            return

        try:
            self.redis.setex(cache_key, self.cache_ttl, json.dumps(data))
        except RedisError as e:
            print(f"Error writing to cache: {e}")

    def _make_api_request(
        self, endpoint: str, data: Dict[str, Any] = None, method: str = "POST"
    ) -> Optional[Dict]:
        """Make API request to Neshan endpoints with Redis caching and dynamic HTTP method"""

        cache_key = self._get_cache_key(endpoint, data)
        # Try to get from cache first
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data

        base_url = "https://api.neshan.org"
        headers = {"Api-Key": self.api_key}
        try:
            url = f"{base_url}/{endpoint}"
            method = method.upper()
            if method == "POST":
                response = requests.post(url, data=data, headers=headers)
            elif method == "GET":
                # For GET, send only non-None values as query params
                params = {k: v for k, v in (data or {}).items() if v is not None}
                response = requests.get(url, params=params, headers=headers)
            elif method == "DELETE":
                response = requests.delete(url, data=data, headers=headers)
            elif method == "PUT":
                response = requests.put(url, data=data, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            response.raise_for_status()
            data = response.json()
            # Cache the successful response
            self._set_cache(cache_key, data)
            return data
        except requests.exceptions.RequestException as e:
            print(f"Response text: {response.text}")
            print(f"Error fetching data from {endpoint}: {e}")
            return None

    def search_address(self, searchTerm: str) -> Optional[Dict[str, Any]]:
        resData = self._make_api_request(
            "v1/search",
            {"term": searchTerm, "lat": self.city_lat, "lng": self.city_long},
            method="GET",
        )

        return resData

    def reverse(self, lat: str, lng) -> Optional[Dict[str, Any]]:
        resData = self._make_api_request(
            "v5/reverse",
            {"lat": lat, "lng": lng},
            method="GET",
        )

        return resData
