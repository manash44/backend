import os
import sys
import time
import subprocess
import uuid
import threading
import logging
import re
import random
import shutil
from urllib.parse import urlparse, urlunparse
from flask import Flask, request, jsonify, send_file, Response, stream_with_context
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Enable CORS for all domains to allow frontend connection from Netlify/Local
CORS(app) 

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'downloads')
TEMP_DIR = os.path.join(BASE_DIR, 'temp')

for d in [DOWNLOAD_DIR, TEMP_DIR]:
    os.makedirs(d, exist_ok=True)

# Global Tasks Dictionary
tasks = {}

# --- Helper Functions ---

def clean_old_files():
    """Delete files older than 1 hour"""
    try:
        now = time.time()
        for f in os.listdir(DOWNLOAD_DIR):
            path = os.path.join(DOWNLOAD_DIR, f)
            if os.path.isfile(path):
                if now - os.path.getmtime(path) > 3600:
                    os.remove(path)
        
        # Also clean temp folders
        for str_uuid in list(tasks.keys()):
            # Remove tasks older than 1 hour from memory
            if 'created_at' in tasks[str_uuid] and now - tasks[str_uuid]['created_at'] > 3600:
                del tasks[str_uuid]
                
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

def format_size(size_bytes):
    if size_bytes == 0: return "0B"
    size_name = ("B", "KB", "MB", "GB")
    i = int(os.path.dirname(str(size_bytes))) # rough log10
    import math
    if size_bytes == 0:
        return "0B"
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0'
]

def get_referer(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"

# --- Core Downloader Logic ---

import yt_dlp

class MyLogger:
    def __init__(self, task_id):
        self.task_id = task_id

    def debug(self, msg):
        if self.task_id in tasks:
            # Filter spammy logs
            if not any(x in msg for x in ['[debug] ', 'Fetching', 'Invoking']):
                 tasks[self.task_id]['logs'].append(msg)

    def warning(self, msg):
        if self.task_id in tasks:
            tasks[self.task_id]['logs'].append(f"WARNING: {msg}")

    def error(self, msg):
        if self.task_id in tasks:
            tasks[self.task_id]['logs'].append(f"ERROR: {msg}")

def progress_hook(d, task_id):
    if task_id in tasks:
        if d['status'] == 'downloading':
            p = d.get('_percent_str', '0%').replace('%','')
            try:
                tasks[task_id]['progress'] = float(p)
            except:
                pass
            tasks[task_id]['speed'] = d.get('_speed_str', 'N/A')
            tasks[task_id]['eta'] = d.get('_eta_str', 'N/A')
            tasks[task_id]['status'] = 'downloading'
            
        elif d['status'] == 'finished':
            tasks[task_id]['progress'] = 100
            tasks[task_id]['message'] = 'Processing conversion...'

def run_download(url, task_id, fmt='video', qual='best'):
    task_dir = os.path.join(TEMP_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)
    
    # ---------------------------------------------------------
    # FEATURE: URL Normalization for XHamster Mirrors
    # Converts mirrors (xhamster1.desi) to canonical (xhamster.com)
    # This invokes the robust XHamsterIE instead of generic extraction.
    # ---------------------------------------------------------
    if 'xhamster' in url.lower() and '.com' not in url.lower():
        try:
            parsed = urlparse(url)
            if 'xhamster' in parsed.netloc:
                 new_netloc = 'xhamster.com'
                 # Reconstruct URL
                 url = urlunparse(parsed._replace(netloc=new_netloc))
                 tasks[task_id]['logs'].append(f"Redirecting mirror to canonical: {url}")
        except:
            pass
    # ---------------------------------------------------------

    tasks[task_id]['message'] = 'Initializing downloader...'
    
    ydl_opts = {
        'ffmpeg_location': os.getcwd() if os.path.exists(os.path.join(os.getcwd(), 'ffmpeg.exe')) else None,
        'outtmpl': os.path.join(task_dir, '%(title)s.%(ext)s'),
        'progress_hooks': [lambda d: progress_hook(d, task_id)],
        'logger': MyLogger(task_id),
        
        # Robust Network Options
        'socket_timeout': 30,
        'retries': 20,
        'file_access_retries': 5,
        'fragment_retries': 20,
        'skip_unavailable_fragments': False,
        
        # Privacy / Anti-Block
        'geo_bypass': True,
        'source_address': '0.0.0.0', 
        
        # Output
        'noplaylist': True,
        'restrictfilenames': True,   # Avoid special chars in filename
        'windowsfilenames': True,
        
        # Headers
        'http_headers': {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': get_referer(url)
        }
    }

    # Format Selection
    if fmt == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        # Video Quality Logic
        if qual == 'best':
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
        else:
            # Try to get close to target height, fallback to best
            try:
                h = int(qual)
                ydl_opts['format'] = f'bestvideo[height<={h}]+bestaudio/best[height<={h}]/best'
            except:
                ydl_opts['format'] = 'bestvideo+bestaudio/best'

    # Attempt Download
    try:
        # 1. First Attempt: Standard
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
            
    except Exception as e:
        tasks[task_id]['logs'].append(f"Standard download failed: {str(e)}")
        
        # 2. Retry Logic specifically for XHamster/Others that might need it
        # Sometimes switching UA or using 'impersonate' (if available via plugin) helps
        # For now, we perform a retry with stricter format backup
        
        tasks[task_id]['message'] = 'Retrying with backup options...'
        ydl_opts['format'] = 'best' # Fallback to single file if merge failed
        
        try:
             with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)
        except Exception as retry_e:
            tasks[task_id]['error'] = str(retry_e)
            tasks[task_id]['status'] = 'error'
            return

    # Success Handling
    try:
        # Identify downloaded file
        files = [f for f in os.listdir(task_dir) if not f.endswith('.part') and not f.endswith('.ytdl')]
        if not files:
            raise Exception("No file found after download")
            
        # Pick the most recent/largest file
        downloaded_file = files[0] # Usually only one
        
        # Move to permanent download folder
        final_path = os.path.join(DOWNLOAD_DIR, f"{task_id}_{downloaded_file}")
        shutil.move(os.path.join(task_dir, downloaded_file), final_path)
        shutil.rmtree(task_dir) # Clean temp
        
        tasks[task_id]['status'] = 'ready'
        tasks[task_id]['filename'] = downloaded_file
        tasks[task_id]['file_path'] = final_path
        tasks[task_id]['file_size_str'] = format_size(os.path.getsize(final_path))
        
    except Exception as e:
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['error'] = f"File processing error: {str(e)}"


# --- Routes ---

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "VidGrab Backend",
        "version": "2.0.0"
    })

@app.route('/status/test')
def status_test():
    return jsonify({"status": "ok"}), 200

@app.route('/download', methods=['POST'])
def start_download():
    data = request.json
    url = data.get('url')
    fmt = data.get('format', 'video')
    qual = data.get('quality', 'best')
    
    if not url:
        return jsonify({"error": "No URL provided"}), 400
        
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'id': task_id,
        'status': 'queued',
        'progress': 0,
        'logs': [],
        'created_at': time.time()
    }
    
    # Run in background thread
    threading.Thread(target=run_download, args=(url, task_id, fmt, qual)).start()
    
    # Clean up old tasks periodically
    if random.random() < 0.1:
        threading.Thread(target=clean_old_files).start()
        
    return jsonify({"task_id": task_id})

@app.route('/status/<task_id>')
def get_status(task_id):
    if task_id not in tasks:
        return jsonify({"status": "error", "message": "Task not found"}), 404
    return jsonify(tasks[task_id])

@app.route('/file/<task_id>')
def get_file(task_id):
    if task_id not in tasks or tasks[task_id].get('status') != 'ready':
         return jsonify({"error": "File not ready"}), 404
         
    file_path = tasks[task_id]['file_path']
    filename = tasks[task_id]['filename']
    
    return send_file(file_path, as_attachment=True, download_name=filename)

if __name__ == '__main__':
    # Default port 10000 for Render, 5000 for local
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
