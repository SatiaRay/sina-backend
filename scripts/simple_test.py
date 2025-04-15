import requests

def simple_test():
    # آدرس API
    url = "http://localhost:8001/askme"
    
    # ارسال یک سوال ساده
    response = requests.post(
        url,
        json={"question": "هوش مصنوعی چیست؟"},
        headers={"Content-Type": "application/json"}
    )
    
    # چاپ پاسخ
    if response.status_code == 200:
        data = response.json()
        print("پاسخ:")
        print(data["answer"])
        print("\nمنابع:")
        for source in data["sources"]:
            print(f"- {source['metadata']}")
    else:
        print(f"خطا: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    simple_test() 