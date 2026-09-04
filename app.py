# flake8: noqa: E501
import base64
import itertools
import logging
import math
import os
import random
import shutil
import threading
import time
import uuid
import re
import concurrent.futures
from typing import Any, Dict, List, Optional
from urllib.parse import ParseResult, urlparse, urlunparse

from flask import Flask, request, jsonify, send_file  # type: ignore
from flask_cors import CORS  # type: ignore

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Use /tmp for temporary files if available (better for containerized envs)
TEMP_DIR = (
    "/tmp/vidgetnow_downloads"
    if os.path.exists("/tmp")
    else os.path.join(BASE_DIR, "temp")
)
DOWNLOAD_DIR = os.path.join(TEMP_DIR, "downloads_ready")

for _d in [DOWNLOAD_DIR, TEMP_DIR]:
    os.makedirs(_d, exist_ok=True)

# Global Tasks Dictionary
tasks: Dict[str, Any] = {}

# --- Optimization helper for background cleanup ---
last_cleanup: float = 0.0
cleanup_lock = threading.Lock()

# Global thread pool to ensure tasks are downloaded one by one
download_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

# --- Helper Functions ---


def _truncate(s: str, n: int) -> str:
    """Truncate string to at most n characters (Pyre2-compatible)."""
    # Use itertools.islice to avoid slice indexing, which Pyre2's stubs reject.
    return "".join(itertools.islice(s, n))


def clean_old_files() -> None:
    """Delete files older than 1 hour."""
    global last_cleanup
    with cleanup_lock:
        if time.time() - last_cleanup < 600:
            return
        last_cleanup = time.time()

    try:
        now = time.time()
        if os.path.exists(DOWNLOAD_DIR):
            for f in os.listdir(DOWNLOAD_DIR):
                path = os.path.join(DOWNLOAD_DIR, f)
                if os.path.isfile(path):
                    if now - os.path.getmtime(path) > 3600:
                        try:
                            os.remove(path)
                        except Exception:
                            pass

        if os.path.exists(TEMP_DIR):
            for f in os.listdir(TEMP_DIR):
                path = os.path.join(TEMP_DIR, f)
                if os.path.isdir(path) and f != "downloads_ready":
                    if now - os.path.getmtime(path) > 3600:
                        try:
                            shutil.rmtree(path)
                        except Exception:
                            pass

        for str_uuid in list(tasks.keys()):
            task = tasks[str_uuid]
            if isinstance(task, dict) and "created_at" in task:
                if now - float(task["created_at"]) > 3600:
                    tasks.pop(str_uuid, None)

    except Exception as e:
        logger.error("Cleanup error: %s", e)


def format_size(size_bytes: int) -> str:
    """Return a human-readable file size string."""
    if size_bytes <= 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p: float = math.pow(1024, i)
    val: float = float(size_bytes) / p
    s_val = int(val * 100) / 100.0
    return "%s %s" % (s_val, size_name[i])


USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
]


def get_referer(url: str) -> str:
    """Return the origin of the given URL, used as a Referer header."""
    try:
        parsed: ParseResult = urlparse(url)
        return "%s://%s/" % (parsed.scheme, parsed.netloc)
    except Exception:
        return "https://www.google.com/"


def get_cookiefile() -> Optional[str]:
    """Return a cookies.txt path from disk or Render environment variables."""
    explicit_path = os.environ.get("YTDLP_COOKIES_FILE")
    if explicit_path and os.path.exists(explicit_path):
        return explicit_path

    repo_cookies = os.path.join(BASE_DIR, "cookies.txt")
    if os.path.exists(repo_cookies):
        return repo_cookies

    cookie_text = os.environ.get("YTDLP_COOKIES", "")
    cookie_b64 = os.environ.get("YTDLP_COOKIES_B64", "")
    if cookie_b64:
        try:
            cookie_text = base64.b64decode(cookie_b64).decode("utf-8")
        except Exception:
            logger.warning("YTDLP_COOKIES_B64 could not be decoded")
            cookie_text = ""

    if cookie_text.strip():
        env_cookie_path = os.path.join(TEMP_DIR, "cookies.txt")
        with open(env_cookie_path, "w", encoding="utf-8") as f:
            f.write(cookie_text)
        return env_cookie_path

    return None


def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def friendly_download_error(error: Exception) -> str:
    raw = str(error).replace("ERROR: ", "").strip()
    lower = raw.lower()

    if "http error 429" in lower or "too many requests" in lower:
        return (
            "This site is rate-limiting the server. For YouTube, add a fresh "
            "cookies.txt file to the backend or try again later."
        )
    if "sign in to confirm" in lower or "confirm you're not a bot" in lower:
        return (
            "YouTube requires verification. Make sure you are logged into YouTube in your browser, "
            "or close your browser if the cookies are locked."
        )
    if "could not copy chrome cookie database" in lower or "permission denied" in lower and "cookies" in lower:
        return "Your browser is locking its cookies. Please fully close Chrome/Edge and try again, or use a different browser in Settings."
    if "unsupported url" in lower:
        return "This URL is not supported by the downloader."
    if "keyerror('videomodel')" in lower or "videomodel" in lower:
        return "This adult site recently changed its layout. Our extractor is updating. Try a different site or check back soon."

    truncated = _truncate(raw, 180)
    return "Failed: " + truncated + ("..." if len(raw) > 180 else "")


# --- Core Downloader Logic ---


class MyLogger:
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id

    def debug(self, msg: str) -> None:
        if self.task_id in tasks:
            # Filter spammy logs
            if "merging" in msg.lower() or "converting" in msg.lower():
                tasks[self.task_id]["message"] = msg  # Show merge/convert status
            if not any(x in msg for x in ["[debug] ", "Fetching", "Invoking"]):
                tasks[self.task_id]["logs"].append(msg)

    def warning(self, msg: str) -> None:
        if self.task_id in tasks:
            tasks[self.task_id]["logs"].append("WARNING: " + msg)

    def error(self, msg: str) -> None:
        if self.task_id in tasks:
            tasks[self.task_id]["logs"].append("ERROR: " + msg)


def progress_hook(d: Dict[str, Any], task_id: str) -> None:
    if task_id in tasks:
        if d["status"] == "downloading":
            p_str = str(d.get("_percent_str", "0%"))
            # Remove ANSI color codes that yt-dlp might output
            p_str = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', p_str)
            p = p_str.replace("%", "").strip()
            try:
                tasks[task_id]["progress"] = float(p)
            except Exception:
                pass
            tasks[task_id]["speed"] = d.get("_speed_str", "N/A")
            tasks[task_id]["eta"] = d.get("_eta_str", "N/A")

            # Capture size if available
            if d.get("_total_bytes_str"):
                tasks[task_id]["size"] = d.get("_total_bytes_str")
            elif d.get("_total_bytes_estimate_str"):
                tasks[task_id]["size"] = d.get("_total_bytes_estimate_str")

            tasks[task_id]["status"] = "downloading"

        elif d["status"] == "finished":
            tasks[task_id]["progress"] = 100
            tasks[task_id]["message"] = "Processing conversion..."


def _normalize_url(url: str, task_id: str) -> str:
    """Normalize xhamster mirror URLs to the canonical domain."""
    # Disabling normalization as mirrors often work better than the canonical domain
    # depending on regional blocking. yt-dlp handles most mirrors natively.
    return url


def run_download(
    url: str, task_id: str, fmt: str = "video", qual: str = "best", browser_cookie: str = ""
) -> None:
    task_dir = os.path.join(TEMP_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    url = _normalize_url(url, task_id)

    tasks[task_id]["message"] = "Initializing downloader..."

    try:
        import yt_dlp  # type: ignore
    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["message"] = "Downloader dependency failed to load."
        tasks[task_id]["error"] = str(e)
        logger.exception("yt-dlp import failed")
        return

    try:
        import imageio_ffmpeg  # type: ignore
        ffmpeg_loc = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_loc = os.path.join(BASE_DIR, "ffmpeg.exe")
        if not os.path.exists(ffmpeg_loc):
            ffmpeg_loc = None

    ydl_opts: Dict[str, Any] = {
        "ffmpeg_location": ffmpeg_loc,
        "outtmpl": os.path.join(task_dir, "%(title)s.%(ext)s"),
        "progress_hooks": [lambda d: progress_hook(d, task_id)],
        "logger": MyLogger(task_id),
        "color": "no_color",
        # Robust Network Options
        "socket_timeout": 30,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 5,
        # Privacy / Anti-Block
        "geo_bypass": True,
        "source_address": "0.0.0.0",
        # Output configuration
        "noplaylist": not any(x in url.lower() for x in ["instagram.com", "twitter.com", "x.com"]),
        "restrictfilenames": True,
        "windowsfilenames": True,
        "overwrites": True,
        # Headers
        "http_headers": {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Referer": get_referer(url),
        },
    }

    # --- YouTube-specific options ---
    # Optional: Use cookies.txt if it exists to bypass bot protection reliably
    cookies_path = get_cookiefile()
    if cookies_path:
        ydl_opts["cookiefile"] = cookies_path

    # Do not attempt to extract local browser cookies if running on a cloud server like Render.
    if browser_cookie and browser_cookie.lower() != "none" and not os.environ.get("RENDER"):
        # Only use browser cookies for YouTube to prevent breaking other extractors
        if "youtube.com" in url.lower() or "youtu.be" in url.lower():
            ydl_opts["cookiesfrombrowser"] = (browser_cookie.lower(),)

    if "youtube.com" in url.lower() or "youtu.be" in url.lower():
        # Always use robust player clients to bypass bot verification blocks
        ydl_opts["extractor_args"] = {
            "youtube": {
                "player_client": ["tv", "web_safari", "ios", "default"],
            }
        }

    # Enable browser impersonation for Facebook and Instagram to bypass blocks
    if "facebook.com" in url.lower() or "fb.watch" in url.lower() or "instagram.com" in url.lower():
        # Requires curl_cffi installed
        ydl_opts["impersonate"] = "chrome"
        if "facebook" in url.lower() or "fb.watch" in url.lower():
            if "extractor_args" not in ydl_opts:
                ydl_opts["extractor_args"] = {}
            ydl_opts["extractor_args"]["facebook"] = {"api": ["graphql"]}



    # Format Selection
    if fmt == "audio":
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        ext = fmt if fmt in ["mp4", "webm", "mkv", "flv"] else "mp4"
        if qual == "best":
            # Prefer single file (no merge) or specific extension
            ydl_opts["format"] = f"best[ext={ext}]/bestvideo[ext={ext}]+bestaudio/bestvideo+bestaudio/best"
        else:
            try:
                h = int(qual)
                # Try single file first, then merge if needed, fallback to any extension
                ydl_opts["format"] = (
                    f"best[ext={ext}][height<={h}]/bestvideo[ext={ext}][height<={h}]+bestaudio/"
                    f"best[height<={h}]/bestvideo[height<={h}]+bestaudio/best"
                )
            except Exception:
                ydl_opts["format"] = f"best[ext={ext}]/bestvideo+bestaudio/best"

    # Attempt Download
    try:
        # 1. First Attempt: Standard
        logger.info("Task %s: Starting download for %s", task_id, url)
        logger.info("Task %s: Format=%s, Quality=%s", task_id, fmt, qual)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        tasks[task_id]["message"] = "Download complete. Finalizing..."

    except Exception as e:
        error_msg = str(e)
        tasks[task_id]["logs"].append("Standard download failed: " + error_msg)
        logger.error("Task %s failed first attempt: %s", task_id, error_msg)

        # 2. Retry Logic
        tasks[task_id]["message"] = "Retrying with backup options..."

        # Force single file to avoid merge issues on low-resource envs
        if fmt == "audio":
            ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio[ext=aac]/m4a/best"
            if "postprocessors" in ydl_opts:
                del ydl_opts["postprocessors"]
        else:
            ext = fmt if fmt in ["mp4", "webm", "mkv", "flv"] else "mp4"
            ydl_opts["format"] = f"best[ext={ext}]/best"

        ydl_opts["verbose"] = True

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)
            tasks[task_id]["message"] = "Retry complete. Finalizing..."
        except Exception as retry_e:
            logger.error("Task %s retry failed: %s", task_id, retry_e)
            tasks[task_id]["message"] = friendly_download_error(retry_e)
            tasks[task_id]["error"] = str(retry_e)
            tasks[task_id]["status"] = "error"
            return

    # Success Handling
    try:
        # Wait a moment for file system to sync
        time.sleep(1)

        # Identify downloaded file with retries
        ready_files: List[str] = []
        for _ in range(10):
            ready_files = [
                f
                for f in os.listdir(task_dir)
                if not f.endswith(".part") and not f.endswith(".ytdl")
            ]
            if ready_files:
                break
            time.sleep(1)

        if not ready_files:
            # Last ditch effort: look for ANY file
            ready_files = list(os.listdir(task_dir))
            if not ready_files:
                raise RuntimeError("No file found after download.")

        if len(ready_files) > 1:
            import zipfile
            tasks[task_id]["message"] = f"Zipping {len(ready_files)} files..."
            zip_filename = "gallery.zip"
            final_path = os.path.join(DOWNLOAD_DIR, task_id + "_" + zip_filename)
            with zipfile.ZipFile(final_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for f in ready_files:
                    zipf.write(os.path.join(task_dir, f), f)
            downloaded_file = zip_filename
        else:
            # Pick largest file (in case of detached audio/video parts)
            ready_files.sort(
                key=lambda x: os.path.getsize(os.path.join(task_dir, x)), reverse=True
            )
            downloaded_file = ready_files[0]
            final_path = os.path.join(DOWNLOAD_DIR, task_id + "_" + downloaded_file)
            shutil.move(os.path.join(task_dir, downloaded_file), final_path)

        tasks[task_id]["status"] = "ready"
        tasks[task_id]["filename"] = downloaded_file
        tasks[task_id]["file_path"] = final_path
        tasks[task_id]["file_size_str"] = format_size(os.path.getsize(final_path))

    except Exception as e:
        tasks[task_id]["status"] = "error"
        err_msg = str(e)
        truncated_err = _truncate(err_msg, 150)
        if len(err_msg) > 150:
            tasks[task_id]["message"] = "Error processing file: " + truncated_err + "..."
        else:
            tasks[task_id]["message"] = "Error processing file: " + err_msg
        tasks[task_id]["error"] = "File processing error: " + str(e)
        logger.error("File error %s: %s", task_id, e)
    finally:
        # Cleanup temp task directory
        try:
            shutil.rmtree(task_dir)
        except Exception:
            pass


# --- Routes ---


@app.route("/")
def home() -> Any:
    return jsonify(
        {"status": "online", "service": "VidGetNow Backend", "version": "2.2.1"}
    )


@app.route("/health")
@app.route("/api/status/test")
@app.route("/status/test")
def status_test() -> Any:
    return jsonify({"status": "ok"}), 200


@app.route("/api/download", methods=["POST"])
@app.route("/download", methods=["POST"])
def start_download() -> Any:
    data: Dict[str, Any] = request.json or {}
    url = str(data.get("url", "")).strip()
    fmt = str(data.get("format", "video"))
    qual = str(data.get("quality", "best"))
    browser_cookie = str(data.get("browserCookie", ""))

    if not url:
        return jsonify({"error": "No URL provided"}), 400
    if not is_valid_url(url):
        return jsonify({"error": "Enter a valid http or https video URL"}), 400

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "id": task_id,
        "status": "queued",
        "progress": 0,
        "logs": [],
        "message": "Waiting in queue...",
        "created_at": time.time(),
    }

    download_executor.submit(run_download, url, task_id, fmt, qual, browser_cookie)

    # Always clean old files to prevent disk usage buildup
    threading.Thread(target=clean_old_files, daemon=True).start()

    return jsonify({"task_id": task_id})


@app.route("/api/status/<task_id>")
@app.route("/status/<task_id>")
def get_status(task_id: str) -> Any:
    if task_id not in tasks:
        return jsonify({"status": "error", "message": "Task not found"}), 404
    return jsonify(tasks[task_id])


@app.route("/api/file/<task_id>")
@app.route("/file/<task_id>")
def get_file(task_id: str) -> Any:
    if task_id not in tasks or tasks[task_id].get("status") != "ready":
        return jsonify({"error": "File not ready"}), 404

    file_path: str = tasks[task_id]["file_path"]
    filename: str = tasks[task_id]["filename"]

    return send_file(file_path, as_attachment=True, download_name=filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
