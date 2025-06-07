import requests

class AppSatiaCo:
    def __init__(self, access_token: str, customer: str) -> None:
        self.access_token = access_token
        self.customer = customer

    def get_connection_logs(self, beginDate: str = '', endDate: str = '', page: int = 1):
        url = "https://app.satia.co/proxy.php/ibs/getConnectionLogs"
        payload = {
            "token": self.access_token,
            "customer": self.customer,
            "beginDate": beginDate,
            "endDate": endDate,
            "page": page
        }
        try:
            response = requests.post(url, data=payload)
            response.raise_for_status() # Raise an exception for bad status codes
            data = response.json()['result']['data']['credit'] # Assuming the response is JSON
            return {
                "month" : data[0]['MONTH'],
                "download" : data[0]['IN'],
                "upload" : data[0]['OUT']
            }
        except requests.exceptions.RequestException as e:
            print(f"Error fetching connection logs: {e}")
            return None # Or return an empty dictionary, depending on desired behavior