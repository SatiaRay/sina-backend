import requests
import json

def test_chat():
    url = "http://localhost:8001/askme"
    question = "بیانیه ماموریت ساتیا چیست؟"
    
    response = requests.post(url, json={"question": question})
    result = response.json()
    
    print("سوال:", question)
    print("پاسخ:", result["answer"])
    print("منابع استفاده شده:")
    for doc in result["sources"]:
        print("-", doc["text"][:200], "...")

if __name__ == "__main__":
    test_chat() 