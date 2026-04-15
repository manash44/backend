import yt_dlp
import traceback

def test():
    ydl_opts = {
        "format": "best[ext=mp4][height<=1080]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "verbose": True,
        "outtmpl": "test_video_1080.%(ext)s",
        "extractor_args": {
            "youtube": {
                "player_client": ["tv", "web_safari", "ios", "default"],
            }
        }
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info("https://www.youtube.com/watch?v=dQw4w9WgXcQ", download=False)
            print("Video matched successfully")
    except Exception as e:
        print("Error:")
        traceback.print_exc()

test()
