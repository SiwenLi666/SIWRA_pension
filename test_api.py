"""
Simple script to test the pension advisor API
"""
import requests
import json
import sys
import time

# Set console encoding to UTF-8
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def test_chat_endpoint():
    """Test the /chat endpoint"""
    url = "http://127.0.0.1:9090/chat"
    headers = {"Content-Type": "application/json"}
    
    # Test with a greeting instead of a specific question
    data = {"message": "Hej, jag skulle vilja veta mer om min pension."}
    
    print(f"Sending request to {url}")
    print(f"Request data: {json.dumps(data)}")
    
    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            print("API call successful!")
            print(f"Response: {response.json()}")
            return True
        else:
            print(f"API call failed with status code {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"Error making API call: {str(e)}")
        return False

def test_conversation_flow():
    """Test a multi-turn conversation flow"""
    url = "http://127.0.0.1:9090/chat"
    headers = {"Content-Type": "application/json"}
    
    # Conversation flow
    messages = [
        "Hej, jag skulle vilja veta mer om min pension.",
        "Jag är 45 år gammal och jobbar som lärare.",
        "Min månadslön är 38000 kr.",
        "Vad är AKAP-KR?"
    ]
    
    for i, message in enumerate(messages):
        print(f"\n--- Message {i+1} ---")
        data = {"message": message}
        print(f"Sending: {message}")
        
        try:
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 200:
                print(f"Response: {response.json()['response']}")
            else:
                print(f"Error: Status code {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
            # Wait a bit between messages
            if i < len(messages) - 1:
                time.sleep(2)
                
        except Exception as e:
            print(f"Error: {str(e)}")
            return False
    
    return True

if __name__ == "__main__":
    print("Testing pension advisor API...")
    print("\n=== Testing basic chat endpoint ===")
    test_chat_endpoint()
    
    print("\n=== Testing conversation flow ===")
    test_conversation_flow()
