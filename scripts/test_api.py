import requests
import json

def test_add_knowledge():
    url = "http://localhost:8001/add_knowledge"
    data = {
        "url": "http://185.143.223.81/%D8%A8%DB%8C%D8%A7%D9%86%DB%8C%D9%87-%D9%85%D8%A7%D9%85%D9%88%D8%B1%DB%8C%D8%AA/"
    }
    
    response = requests.post(url, json=data)
    print("Status Code:", response.status_code)
    print("Response:", response.json())

if __name__ == "__main__":
    test_add_knowledge() 