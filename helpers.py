"""
URL Uploader Bot — Helper Functions
"""

import os
import math
import mimetypes
import time
from urllib.parse import urlparse, unquote

from config import (
    VIDEO_EXTENSIONS, AUDIO_EXTENSIONS,
    PHOTO_EXTENSIONS, GIF_EXTENSIONS
)


# ─── Size Formatter ─────────────────────────────────────────────────────────

def human_size(size_bytes: int) -> str:
    """Bytes ko human-readable format mein convert karo"""
    if size_bytes <= 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    i = min(i, len(units) - 1)
    val = size_bytes / (1024 ** i)
    return f"{val:.2f} {units[i]}"


# ─── Time Formatter ─────────────────────────────────────────────────────────

def format_eta(seconds: float) -> str:
    """ETA ko readable format mein dikhao"""
    if seconds <= 0 or seconds == float("inf"):
        return "..."
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}m {s}s"
    else:
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h}h {m}m {s}s"


# ─── Progress Bar ───────────────────────────────────────────────────────────

def make_progress_bar(current: int, total: int, length: int = 18) -> str:
    """Telegram-friendly progress bar banao"""
    if total <= 0:
        return "░" * length
    percent = min(current / total, 1.0)
    filled  = int(percent * length)
    bar     = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {percent * 100:.1f}%"


# ─── File Type Detector ─────────────────────────────────────────────────────

def detect_media_type(content_type: str = "", filename: str = "") -> str:
    """
    Content-Type ya filename se media type detect karo.
    Returns: 'video' | 'audio' | 'photo' | 'gif' | 'document'
    """
    ct = content_type.lower()

    # Content-Type se check
    if "video" in ct:
        return "video"
    if "audio" in ct or "ogg" in ct:
        return "audio"
    if "image/gif" in ct:
        return "gif"
    if "image" in ct:
        return "photo"

    # Extension se check
    ext = os.path.splitext(filename)[1].lower()
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    if ext in GIF_EXTENSIONS:
        return "gif"
    if ext in PHOTO_EXTENSIONS:
        return "photo"

    # MIME guess
    guessed_mime, _ = mimetypes.guess_type(filename)
    if guessed_mime:
        if "video" in guessed_mime:
            return "video"
        if "audio" in guessed_mime:
            return "audio"
        if "image/gif" in guessed_mime:
            return "gif"
        if "image" in guessed_mime:
            return "photo"

    return "document"


# ─── Filename Extractor ─────────────────────────────────────────────────────

def extract_filename(url: str, content_disposition: str = "", content_type: str = "") -> str:
    """URL ya headers se filename nikalo"""

    # Content-Disposition se try karo
    if content_disposition:
        for part in content_disposition.split(";"):
            part = part.strip()
            if part.startswith("filename*="):
                fname = part.split("=", 1)[1].strip()
                if "''" in fname:
                    fname = fname.split("''", 1)[1]
                return unquote(fname)
            elif part.startswith('filename="'):
                return part.split('"')[1]
            elif part.startswith("filename="):
                return unquote(part.split("=", 1)[1].strip("'\""))

    # URL path se nikalo
    parsed = urlparse(url)
    path   = parsed.path
    fname  = unquote(os.path.basename(path))

    if fname and "." in fname:
        return fname

    # Extension guess karo
    ext = ""
    if content_type:
        ct = content_type.split(";")[0].strip()
        guessed = mimetypes.guess_extension(ct)
        if guessed:
            ext = guessed

    return f"downloaded_file{ext or '.bin'}"


# ─── URL Validator ──────────────────────────────────────────────────────────

def is_valid_url(url: str) -> bool:
    """Basic URL validation"""
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False
