import requests
import time
import sys

def test_endpoint(fmt):
    res = requests.post("http://127.0.0.1:5000/download", json={
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "format": fmt,
        "quality": "best"
    })
    
    if res.status_code != 200:
        print("Error submitting:", res.text)
        return

    task_id = res.json()["task_id"]
    print(f"Task ID ({fmt}):", task_id)
    
    while True:
        s_res = requests.get(f"http://127.0.0.1:5000/status/{task_id}")
        data = s_res.json()
        print(f"[{fmt}] Status:", data.get("status"), "Message:", data.get("message"))
        
        if data.get("status") in ["ready", "error"]:
            print(f"[{fmt}] Final state:", data)
            break
            
        time.sleep(2)

test_endpoint("video")
print("-" * 50)
test_endpoint("audio")
