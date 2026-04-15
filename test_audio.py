import app
import logging
import sys

logging.basicConfig(level=logging.DEBUG)

if __name__ == "__main__":
    task_id = "test_task_123"
    app.tasks[task_id] = {
        "id": task_id,
        "status": "queued",
        "progress": 0,
        "logs": [],
        "message": "Queued..."
    }
    app.run_download("https://www.youtube.com/watch?v=dQw4w9WgXcQ", task_id, "audio", "best")
    print(app.tasks[task_id])
