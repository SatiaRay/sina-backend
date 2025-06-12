import requests
import json
import os
from typing import Dict, Any, Optional
from redis import Redis
from redis.exceptions import RedisError

class AppSatiaCo:
    def __init__(self, access_token: str, customer: str) -> None:
        self.access_token = access_token
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
            "customer": self.customer
        }
        
        # Add any extra parameters
        if extra_params:
            payload = {**payload, **extra_params}
            
        cache_key = self._get_cache_key(endpoint, payload)
        
        # Try to get from cache first
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data
        
        try:
            response = requests.post(f"https://app.satia.co/proxy.php/{endpoint}", data=payload)
            response.raise_for_status()
            data = response.json()
            
            # Cache the successful response
            self._set_cache(cache_key, data)
            return data
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data from {endpoint}: {e}")
            return None

    def get_connection_logs(self, serial: str = "", beginDate: str = '', endDate: str = '', page: int = 1):
        extra_params = {
            "beginDate": beginDate,
            "endDate": endDate,
            "page": page
        }
        
        if serial:
            account = self.find_account(serial, return_original_value=True)
            if account:
                extra_params["customer"] = json.dumps(account)
        
        data = self._make_api_request("ibs/getConnectionLogs", extra_params)
        if not data:
            return None

        services = data['result']['data']['services']
        return {
            'abroad': {
                'label': "اینترنت بین الملل",
                'download': services[0]['IN'],
                'upload': services[0]['OUT'],
                'total': services[0]['IN'] + services[0]['OUT'],
                'discount': services[0]['CREDITUSED'] - (services[0]['IN'] + services[0]['OUT']),
            },
            'local': {
                'label': "اینترنت داخلی",
                'download': services[1]['IN'],
                'upload': services[1]['OUT'],
                'total': services[1]['IN'] + services[1]['OUT'],
                'discount': services[1]['CREDITUSED'] - (services[0]['IN'] + services[0]['OUT']),
            },
            'tv': {
                'label': "تلویزیون اینترنتی",
                'download': services[2]['IN'],
                'upload': services[2]['OUT'],
                'total': services[2]['IN'] + services[2]['OUT'],
                'discount': services[2]['CREDITUSED'] - (services[0]['IN'] + services[0]['OUT']),
            },
            'free': {
                'label': "اینترنت رایگان",
                'download': services[3]['IN'],
                'upload': services[3]['OUT'],
                'total': services[3]['IN'] + services[3]['OUT'],
                'discount': services[3]['CREDITUSED'] - (services[0]['IN'] + services[0]['OUT']),
            },
            'messager': {
                'label': "پیام رسان های داخلی",
                'download': services[4]['IN'],
                'upload': services[4]['OUT'],
                'total': services[4]['IN'] + services[4]['OUT'],
                'discount': services[4]['CREDITUSED'] - (services[0]['IN'] + services[0]['OUT']),
            }
        }

    def get_service_info(self, serial: str = "", beginDate: str = '', endDate: str = ''):
        extra_params = {
            "beginDate": beginDate,
            "endDate": endDate,
        }
        
        if serial:
            account = self.find_account(serial, return_original_value=True)
            if account:
                extra_params["customer"] = json.dumps(account)
        
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
        
    def find_account(self, serial: str, return_original_value = False):
        accounts = self.get_accounts_list()
        if not accounts:
            return None
            
        for account in accounts:
            if str(account["serial"]) == str(serial):
                if(return_original_value):
                    return {
                        "Serial": account["serial"],
                        "Mobile": "",
                        "AdslTel": account["number"],
                        "Name": account["name"],
                        "CustomerType": "W",
                        "SmsCode": "",
                        "UserId": "",
                        "Type": account["type"],
                        "status": [{
                            "Serial": 6,
                            "Name": account["status"],
                            "BranchRef": "1",
                            "pivot": {
                                "CustomerRef": str(account["serial"]),
                                "StatusRef": "6",
                                "Active": "1",
                                "Date": "",
                                "Comment": ""
                            }
                        }]
                    }
                return account
                
        return None
        
    def get_accounts_list(self, beginDate: str = '', endDate: str = ''):
        extra_params = {
            "beginDate": beginDate,
            "endDate": endDate,
        }
        
        data = self._make_api_request("splash", extra_params=extra_params)
        if not data:
            return None

        accounts = data['user']['customers']
        
        output = []
        
        for account in accounts:
            output.append({
                "serial": account['Serial'],
                "number": account['AdslTel'],
                "name": account['Name'],
                "type": account['Type'],
                "status": account['status'][0]['Name']
            })
            
        return output