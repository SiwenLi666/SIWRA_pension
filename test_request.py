import requests
import json

def test_chat():
    url = "http://localhost:9090/chat"
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "message": "svara på svenska: kan du sammanfatta all information som har med pension att göra?"
    }
    
    response = requests.post(url, headers=headers, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

if __name__ == "__main__":
    test_chat()
