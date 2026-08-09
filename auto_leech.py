"""
╔══════════════════════════════════════════════════════════════╗
║               AUTO LEECH MODULE — KabaAPI + LalamAsA         ║
║                                                              ║
║  Har 10 min mein KabaAPI call karta hai.                     ║
║  Naye posts ka mp4_url download karke                        ║
║  AUTO_LEECH_CHANNEL pe upload kar deta hai.                  ║
║  KabaAPI complete hone ke baad LalamAsA API call hoti hai.   ║
║  Thumbnail: API se directly | Duration: ffprobe              ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import asyncio
import logging
import time
import aiohttp
import tempfile

from pyrogram import Client
from motor.motor_asyncio import AsyncIOMotorClient

from config import DOWNLOAD_DIR, PROGRESS_UPDATE_INTERVAL, MAX_FILE_SIZE
from helpers import (
    human_size, format_eta, make_progress_bar,
    detect_media_type, extract_filename
)

# ─── Config ──────────────────────────────────────────────────────────────────

KABA_API_URL       = "https://kabaapi.tmrbotz.workers.dev/"
LALA_API_URL       = "https://lalamasa-api.tmrbotz.workers.dev/"
AUTO_LEECH_CHANNEL = int(os.environ.get("AUTO_LEECH_CHANNEL", "-1002205504138"))
POLL_INTERVAL      = 5 * 60        # 10 minutes
CHUNK_SIZE         = 1024 * 1024    # 1 MB
MONGO_URI          = os.environ.get("MONGO_URI", "")
MONGO_DB           = "kaba"
MONGO_COLLECTION   = "processed_posts"

log = logging.getLogger("AutoLeech")

DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Encoding": "identity",
}

# ─── MongoDB ─────────────────────────────────────────────────────────────────

_mongo_col = None

def get_mongo_col():
    global _mongo_col
    if _mongo_col is None:
        client     = AsyncIOMotorClient(MONGO_URI)
        _mongo_col = client[MONGO_DB][MONGO_COLLECTION]
    return _mongo_col


async def get_processed_ids(post_ids: list) -> set:
    col  = get_mongo_col()
    docs = await col.find(
        {"post_id": {"$in": post_ids}},
        {"post_id": 1, "_id": 0}
    ).to_list(length=None)
    return {doc["post_id"] for doc in docs}


async def mark_processed(post_id: str, title: str) -> None:
    col = get_mongo_col()
    await col.update_one(
        {"post_id": post_id},
        {"$set": {"post_id": post_id, "title": title}},
        upsert=True,
    )
    log.info(f"✅ MongoDB: marked [{post_id}]")


# ─── API Fetch ───────────────────────────────────────────────────────────────

async def fetch_new_posts(api_url: str) -> list:
    """
    API se posts fetch karo, duplicate filter karo.
    Returns: list of new posts
    """
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    log.warning(f"API [{api_url}]: HTTP {resp.status}")
                    return []
                data = await resp.json(content_type=None)
    except Exception as e:
        log.warning(f"API fetch error [{api_url}]: {e}")
        return []

    if not data.get("success"):
        log.warning(f"API [{api_url}]: success=false")
        return []

    posts = data.get("posts", [])
    if not posts:
        log.info(f"API [{api_url}]: koi post nahi mila")
        return []

    log.info(f"📋 API [{api_url}]: {len(posts)} posts mile")

    # MongoDB batch duplicate check
    all_ids       = [p["post_id"] for p in posts]
    processed_ids = await get_processed_ids(all_ids)
    log.info(f"📊 Already processed: {len(processed_ids)} | Naye: {len(all_ids) - len(processed_ids)}")

    new_posts = [p for p in posts if p["post_id"] not in processed_ids]
    return new_posts


# ─── Video Duration (ffprobe) ────────────────────────────────────────────────

async def get_video_duration(file_path: str) -> int:
    """ffprobe se duration nikalo — nahi hai to 0."""
    try:
        check = await asyncio.create_subprocess_exec(
            "ffprobe", "-version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(check.communicate(), timeout=5)
    except Exception:
        log.info("ffprobe not available — duration skip")
        return 0

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        duration_str = stdout.decode().strip()
        if duration_str:
            return int(float(duration_str))
    except Exception as e:
        log.warning(f"ffprobe error: {e}")
    return 0


# ─── Thumbnail Download ───────────────────────────────────────────────────────

async def download_thumbnail(thumb_url: str) -> str | None:
    """Thumbnail URL se image download karke temp file mein save karo."""
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(thumb_url, headers=DOWNLOAD_HEADERS) as resp:
                if resp.status != 200:
                    return None
                os.makedirs(DOWNLOAD_DIR, exist_ok=True)
                tmp = tempfile.NamedTemporaryFile(
                    delete=False, suffix=".jpg", dir=DOWNLOAD_DIR
                )
                tmp.write(await resp.read())
                tmp.close()
                log.info(f"🖼️ Thumbnail saved: {tmp.name}")
                return tmp.name
    except Exception as e:
        log.warning(f"Thumbnail download error: {e}")
        return None


# ─── MP4 Downloader ──────────────────────────────────────────────────────────

async def download_mp4(url: str, title: str, progress_cb=None):
    """
    mp4_url se file download karo.
    Returns: (file_path, filename, file_size)
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    timeout = aiohttp.ClientTimeout(connect=30, sock_read=300, total=None)

    async with aiohttp.ClientSession(
        headers=DOWNLOAD_HEADERS, timeout=timeout
    ) as session:
        async with session.get(url, allow_redirects=True) as resp:
            if resp.status not in (200, 206):
                raise Exception(f"HTTP {resp.status} — download fail")

            content_type = resp.headers.get("Content-Type", "video/mp4")
            content_disp = resp.headers.get("Content-Disposition", "")
            total_size   = int(resp.headers.get("Content-Length", 0))

            if total_size > MAX_FILE_SIZE:
                raise Exception(f"File too large: {human_size(total_size)}")

            filename  = extract_filename(str(resp.url), content_disp, content_type)
            # Prefix add karo
            name, ext = os.path.splitext(filename)
            filename  = f"[@NT_Hub] {name}{ext}"

            file_path = os.path.join(DOWNLOAD_DIR, filename)
            base, ext = os.path.splitext(file_path)
            counter = 1
            while os.path.exists(file_path):
                file_path = f"{base}_{counter}{ext}"
                counter += 1

            downloaded   = 0
            last_cb_time = 0.0

            with open(file_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    if downloaded > MAX_FILE_SIZE:
                        f.close()
                        os.remove(file_path)
                        raise Exception("File 2GB se zyada ho gayi!")

                    now = time.monotonic()
                    if progress_cb and (now - last_cb_time) >= 0:
                        last_cb_time = now
                        try:
                            await progress_cb(downloaded, total_size or downloaded)
                        except Exception:
                            pass

            if progress_cb:
                try:
                    await progress_cb(downloaded, downloaded)
                except Exception:
                    pass

            return file_path, filename, downloaded


# ─── Process One Post ─────────────────────────────────────────────────────────

async def process_post(client: Client, post: dict) -> bool:
    """
    Ek post ka mp4_url download karke channel pe upload karo.
    """
    post_id   = post["post_id"]
    title     = post["title"]
    mp4_url   = post.get("mp4_url", "")
    thumb_url = post.get("thumbnail", "")
    page_url  = post.get("page_url", "")

    if not mp4_url:
        log.warning(f"[{post_id}] mp4_url missing — skip")
        await mark_processed(post_id, title)
        return False

    log.info(f"🎬 Processing [{post_id}]: {title[:60]}")

    # Thumbnail download
    thumb_path = None
    if thumb_url:
        thumb_path = await download_thumbnail(thumb_url)

    # Status message
    try:
        status_msg = await client.send_message(
            chat_id=AUTO_LEECH_CHANNEL,
            text=(
                f"⏳ **Auto Leech Start...**\n\n"
                f"🎬 `{title}`\n"
            ),
        )
    except Exception as e:
        log.warning(f"Status message failed: {e}")
        status_msg = None

    start_time  = time.monotonic()
    file_path   = None
    last_update = [0.0]

    async def safe_edit(text: str):
        if status_msg:
            try:
                await status_msg.edit_text(text)
            except Exception:
                pass

    try:
        # ── PHASE 1: DOWNLOAD ───────────────────────────────────────────────
        dl_start = [time.monotonic()]

        async def on_dl_progress(downloaded: int, total: int):
            now = time.monotonic()
            if (now - last_update[0]) < PROGRESS_UPDATE_INTERVAL:
                return
            last_update[0] = now
            elapsed = now - dl_start[0]
            speed   = downloaded / elapsed if elapsed > 0 else 0
            eta     = (total - downloaded) / speed if speed > 0 and total > downloaded else 0
            bar     = make_progress_bar(downloaded, total)
            total_s = human_size(total) if total > 0 else "?"
            await safe_edit(
                f"⬇️ **Downloading...**\n\n"
                f"🎬 `{title}`\n\n"
                f"{bar}\n\n"
                f"📥 `{human_size(downloaded)}` / `{total_s}`\n"
                f"⚡ Speed: `{human_size(int(speed))}/s`\n"
                f"⏱️ ETA: `{format_eta(eta)}`"
            )

        dl_start[0] = time.monotonic()
        file_path, filename, file_size = await download_mp4(
            mp4_url, title, progress_cb=on_dl_progress
        )
        log.info(f"  ✅ Downloaded: {filename} ({human_size(file_size)})")

        # ── PHASE 2: DURATION ───────────────────────────────────────────────
        await safe_edit(
            f"🔍 **Duration check...**\n\n🎬 `{title}`"
        )
        duration = await get_video_duration(file_path)
        log.info(f"  ⏱️ Duration: {duration}s")

        # ── PHASE 3: UPLOAD ─────────────────────────────────────────────────
        last_update[0] = 0.0
        ul_start = [time.monotonic()]

        await safe_edit(
            f"⬆️ **Uploading...**\n\n"
            f"🎬 `{title}`\n"
            f"📦 {human_size(file_size)}"
        )

        async def on_ul_progress(current: int, total: int):
            now = time.monotonic()
            if (now - last_update[0]) < PROGRESS_UPDATE_INTERVAL:
                return
            last_update[0] = now
            elapsed = now - ul_start[0]
            speed   = current / elapsed if elapsed > 0 else 0
            eta     = (total - current) / speed if speed > 0 and total > current else 0
            bar     = make_progress_bar(current, total)
            await safe_edit(
                f"⬆️ **Uploading...**\n\n"
                f"🎬 `{title}`\n"
                f"📦 {human_size(file_size)}\n\n"
                f"{bar}\n\n"
                f"📤 `{human_size(current)}` / `{human_size(total)}`\n"
                f"⚡ Speed: `{human_size(int(speed))}/s`\n"
                f"⏱️ ETA: `{format_eta(eta)}`"
            )

        ul_start[0] = time.monotonic()

        caption = (
            f"🎬 **{title}**\n\n"
        )

        await client.send_video(
            chat_id=AUTO_LEECH_CHANNEL,
            video=file_path,
            caption=caption,
            thumb=thumb_path,
            duration=int(duration) if duration and duration > 0 else None,
            supports_streaming=True,
            progress=on_ul_progress,
        )

        elapsed = time.monotonic() - start_time

        # Status message delete karo
        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass

        log.info(f"  ✅ Uploaded in {elapsed:.1f}s")

        await mark_processed(post_id, title)
        return True

    except Exception as e:
        log.warning(f"  ❌ Failed [{post_id}]: {e}")
        await safe_edit(
            f"❌ **Failed!**\n\n"
            f"🎬 `{title}`\n\n"
            f"`{str(e)[:200]}`"
        )
        return False

    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        if thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass


# ─── Main Loop ────────────────────────────────────────────────────────────────

async def auto_leech_loop(client: Client):
    """Background task — har POLL_INTERVAL seconds mein dono APIs poll karta hai."""
    log.info(f"🤖 AutoLeech loop started — polling every {POLL_INTERVAL // 60} min")
    log.info(f"📢 Target channel: {AUTO_LEECH_CHANNEL}")

    # Bot ke start hone ka wait
    while not client.is_connected:
        log.info("⏳ Bot abhi start nahi hua — 2 sec wait...")
        await asyncio.sleep(2)
    log.info("✅ Bot connected — AutoLeech ready!")

    while True:
        try:
            # ── STEP 1: KabaAPI ─────────────────────────────────────────────
            log.info("🔄 KabaAPI poll kar raha hoon...")
            kaba_posts = await fetch_new_posts(KABA_API_URL)

            if kaba_posts:
                log.info(f"🆕 KabaAPI: {len(kaba_posts)} naye post(s) mile")
                for post in kaba_posts:
                    await process_post(client, post)
                    await asyncio.sleep(10)
            else:
                log.info("KabaAPI: koi naya post nahi mila")

            # ── STEP 2: LalamAsA API (KabaAPI complete hone ke baad) ────────
            log.info("🔄 LalamAsA API poll kar raha hoon...")
            lala_posts = await fetch_new_posts(LALA_API_URL)

            if lala_posts:
                log.info(f"🆕 LalamAsA: {len(lala_posts)} naye post(s) mile")
                for post in lala_posts:
                    await process_post(client, post)
                    await asyncio.sleep(10)
            else:
                log.info("LalamAsA: koi naya post nahi mila")

        except Exception as e:
            log.exception(f"AutoLeech loop error (continuing): {e}")

        log.info(f"💤 Next poll in {POLL_INTERVAL // 60} min...")
        await asyncio.sleep(POLL_INTERVAL)
