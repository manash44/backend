import urllib.request
import json
import time

url = "http://127.0.0.1:5000/download"
data = {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "format": "audio", "quality": "best"}
req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req) as response:
    res = json.loads(response.read().decode())
print(res)

task_id = res["task_id"]

for _ in range(30):
    with urllib.request.urlopen(f"http://127.0.0.1:5000/status/{task_id}") as status_req:
        status_res = json.loads(status_req.read().decode())
        print(status_res)
        if status_res.get("status") in ("ready", "error"):
            break
        time.sleep(1)
