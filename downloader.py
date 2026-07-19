"""
URL Uploader Bot — Download Engine
Async file downloader with real-time progress reporting.
"""

import os
import time
import asyncio
import aiohttp
from typing import Callable, Optional, Tuple

from config import DOWNLOAD_DIR, MAX_FILE_SIZE
from helpers import human_size, extract_filename


# HTTP request headers (common browser UA to avoid blocks)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Encoding": "identity",   # No compression — byte count sahi rahe
}

CHUNK_SIZE = 1024 * 1024        # 1 MB per chunk
CONNECT_TIMEOUT = 30            # seconds
READ_TIMEOUT    = 300           # 5 min (slow servers ke liye)


class DownloadError(Exception):
    """Custom exception for download failures"""
    pass


async def download_url(
    url: str,
    progress_cb: Optional[Callable] = None,
) -> Tuple[str, str, str, int]:
    """
    URL se file download karo.

    Args:
        url:         Direct download URL
        progress_cb: async callback(downloaded_bytes, total_bytes)

    Returns:
        Tuple of (file_path, filename, content_type, total_bytes)

    Raises:
        DownloadError on any failure
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    timeout = aiohttp.ClientTimeout(
        connect=CONNECT_TIMEOUT,
        sock_read=READ_TIMEOUT,
        total=None,               # Total timeout nahi — bade files ke liye
    )

    try:
        async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout) as session:
            async with session.get(url, allow_redirects=True) as resp:

                # ── Status check ──────────────────────────────────────────
                if resp.status == 403:
                    raise DownloadError("403 Forbidden — Server ne access deny kar diya.")
                if resp.status == 404:
                    raise DownloadError("404 Not Found — URL exist nahi karta.")
                if resp.status not in (200, 206):
                    raise DownloadError(f"HTTP Error {resp.status} — Download fail hua.")

                # ── File info ──────────────────────────────────────────────
                content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()
                content_disp = resp.headers.get("Content-Disposition", "")
                total_size   = int(resp.headers.get("Content-Length", 0))

                # Size limit check
                if total_size > MAX_FILE_SIZE:
                    raise DownloadError(
                        f"File bahut bada hai!\n"
                        f"File size: {human_size(total_size)}\n"
                        f"Maximum allowed: {human_size(MAX_FILE_SIZE)}"
                    )

                filename  = extract_filename(str(resp.url), content_disp, content_type)
                file_path = os.path.join(DOWNLOAD_DIR, filename)

                # Duplicate name handle karo
                base, ext = os.path.splitext(file_path)
                counter   = 1
                while os.path.exists(file_path):
                    file_path = f"{base}_{counter}{ext}"
                    counter  += 1

                # ── Download loop ──────────────────────────────────────────
                downloaded   = 0
                last_cb_time = 0.0

                with open(file_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)

                        # Runtime size check (agar Content-Length nahi tha)
                        if downloaded > MAX_FILE_SIZE:
                            f.close()
                            os.remove(file_path)
                            raise DownloadError(
                                f"File size 2GB se zyada ho gayi! Download rok diya."
                            )

                        # Progress callback (throttled)
                        now = time.monotonic()
                        if progress_cb and (now - last_cb_time) >= 0:
                            last_cb_time = now
                            try:
                                await progress_cb(downloaded, total_size or downloaded)
                            except Exception:
                                pass  # Progress error se download nahi rokna

                # Final progress call (100%)
                if progress_cb:
                    try:
                        await progress_cb(downloaded, downloaded)
                    except Exception:
                        pass

                return file_path, filename, content_type, downloaded

    except aiohttp.ClientConnectorError as e:
        raise DownloadError(f"Connection fail hua: {e}")
    except aiohttp.InvalidURL:
        raise DownloadError("Invalid URL — check karo aur dobara try karo.")
    except asyncio.TimeoutError:
        raise DownloadError("Timeout! Server ne response nahi diya.")
    except DownloadError:
        raise
    except Exception as e:
        raise DownloadError(f"Unknown error: {e}")
