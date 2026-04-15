import yt_dlp
import traceback

def test():
    ydl_opts = {
        "extractor_args": {
            "youtube": {
                "player_client": ["tv", "web_safari", "ios", "default"],
            }
        },
        "verbose": True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info("https://www.youtube.com/watch?v=BaW_jenozKc", download=False)
            print("Video metadata extracted successfully")
    except Exception as e:
        print("Error:")
        traceback.print_exc()

test()
