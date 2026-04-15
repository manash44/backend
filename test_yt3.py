import yt_dlp
import traceback
import random

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

def test():
    ydl_opts = {
        "format": "best[ext=mp4]/bestvideo+bestaudio/best",
        "verbose": True,
        "outtmpl": "test_video.%(ext)s",
        "http_headers": {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["tv", "web_safari", "ios", "default"],
            }
        }
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ", download=True)
            print("Video downloaded successfully")
    except Exception as e:
        print("Error:")
        traceback.print_exc()

test()
