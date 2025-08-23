import requests
import json
import os
from typing import Dict, Any, Optional
from redis import Redis
from redis.exceptions import RedisError
from models.tools.functions.logging_decorator import FunctionCallLogger
import urllib3

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Ayan:
    def __init__(self) -> None:
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
        return f"ayan.arak.ir:{endpoint}:{json.dumps(payload, sort_keys=True)}"

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

        base_url = "https://ayan.arak.ir"
        headers = {}
        try:
            url = f"{base_url}/{endpoint}"
            method = method.upper()
            if method == "POST":
                response = requests.post(url, data=data, headers=headers, verify=False)
            elif method == "GET":
                # For GET, send only non-None values as query params
                params = {k: v for k, v in (data or {}).items() if v is not None}
                response = requests.get(
                    url, params=params, headers=headers, verify=False
                )
            elif method == "DELETE":
                response = requests.delete(
                    url, data=data, headers=headers, verify=False
                )
            elif method == "PUT":
                response = requests.put(url, data=data, headers=headers, verify=False)
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

    @FunctionCallLogger()
    def get_zoning(self, lat: float, lng: float) -> Optional[Dict[str, Any]]:
        resData = self._make_api_request(
            "shahrsazi/SetRegion.php",
            {"Latitude": lng, "Longitude": lat},
            method="GET",
        )

        return resData
    
    @FunctionCallLogger()
    def get_conditions(self) -> Optional[Dict[str, Any]]:
        return {
            "building_conditions" : """
                ###  تعداد طبقات و سطح اشغال مجاز برای اراضی120 مترمربع و بیشتر در مناطق تراکمی مختلف
                | پهنه تراکم زیاد |   |   | پهنه تراکم متوسط |   |   | پهنه تراکم کم |   |   | عرض معبر |
                |-----------------|---|---|------------------|---|---|---------------|---|---|-----------|
                | حداکثرتراکم مجاز (درصد) | حداکثرتعداد طبقات مجاز | حداکثرسطح اشغال مجاز (درصد) | حداکثرتراکم مجاز (درصد) | حداکثرتعداد طبقات مجاز | حداکثرسطح اشغال مجاز (درصد) | حداکثرتراکم مجاز (درصد) | حداکثرتعداد طبقات مجاز | حداکثرسطح اشغال مجاز (درصد) |   |
                | 120 | 2  | 60 | 120 | 2  | 60 | 120 | 2  | 60 | عرض معبر < 8 |
                | 200 | 4  | 50 | 180 | 3  | 60 | 180 | 3  | 60 | 8 ≤ عرض معبر < 12 |
                | 250 | 5  | 50 | 200 | 4  | 50 | 180 | 3  | 60 | 12 ≤ عرض معبر < 24 |
                | 320 | 8** | 40 | 250 | 5  | 50 | 200 | 4  | 50 | 24 ≤ عرض معبر < 36 |
                | 480 | 12** | 40 | 315 | 7* | 45 | 200 | 4  | 50 | عرض معبر ≥ 36 |
                * منوط به رعایت ضوابط مصوب شورایعالی شهرسازی و معماری ایران و رعایت حداقل مساحت زمین

                * منوط به استقرار در پهنه های بلند مرتبه یا محورهای بلند مرتبه (مختلط مقیاس شهر) و رعایت حداقل مساحت زمین
                
                ### تعداد طبقات مجاز برحسب مساحت زمین ، در مناطق تراکمی مختلف
                | تراکم زیاد | تراکم متوسط | تراکم کم | مساحت قطعه / حداکثر تعداد طبقات |
                |------------|-------------|----------|----------------------------------|
                | **حداکثر تعداد طبقات مجاز*** |   |   | حداکثر تعداد طبقات / مساحت قطعه |
                | 1 | 1 | 1 | 50 ≤ مساحت قطعه < 70 |
                | 2 | 2 | 2 | 70 ≤ مساحت قطعه < 120 |
                | 3 | 3 | 3 | 120 ≤ مساحت قطعه < 160 |
                | 4 | 4 | 4 | 160 ≤ مساحت قطعه < 240 |
                | 5 | 5 | 4 | 240 ≤ مساحت قطعه < 300 |
                | 6 | 6 | 4 | 300 ≤ مساحت قطعه < 400 |
                | 8** | 7* | 4 | 400 ≤ مساحت قطعه < 750 |
                | 12** | 7* | 4 | مساحت قطعه ≥ 750 |
                * منوط به رعایت ضوابط مصوب شورایعالی شهرسازی و معماری ایران و رعایت حداقل عرض معبر

                * منوط به استقرار در پهنه های بلند مرتبه یا محورهای بلند مرتبه (مختلط مقیاس شهر) و رعایت حداقل عرض معبر
                
                ### تراکم و سطح اشغال مجاز بر حسب تعداد طبقات در اراضی 120 مترمربع و بیشتر در مناطق تراکمی مختلف
                | تعداد طبقات | سطح اشغال | تراکم |
                |-------------|-----------|-------|
                | 1 طبقه  | 60% | 60%  |
                | 2 طبقه  | 60% | 120% |
                | 3 طبقه  | 60% | 180% |
                | 4 طبقه  | 50% | 200% |
                | 5 طبقه  | 50% | 250% |
                | 6 طبقه  | 45% | 270% |
                | 7 طبقه  | 45% | 315% |
                | 8 طبقه  | 40% | 320% |
                | 9 طبقه  | 40% | 360% |
                | 10 طبقه | 40% | 400% |
                | 11 طبقه | 40% | 440% |
                | 12 طبقه | 40% | 480% |
            """
        }
