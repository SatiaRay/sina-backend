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
            data = response.json()['result']['data'] # Assuming the response is JSON
            services = data['services'];
            return {
                'abroad' : {
                    'label' : "اینترنت بین الملل",
                    'download' : services[0]['IN'],
                    'upload' : services[0]['OUT'],
                    'total' : services[0]['IN'] + services[0]['OUT'],
                    'discount' : services[0]['CREDITUSED'] - (services[0]['IN'] + services[0]['OUT']),
                },
                'local' : {
                    'label' : "اینترنت داخلی",
                    'download' : services[1]['IN'],
                    'upload' : services[1]['OUT'],
                    'total' : services[1]['IN'] + services[1]['OUT'],
                    'discount' : services[1]['CREDITUSED'] - (services[0]['IN'] + services[0]['OUT']),
                },
                'tv' : {
                    'label' : "تلویزیون اینترنتی",
                    'download' : services[2]['IN'],
                    'upload' : services[2]['OUT'],
                    'total' : services[2]['IN'] + services[2]['OUT'],
                    'discount' : services[2]['CREDITUSED'] - (services[0]['IN'] + services[0]['OUT']),
                },
                'free' : {
                    'label' : "اینترنت رایگان",
                    'download' : services[3]['IN'],
                    'upload' : services[3]['OUT'],
                    'total' : services[3]['IN'] + services[3]['OUT'],
                    'discount' : services[3]['CREDITUSED'] - (services[0]['IN'] + services[0]['OUT']),
                },
                'messager' : {
                    'label' : "پیام رسان های داخلی",
                    'download' : services[4]['IN'],
                    'upload' : services[4]['OUT'],
                    'total' : services[4]['IN'] + services[4]['OUT'],
                    'discount' : services[4]['CREDITUSED'] - (services[0]['IN'] + services[0]['OUT']),
                }
            }
        except requests.exceptions.RequestException as e:
            print(f"Error fetching connection logs: {e}")
            return None # Or return an empty dictionary, depending on desired behavior