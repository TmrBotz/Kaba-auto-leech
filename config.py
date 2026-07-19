"""
╔══════════════════════════════════════════╗
║       URL UPLOADER BOT - CONFIG          ║
║       Engine: WZGram (MTProto)           ║
╚══════════════════════════════════════════╝

Yahan apna API_ID, API_HASH aur BOT_TOKEN dalo.
"""

import os

# ─── Telegram API Credentials ───────────────────────────────────────────────
# https://my.telegram.org se lo
API_ID   = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")

# @BotFather se lo
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# ─── Download Settings ──────────────────────────────────────────────────────
DOWNLOAD_DIR   = "./downloads"          # Files kahan save hongi
MAX_FILE_SIZE  = 2 * 1024 * 1024 * 1024  # 2 GB (free limit)

# ─── Progress Update Interval (seconds) ────────────────────────────────────
PROGRESS_UPDATE_INTERVAL = 4   # Har 4 second mein progress update

# ─── Supported Media Extensions ────────────────────────────────────────────
VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv",
    ".flv", ".webm", ".m4v", ".3gp", ".ts",
    ".mpeg", ".mpg", ".m2ts", ".mts"
}

AUDIO_EXTENSIONS = {
    ".mp3", ".flac", ".aac", ".ogg", ".wav",
    ".m4a", ".opus", ".wma", ".aiff", ".alac",
    ".ape", ".mka"
}

PHOTO_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp",
    ".bmp", ".tiff", ".tif"
}

# GIF alag handle hoga (animation)
GIF_EXTENSIONS = {".gif"}
