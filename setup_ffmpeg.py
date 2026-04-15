import os
import zipfile
import urllib.request
import shutil
import sys

def download_ffmpeg():
    print("Downloading FFmpeg (this may take a minute)...")
    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    zip_path = "ffmpeg.zip"
    
    try:
        # Download
        urllib.request.urlretrieve(url, zip_path)
        print("Download complete. Extracting...")
        
        # Extract
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Find the bin folder inside the zip (it usually has a versioned folder name)
            for file in zip_ref.namelist():
                if file.endswith('ffmpeg.exe') or file.endswith('ffprobe.exe'):
                    filename = os.path.basename(file)
                    print(f"Extracting {filename}...")
                    target_path = os.path.join(os.getcwd(), filename)
                    
                    # Read from zip and write to current dir
                    with zip_ref.open(file) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)
                        
        print("FFmpeg setup complete! You can now use MP3 conversion.")
        
    except Exception as e:
        print(f"Error setting up FFmpeg: {e}")
    finally:
        # Cleanup zip
        if os.path.exists(zip_path):
            os.remove(zip_path)

if __name__ == "__main__":
    download_ffmpeg()
