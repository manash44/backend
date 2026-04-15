# flake8: noqa: E501
import itertools
import logging
import math
import os
import random
import shutil
import threading
import time
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import ParseResult, urlparse, urlunparse

from flask import Flask, request, jsonify, send_file  # type: ignore
from flask_cors import CORS  # type: ignore
import yt_dlp  # type: ignore

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
            p = str(d.get("_percent_str", "0%")).replace("%", "")
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
    if "xhamster" in url.lower() and ".com" not in url.lower():
        try:
            parsed: ParseResult = urlparse(url)
            if "xhamster" in parsed.netloc:
                normalized = urlunparse((
                    parsed.scheme,
                    "xhamster.com",
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment,
                ))
                tasks[task_id]["logs"].append(
                    "Redirecting mirror to canonical: " + normalized
                )
                return normalized
        except Exception:
            pass
    return url


def run_download(
    url: str, task_id: str, fmt: str = "video", qual: str = "best"
) -> None:
    task_dir = os.path.join(TEMP_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    url = _normalize_url(url, task_id)

    tasks[task_id]["message"] = "Initializing downloader..."

    try:
        import imageio_ffmpeg
        ffmpeg_loc = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_loc = (
            BASE_DIR if os.path.exists(os.path.join(BASE_DIR, "ffmpeg.exe")) else None
        )

    ydl_opts: Dict[str, Any] = {
        "ffmpeg_location": ffmpeg_loc,
        "outtmpl": os.path.join(task_dir, "%(title)s.%(ext)s"),
        "progress_hooks": [lambda d: progress_hook(d, task_id)],
        "logger": MyLogger(task_id),
        # Robust Network Options
        "socket_timeout": 15,
        "retries": 3,
        "fragment_retries": 3,
        "concurrent_fragment_downloads": 5,
        # Privacy / Anti-Block
        "geo_bypass": True,
        "source_address": "0.0.0.0",
        # Output configuration
        "noplaylist": True,
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
    cookies_path = os.path.join(BASE_DIR, "cookies.txt")
    if os.path.exists(cookies_path):
        ydl_opts["cookiefile"] = cookies_path

    if "youtube.com" in url.lower() or "youtu.be" in url.lower():
        # Avoid locking issues with browser cookies by using robust player clients
        ydl_opts["extractor_args"] = {
            "youtube": {
                "player_client": ["tv", "web_safari", "ios", "default"],
            }
        }

    # Add age verification cookies for adult content sites
    if any(
        site in url.lower()
        for site in ["xhamster", "xvideos", "pornhub", "redtube", "youporn"]
    ):
        ydl_opts["http_headers"][
            "Cookie"
        ] = "age_verified=1; hasVisited=1; accessAgeDisclaimerPH=1; accessPH=1"

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
        if qual == "best":
            # Prefer single file (no merge) to reduce server CPU usage
            ydl_opts["format"] = "best[ext=mp4]/bestvideo+bestaudio/best"
        else:
            try:
                h = int(qual)
                # Try single file first, then merge if needed
                ydl_opts["format"] = (
                    "best[ext=mp4][height<=%d]/bestvideo[height<=%d]+bestaudio/best[height<=%d]/best" % (h, h, h)
                )
            except Exception:
                ydl_opts["format"] = "best[ext=mp4]/bestvideo+bestaudio/best"

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
            ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
            if "postprocessors" in ydl_opts:
                del ydl_opts["postprocessors"]
        else:
            ydl_opts["format"] = "best[ext=mp4]/best"

        ydl_opts["verbose"] = True

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)
            tasks[task_id]["message"] = "Retry complete. Finalizing..."
        except Exception as retry_e:
            logger.error("Task %s retry failed: %s", task_id, retry_e)
            clean_err = str(retry_e).replace("ERROR: ", "")
            truncated = _truncate(clean_err, 150)
            if len(clean_err) > 150:
                tasks[task_id]["message"] = "Failed: " + truncated + "..."
            else:
                tasks[task_id]["message"] = "Failed: " + clean_err
            tasks[task_id]["error"] = str(retry_e)
            tasks[task_id]["status"] = "error"
            return

    # Success Handling
    try:
        # Wait a moment for file system to sync
        time.sleep(1)

        # Identify downloaded file with retries
        ready_files: List[str] = []
        for _ in range(3):
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
        {"status": "online", "service": "VidGetNow Backend", "version": "2.1.0"}
    )


@app.route("/status/test")
def status_test() -> Any:
    return jsonify({"status": "ok"}), 200


@app.route("/download", methods=["POST"])
def start_download() -> Any:
    data: Dict[str, Any] = request.json or {}
    url = str(data.get("url", ""))
    fmt = str(data.get("format", "video"))
    qual = str(data.get("quality", "best"))

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "id": task_id,
        "status": "queued",
        "progress": 0,
        "logs": [],
        "message": "Queued...",
        "created_at": time.time(),
    }

    threading.Thread(target=run_download, args=(url, task_id, fmt, qual)).start()

    # Always clean old files to prevent disk usage buildup
    threading.Thread(target=clean_old_files).start()

    return jsonify({"task_id": task_id})


@app.route("/status/<task_id>")
def get_status(task_id: str) -> Any:
    if task_id not in tasks:
        return jsonify({"status": "error", "message": "Task not found"}), 404
    return jsonify(tasks[task_id])


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
