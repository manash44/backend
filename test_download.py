import yt_dlp
import os

url = "https://xhamster1.desi/videos/i-really-like-my-friends-bf-and-i-couldnt-resist-4k-hd-tim-team-xhWUF0w"

def test_dl():
    print(f"Testing URL: {url}")
    
    opts = {
        'cookiesfrombrowser': ('chrome',), 
        'verbose': True,
        'no_warnings': False,
        'ignoreerrors': True,
    }

    # First try standard with cookies (simulating local user)
    print("\n--- Attempt 1: Standard with Chrome Cookies ---")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False) # Just extract info
            if info and 'formats' in info:
                print("SUCCESS: Found formats!")
                return
            else:
                print("FAILED: No formats.")
    except Exception as e:
        print(f"ERROR: {e}")

    # Try without cookies but with user agent
    print("\n--- Attempt 2: User Agent Only (No Cookies) ---")
    opts.pop('cookiesfrombrowser', None)
    opts['http_headers'] = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=False)
            print("SUCCESS")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_dl()
