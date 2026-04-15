import urllib.request
import urllib.error
import json
import time

def test_endpoint(fmt):
    req = urllib.request.Request(
        "http://127.0.0.1:5000/download",
        data=json.dumps({
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "format": fmt,
            "quality": "best"
        }).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode('utf-8'))
            task_id = data["task_id"]
            print(f"Task ID ({fmt}):", task_id)
    except urllib.error.URLError as e:
        print("Error submitting:", e)
        return

    while True:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:5000/status/{task_id}") as s_res:
                data = json.loads(s_res.read().decode('utf-8'))
                print(f"[{fmt}] Status:", data.get("status"), "Message:", data.get("message"))
                
                if data.get("status") in ["ready", "error"]:
                    print(f"[{fmt}] Final state:", json.dumps(data, indent=2))
                    break
        except urllib.error.URLError as e:
            print("Error checking status:", e)
            break
            
        time.sleep(2)

test_endpoint("video")
print("-" * 50)
test_endpoint("audio")
