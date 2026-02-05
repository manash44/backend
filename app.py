from flask import Flask, request, jsonify, send_from_directory, send_file, Response
import yt_dlp
import os
import re
import threading
import uuid
import time
import shutil
import tempfile
import random

from flask_cors import CORS
try:
    from yt_dlp.networking.impersonate import ImpersonateTarget
except (ImportError, Exception):
    ImpersonateTarget = None

# Serve static files from 'frontend/dist'
app = Flask(__name__, static_folder='frontend/dist/assets', static_url_path='/assets')
CORS(app)

# Temp directory for downloads
TEMP_DIR = os.path.join(tempfile.gettempdir(), 'vidgrab_downloads')
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

tasks = {}

# List of User Agents to rotate
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
]

@app.route('/')
def index():
    return send_from_directory('frontend/dist', 'index.html')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('frontend/dist', 'manifest.json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory('frontend/dist', 'sw.js')

@app.route('/icon.svg')
def icon():
    return send_from_directory('frontend/dist', 'icon.svg')

def progress_hook(d, task_id):
    if d['status'] == 'downloading':
        try:
            # Get file sizes first
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded_bytes = d.get('downloaded_bytes', 0)
            
            # Calculate percentage manually for accuracy
            if total_bytes:
                p = (downloaded_bytes / total_bytes) * 100
            else:
                p = 0
                # Fallback to string if available and calculation failed
                if '_percent_str' in d:
                    try:
                        p = float(d['_percent_str'].replace('%','').strip())
                    except:
                        pass

            speed = d.get('_speed_str', 'N/A')
            eta = d.get('_eta_str', 'N/A')
            
            tasks[task_id]['progress'] = p
            tasks[task_id]['speed'] = speed
            tasks[task_id]['eta'] = eta
            tasks[task_id]['total_bytes'] = total_bytes
            tasks[task_id]['downloaded_bytes'] = downloaded_bytes
            tasks[task_id]['total'] = format_size(total_bytes) if total_bytes else '?? MB'
            tasks[task_id]['downloaded'] = format_size(downloaded_bytes)
            tasks[task_id]['status'] = 'downloading'
            
            # Debug log to verify hook is firing
            print(f"Progress: {p:.1f}% | {tasks[task_id]['downloaded']} / {tasks[task_id]['total']}")
            
        except Exception as e:
            print(f"Progress Hook Error: {e}")
            pass
    elif d['status'] == 'finished':
        filename = d.get('filename', '')
        if filename:
            tasks[task_id]['downloaded_file'] = filename
        tasks[task_id]['progress'] = 100

class MyLogger:
    def __init__(self, task_id):
        self.task_id = task_id
    def debug(self, msg):
        # Filter out noisy debug messages
        msg_str = str(msg)
        if any(x in msg_str.lower() for x in ['download', 'extract', 'request', 'error', 'warning']):
            self.add_log(msg_str)
    def warning(self, msg):
        self.add_log(f"⚠️ {msg}")
    def error(self, msg):
        self.add_log(f"❌ {msg}")
    def add_log(self, msg):
        if self.task_id in tasks:
            if 'logs' not in tasks[self.task_id]:
                tasks[self.task_id]['logs'] = []
            # Clean up ANSI codes using regex
            clean_msg = str(msg)
            # Regex to strip ANSI escape codes
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            clean_msg = ansi_escape.sub('', clean_msg)
            
            # Also strip literal bracket codes if they appear as text
            clean_msg = re.sub(r'\[\d+(?:;\d+)*m', '', clean_msg)
            
            tasks[self.task_id]['logs'].append(clean_msg[:300])
            if len(tasks[self.task_id]['logs']) > 50:
                tasks[self.task_id]['logs'].pop(0)

def get_referer(url):
    """Extract referer from URL"""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"

def run_download(url, task_id, fmt='video', qual='best'):
    # Create task-specific temp directory
    task_dir = os.path.join(TEMP_DIR, task_id)
    if not os.path.exists(task_dir):
        os.makedirs(task_dir)

    # Get random user agent
    user_agent = random.choice(USER_AGENTS)
    referer = get_referer(url)
    
    tasks[task_id]['message'] = 'Connecting to server...'

    # Basic options - let yt-dlp handle headers/user-agents internally
    # providing custom headers often breaks specific extractors (like YouTube's Android client)
    ydl_opts = {
        'ffmpeg_location': os.getcwd() if os.path.exists(os.path.join(os.getcwd(), 'ffmpeg.exe')) else None,
        'outtmpl': os.path.join(task_dir, '%(title)s.%(ext)s'),
        'progress_hooks': [lambda d: progress_hook(d, task_id)],
        'logger': MyLogger(task_id),
        
        # Network settings
        'socket_timeout': 30,
        'retries': 15,
        'fragment_retries': 15,
        
        # Geo bypass
        'geo_bypass': True,
        
        # Don't use IPv6
        'source_address': '0.0.0.0',
        
        # Other settings
        'noplaylist': True,
        'restrictfilenames': True,
        'windowsfilenames': True,
        'ignoreerrors': False,
        'no_warnings': True,
        'quiet': False,
        
        # Optimizations
        # Reduced concurrency to prevent fragment dropouts/throttling
        'concurrent_fragment_downloads': 3,
        'buffersize': 1024 * 1024 * 16,
        'http_chunk_size': 10485760,
        
        # Headers to mimic browser
        'http_headers': {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Fetch-Mode': 'navigate',
        }
    }

    # Enable curl-cffi impersonation if available
    # This helps avoid server blocking (WinError 10054)
    use_impersonate = True
    try:
        import curl_cffi
        if ImpersonateTarget is not None and use_impersonate:
            ydl_opts['impersonate'] = 'chrome'
            tasks[task_id]['logs'].append("Using curl-cffi browser impersonation")
    except (ImportError, Exception) as e:
        tasks[task_id]['logs'].append(f"Impersonation not available: {str(e)[:50]}")

    # Format Logic
    if fmt == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        if qual in ['1080', '720', '480', '360']:
            ydl_opts['format'] = f'bestvideo[height<={qual}]+bestaudio/best[height<={qual}]/best'
        else:
            # Try multiple format options
            ydl_opts['format'] = 'best/bestvideo+bestaudio'
    
    # Check if this is an XHamster site - they need special handling
    is_xhamster = 'xhamster' in url.lower() or 'xh' in url.lower()
    
    # Don't use cookies by default - causes issues when browser is open
    # But for XHamster and others, we might try cookies on retry
    ydl_opts.pop('cookiesfrombrowser', None)
    
    # Retry logic with exponential backoff
    max_retries = 4
    last_error = None
    cookie_failed = False
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                wait_time = (attempt + 1) * 3
                tasks[task_id]['message'] = f'Retry {attempt + 1}/{max_retries} with different settings...'
                tasks[task_id]['logs'].append(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                # Use different user agent on retry
                ydl_opts['http_headers']['User-Agent'] = random.choice(USER_AGENTS)
                
                # For XHamster sites, try using cookies from browser on retry
                # ONLY if we haven't failed with cookies before
                if is_xhamster and attempt >= 1 and not cookie_failed:
                    try:
                        # Attempt to use cookies
                        ydl_opts['cookiesfrombrowser'] = ('chrome', None, None, None)
                        tasks[task_id]['logs'].append("Trying with Chrome cookies...")
                    except:
                        pass
                
                # Try without impersonation on later retries if it failed
                if attempt >= 2 and 'impersonate' in ydl_opts:
                    ydl_opts.pop('impersonate', None)
                    tasks[task_id]['logs'].append("Trying without impersonation...")
            
            tasks[task_id]['message'] = 'Extracting video info...'
            
            try:
                ydl_instance = yt_dlp.YoutubeDL(ydl_opts)
            except Exception as e:
                # Catch initialization errors (like impersonate target missing)
                if 'impersonate' in str(e).lower() or 'target' in str(e).lower():
                    tasks[task_id]['logs'].append(f"⚠️ Impersonation failed: {str(e)[:100]}")
                    ydl_opts.pop('impersonate', None)
                    # Retry immediately in next loop or continue if we can
                    continue
                raise e

            with ydl_instance as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Find the downloaded file
                downloaded_file = None
                if os.path.exists(task_dir):
                    files = os.listdir(task_dir)
                    if files:
                        files_with_paths = [(f, os.path.getmtime(os.path.join(task_dir, f))) 
                                           for f in files if not f.endswith('.part') and not f.endswith('.ytdl')]
                        if files_with_paths:
                            files_with_paths.sort(key=lambda x: x[1], reverse=True)
                            downloaded_file = files_with_paths[0][0]
                
                if downloaded_file:
                    tasks[task_id]['status'] = 'ready'
                    tasks[task_id]['filename'] = downloaded_file
                    tasks[task_id]['message'] = 'Ready to save!'
                    tasks[task_id]['created_at'] = time.time()
                    
                    file_path = os.path.join(task_dir, downloaded_file)
                    file_size = os.path.getsize(file_path)
                    tasks[task_id]['file_size'] = file_size
                    tasks[task_id]['file_size_str'] = format_size(file_size)
                    return  # Success!
                else:
                    raise Exception('Download completed but file not found')
                    
        except Exception as e:
            import traceback
            last_error = str(e)
            error_str = last_error.lower()
            
            # Handle Cookie Permission Errors gracefully (Suppress huge traceback)
            if "permission denied" in error_str and "cookies" in error_str:
                cookie_failed = True
                tasks[task_id]['logs'].append("⚠️ Cookies locked (Chrome is open). Retrying without cookies...")
                ydl_opts.pop('cookiesfrombrowser', None)
                continue # Immediately retry
            elif "copy chrome cookie database" in error_str or ("cookie" in error_str and "database" in error_str):
                cookie_failed = True
                tasks[task_id]['logs'].append("⚠️ Cookie database locked. Retrying without cookies...")
                ydl_opts.pop('cookiesfrombrowser', None)
                continue # Immediately retry

            # Log full traceback only for other errors
            full_error = traceback.format_exc()
            print(f"[ERROR] Download failed: {full_error}")
            
            tasks[task_id]['logs'].append(f"Attempt {attempt + 1} failed: {last_error[:200]}")
            
            # Check for impersonation errors specifically
            is_recoverable = False
            if 'impersonate' in last_error.lower() or 'target' in last_error.lower():
                is_recoverable = True
                ydl_opts.pop('impersonate', None)
                tasks[task_id]['logs'].append("Disabling impersonation/target for next retry...")

            # Check if it's a recoverable error
            recoverable_errors = ['connection', 'timeout', 'reset', 'aborted', 'temporarily', '429', '503', 'unable to extract', 'extract', 'title', 'impersonate', 'target']
            is_recoverable = is_recoverable or any(err in last_error.lower() for err in recoverable_errors)
            
            # For XHamster extraction errors, always retry with different methods
            if is_xhamster and 'unable to extract' in last_error.lower():
                is_recoverable = True
                # Try different strategies
                if attempt == 1:
                    # Try with cookies
                    try:
                        ydl_opts['cookiesfrombrowser'] = ('chrome', None, None, None)
                    except:
                        pass
                elif attempt == 2:
                    # Try without impersonation
                    ydl_opts.pop('impersonate', None)
                    ydl_opts.pop('cookiesfrombrowser', None)
            
            if not is_recoverable or attempt == max_retries - 1:
                break
    
    # All retries failed
    tasks[task_id]['status'] = 'error'
    error_msg = last_error or 'Unknown error'
    
    # Provide helpful error messages
    if 'unable to extract' in error_msg.lower() or 'extract title' in error_msg.lower():
        if is_xhamster:
            error_msg = "⚠️ XHamster extraction failed. Solutions:\n1. Open the video in Chrome browser first\n2. Make sure the video URL is correct\n3. Try xhamster.com instead of .desi domain\n4. The site may have changed - try updating yt-dlp: py -m pip install --upgrade yt-dlp"
        else:
            error_msg = f"⚠️ Unable to extract video info. The site may have changed or requires special handling.\nTry:\n1. Open the video in your browser first\n2. Update yt-dlp: py -m pip install --upgrade yt-dlp\n3. Check if the URL is correct"
    elif 'connection' in error_msg.lower() or 'reset' in error_msg.lower() or '10054' in error_msg:
        error_msg = "🚫 Connection blocked! Solutions:\n1. Use a VPN\n2. Open the site in Chrome first, then retry\n3. Try xhamster.com instead of .desi"
    elif 'cookie' in error_msg.lower():
        error_msg = "Cookie error - Close Chrome browser and retry, or try a different browser"
    elif 'ffmpeg' in error_msg.lower():
        error_msg += " (Install FFmpeg for better format support)"
    elif '403' in error_msg:
        error_msg = "Access denied. The site may require login or is geo-restricted. Try using a VPN."
    elif '404' in error_msg:
        error_msg = "Video not found. The URL may be invalid or the video was removed."
    elif 'unavailable' in error_msg.lower():
        error_msg = "Video unavailable in your region. Try using a VPN."
        
    tasks[task_id]['message'] = error_msg

def format_size(size_bytes):
    """Format bytes to human readable string"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def cleanup_old_tasks():
    """Remove tasks and files older than 1 hour"""
    current_time = time.time()
    to_remove = []
    
    for tid, task in list(tasks.items()):
        created_at = task.get('created_at', current_time)
        if current_time - created_at > 3600 or task.get('downloaded', False):
            to_remove.append(tid)
            task_dir = os.path.join(TEMP_DIR, tid)
            if os.path.exists(task_dir):
                try:
                    shutil.rmtree(task_dir)
                except:
                    pass
    
    for tid in to_remove:
        if tid in tasks:
            del tasks[tid]

@app.route('/download', methods=['POST'])
def start_download():
    data = request.get_json()
    url = data.get('url')
    fmt = data.get('format', 'video')
    qual = data.get('quality', 'best')
    
    if not url:
        return jsonify({'status': 'error', 'message': 'No URL provided'}), 400

    cleanup_old_tasks()

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'progress': 0, 
        'status': 'queued', 
        'message': 'Starting...',
        'created_at': time.time(),
        'logs': []
    }
    
    thread = threading.Thread(target=run_download, args=(url, task_id, fmt, qual))
    thread.daemon = True
    thread.start()

    return jsonify({'status': 'success', 'task_id': task_id})

@app.route('/status/<task_id>', methods=['GET'])
def get_status(task_id):
    task = tasks.get(task_id)
    if task:
        return jsonify({
            'status': task.get('status'),
            'progress': task.get('progress', 0),
            'speed': task.get('speed'),
            'eta': task.get('eta'),
            'total': task.get('total'),
            'downloaded': task.get('downloaded'),
            'total_bytes': task.get('total_bytes', 0),
            'downloaded_bytes': task.get('downloaded_bytes', 0),
            'message': task.get('message'),
            'filename': task.get('filename'),
            'file_size_str': task.get('file_size_str'),
            'filename': task.get('filename'),
            'file_size_str': task.get('file_size_str'),
            'logs': task.get('logs', []),
            'raw_progress': task.get('raw_progress'),
        })
    return jsonify({'status': 'error', 'message': 'Task not found'}), 404

@app.route('/file/<task_id>', methods=['GET'])
def download_file(task_id):
    """Serve the downloaded file to browser"""
    task = tasks.get(task_id)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    if task.get('status') != 'ready':
        return jsonify({'error': 'File not ready'}), 400
    
    filename = task.get('filename')
    if not filename:
        return jsonify({'error': 'No file available'}), 404
    
    task_dir = os.path.join(TEMP_DIR, task_id)
    file_path = os.path.join(task_dir, filename)
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    tasks[task_id]['downloaded'] = True
    
    ext = os.path.splitext(filename)[1].lower()
    mime_types = {
        '.mp4': 'video/mp4',
        '.webm': 'video/webm',
        '.mkv': 'video/x-matroska',
        '.mp3': 'audio/mpeg',
        '.m4a': 'audio/mp4',
        '.wav': 'audio/wav',
        '.flac': 'audio/flac',
        '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime',
    }
    mime_type = mime_types.get(ext, 'application/octet-stream')
    
    return send_file(
        file_path,
        mimetype=mime_type,
        as_attachment=True,
        download_name=filename
    )

if __name__ == '__main__':
    import socket
    import sys
    
    # Check if ngrok mode is requested
    USE_NGROK = '--ngrok' in sys.argv or '-n' in sys.argv
    
    # Clean up any old temp files on startup
    if os.path.exists(TEMP_DIR):
        for item in os.listdir(TEMP_DIR):
            item_path = os.path.join(TEMP_DIR, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            except:
                pass
    
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "127.0.0.1"
    
    public_url = None
    
    if USE_NGROK:
        try:
            from pyngrok import ngrok, conf
            
            print(f"\n{'='*60}")
            print(f"  Starting ngrok tunnel for INTERNET access...")
            print(f"{'='*60}")
            
            # Start ngrok tunnel
            public_url = ngrok.connect(5000, "http").public_url
            
            print(f"\n{'='*60}")
            print(f"  VidGrab Server Running with INTERNET ACCESS!")
            print(f"{'='*60}")
            print(f"  Local:    http://localhost:5000")
            print(f"  Network:  http://{local_ip}:5000")
            print(f"")
            print(f"  >>> INTERNET URL: {public_url}")
            print(f"")
            print(f"{'='*60}")
            print(f"  Use the INTERNET URL in your Android app!")
            print(f"  This URL works from ANYWHERE (mobile data, other WiFi)")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"\n[WARNING] Could not start ngrok: {e}")
            print(f"[INFO] Falling back to local network mode")
            print(f"[TIP] Run 'ngrok config add-authtoken YOUR_TOKEN' first")
            print(f"[TIP] Get free token at: https://dashboard.ngrok.com/signup\n")
            USE_NGROK = False
    
    if not USE_NGROK:
        print(f"\n{'='*60}")
        print(f"  VidGrab Server Running!")
        print(f"{'='*60}")
        print(f"  Local:   http://localhost:5000")
        print(f"  Network: http://{local_ip}:5000  (same WiFi only)")
        print(f"{'='*60}")
        print(f"  For INTERNET access, run with: python app.py --ngrok")
        print(f"{'='*60}")
        print(f"  Access from your phone using the Network URL")
        print(f"  Files download to YOUR BROWSER'S Downloads folder")
        print(f"{'='*60}\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
