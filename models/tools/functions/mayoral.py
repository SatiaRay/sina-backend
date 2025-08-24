from agents import Runner
import requests
import json
import os
from typing import Dict, Any, Optional
from redis import Redis
from redis.exceptions import RedisError
from models.tools.functions.logging_decorator import FunctionCallLogger
from models.agents.mayoral_subject_selector import MayoralSubjectSelector



# 137 app api tool functions
class Mayoral:
    def __init__(self, bearer_token) -> None:
        self.bearer_token = bearer_token
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
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict]:
        """Make API request to Satia.co endpoints with Redis caching

        Args:
            endpoint: API endpoint path
            method: HTTP method (GET, POST, PUT, DELETE, PATCH, etc.)
            data: Request body data for POST/PUT/PATCH requests
            params: Query parameters for GET requests
        """

        # Create cache key including method and parameters
        cache_data = {"method": method, "data": data, "params": params}
        cache_key = self._get_cache_key(endpoint, cache_data)

        # Try to get from cache first (only for GET requests)
        if method.upper() == "GET":
            cached_data = self._get_from_cache(cache_key)
            if cached_data:
                return cached_data

        base_url = os.getenv("MAYORAL_API_BASE_URL", "https://arak.satia.co")
        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Accept": "application/json",
        }

        # Add Content-Type header for requests with body
        if method.upper() in ["POST", "PUT", "PATCH"] and data:
            headers["Content-Type"] = "application/json"

        print(f"Making {method.upper()} request to {endpoint}")
        print(f"Headers: {headers}")

        try:
            # Use requests.request to support all HTTP methods
            response = requests.request(
                method=method.upper(),
                url=f"{base_url}/{endpoint}",
                json=data if method.upper() in ["POST", "PUT", "PATCH"] else None,
                params=params if method.upper() == "GET" else None,
                headers=headers,
            )
            response.raise_for_status()
            response_data = response.json()

            # Cache the successful response (only for GET requests)
            if method.upper() == "GET":
                self._set_cache(cache_key, response_data)

            return response_data
        except requests.exceptions.RequestException as e:
            print(
                f"Response text: {response.text if 'response' in locals() else 'No response'}"
            )
            print(f"Error making {method.upper()} request to {endpoint}: {e}")
            return None

    @FunctionCallLogger()
    async def submitRequest(
        self, mobile, address, lat, long, subject_id, description: str = None
    ) -> Optional[Dict[str, Any]]:
        data = {
            "mobile": mobile,
            "address": address,
            "description": description,
            "lat": lat,
            "long": long,
            "subject_id": subject_id,
        }

        data = self._make_api_request("api/submit/request", method="POST", data=data)

        return data

    @FunctionCallLogger()
    async def searchSubject(self, q, description) -> Optional[Dict[str, Any]]:
        params = {
            "q": q,
        }

        data = self._make_api_request("api/subject/search", method="GET", params=params)
        
        transformed_data = []
        
        for item in data['results']:
            transformed_item = {
                "subject_id": item['id'],
                "description": item['name'],
            }
            transformed_data.append(transformed_item)
            
        agent = MayoralSubjectSelector()
        
        input = f"""
            User Request:
            {description}
            
            Found relevant subjects:
            {transformed_data}
        """
        
        res = await Runner.run(agent, input)
            
        return json.loads(res.final_output)
