import requests
import json
import os
import base64
from typing import Dict, Any, Optional
from redis import Redis
from redis.exceptions import RedisError
from models.tools.functions.logging_decorator import FunctionCallLogger


class AppSatiaCo:
    def __init__(self, token: str, customer: str) -> None:
        self.access_token = token
        # Decode base64 customer data
        try:
            decoded_customer = base64.b64decode(customer).decode('utf-8')
            self.customer = json.loads(decoded_customer)
        except (base64.binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"Error decoding customer data: {e}")
            # Fallback to original customer string if decoding fails
            self.customer = customer
        self.redis_host = os.getenv('REDIS_HOST', '127.0.0.1')
        self.redis_port = int(os.getenv('REDIS_PORT', 6379))
        self.redis_db = int(os.getenv('REDIS_DB', 0))
        self.cache_ttl = int(os.getenv('CACHE_TTL', 3600))  # Default 1 hour TTL
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

    def _get_cache_key(self, endpoint: str, payload: Dict[str, Any]) -> str:
        """Generate a unique cache key for the request"""
        return f"satia_co:{endpoint}:{json.dumps(payload, sort_keys=True)}"

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
            self.redis.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(data)
            )
        except RedisError as e:
            print(f"Error writing to cache: {e}")

    def _make_api_request(self, endpoint: str, extra_params: Dict[str, Any] = None) -> Optional[Dict]:
        """Make API request to Satia.co endpoints with Redis caching"""
        # Base payload with common parameters
        payload = {
            "token": self.access_token,
            "customer": json.dumps(self.customer) if isinstance(self.customer, dict) else self.customer
        }
        
        # Add any extra parameters
        if extra_params:
            payload = {**payload, **extra_params}
            
        cache_key = self._get_cache_key(endpoint, payload)
        
        # Try to get from cache first
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data
                
        base_url = os.getenv('APP_SATIA_CO_API_BASE_URL', 'https://app.satia.co/proxy.php')

        try:
            response = requests.post(f"{base_url}/{endpoint}", data=payload)
            response.raise_for_status()
            
            # Check if response has content before parsing JSON
            if not response.content:
                print(f"Error fetching data from {endpoint}: Empty response received")
                return None
            
            # Check if response content type is JSON
            content_type = response.headers.get('content-type', '').lower()
            if 'application/json' not in content_type and 'text/json' not in content_type:
                print(f"Error fetching data from {endpoint}: Non-JSON response received. Content-Type: {content_type}")
                print(f"Response content: {response.text[:500]}")  # Log first 500 chars for debugging
                return None

            print(response.text)
            
            # Try to parse JSON
            try:
                data = response.json()
            except json.JSONDecodeError as json_err:
                print(f"Error parsing JSON from {endpoint}: {json_err}")
                print(f"Response content: {response.text[:500]}")  # Log first 500 chars for debugging
                return None
            
            # Cache the successful response
            self._set_cache(cache_key, data)
            return data
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from {endpoint}: {e}")
            return None
        
    @FunctionCallLogger()
    async def get_connection_logs(self, beginDate: str = '', endDate: str = '', page: int = 1):
        extra_params = {
            "beginDate": beginDate,
            "endDate": endDate,
            "page": page
        }
        
        data = self._make_api_request("ibs/getConnectionLogs", extra_params)
        if not data:
            return None

        return data['result']['data']['credit']
        
    @FunctionCallLogger()
    async def get_service_info(self, beginDate: str = '', endDate: str = ''):
        extra_params = {
            "beginDate": beginDate,
            "endDate": endDate,
        }
        
        data = self._make_api_request("splash", extra_params=extra_params)
        if not data:
            return None

        services = data['user']['customer']['services']
        
        if not services:
            return None
        
        return {
            'remaining_days': services[0]['IBSExpire'],
            'label': services[0]['Label'],
            'cridit_gb': services[0]['IBSCredit'],
            'reserved_cridit_gb': services[0]['IBSReserveCredit'],
            'is_active': services[0]['Active']
        }

    @FunctionCallLogger()
    async def get_transaction_logs(self):
        
        data = self._make_api_request("payments/transactions")
        if not data:
            return None

        return data['result']['data']

        
    @FunctionCallLogger()
    async def get_service_history(self):
        
        data = self._make_api_request("services/serviceHistory")
        if not data:
            return None

        return data['result']