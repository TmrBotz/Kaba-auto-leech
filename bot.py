"""
╔═══════════════════════════════════════════════════════╗
║          URL UPLOADER BOT — MAIN                      ║
║                                                       ║
║  Framework : WZGram (MTProto, Rust-powered crypto)    ║
║  Engine    : Direct MTProto upload (no Bot API)       ║
║  Limit     : 2 GB (free, no String Session needed)    ║
╚═══════════════════════════════════════════════════════╝
"""

import os
import time
import asyncio
import logging
from aiohttp import web

from pyrogram import Client, filters
from pyrogram.types import Message

from config import (
    API_ID, API_HASH, BOT_TOKEN,
    DOWNLOAD_DIR, PROGRESS_UPDATE_INTERVAL
)
from downloader  import download_url, DownloadError
from uploader    import upload_media
from auto_leech  import auto_leech_loop
from helpers     import (
    is_valid_url, make_progress_bar,
    human_size, format_eta
)


# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("URLUploaderBot")


# ─── Bot Client (Bot Token se — String Session ki zaroorat NAHI) ───────────
bot = Client(
    name="url_uploader_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=".sessions",          # Session file yahan save hogi
)


# ════════════════════════════════════════════════════════
#  COMMANDS
# ════════════════════════════════════════════════════════

@bot.on_message(filters.command("start") & filters.private)
async def cmd_start(client: Client, message: Message):
    await message.reply_text(
        "🤖 **URL Uploader Bot**\n\n"
        "Koi bhi **direct download link** bhejo — main file\n"
        "download karke **media format** mein upload kar dunga!\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎬 **Video** → mp4, mkv, avi, mov, webm ...\n"
        "🎵 **Audio** → mp3, flac, aac, ogg, m4a ...\n"
        "🖼️ **Photo** → jpg, png, webp, bmp ...\n"
        "🎞️ **GIF**   → gif (animation)\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ **Max Size:** 2 GB (Free)\n\n"
        "/help — Detailed help dekho",
    )


@bot.on_message(filters.command("help") & filters.private)
async def cmd_help(client: Client, message: Message):
    await message.reply_text(
        "📖 **URL Uploader Bot — Help**\n\n"
        "**Kaise use karein:**\n"
        "1. Bot ko direct download URL bhejo\n"
        "2. Bot download progress dikhayega\n"
        "3. File Telegram pe media ke roop mein aayegi\n\n"
        "**✅ Kya kaam karta hai:**\n"
        "• `http://` aur `https://` links\n"
        "• Redirect wale links (auto-follow)\n"
        "• Content-Disposition wali files\n"
        "• Sabhi common media formats\n\n"
        "**❌ Kya kaam NAHI karta:**\n"
        "• YouTube / Google Drive / Mega links\n"
        "• Login-required pages\n"
        "• 2 GB se zyada files\n"
        "• HLS/DASH streams\n\n"
        "**Commands:**\n"
        "/start — Bot ke baare mein\n"
        "/help  — Ye message\n"
        "/cancel — Chal raha download rok do",
    )


@bot.on_message(filters.command("cancel") & filters.private)
async def cmd_cancel(client: Client, message: Message):
    # Simple cancel notice (advanced task cancellation neeche dekho)
    await message.reply_text(
        "⚠️ Abhi koi active download nahi hai.\n"
        "Ek URL bhejo phir dobara try karo.",
    )


# ════════════════════════════════════════════════════════
#  MAIN URL HANDLER
# ════════════════════════════════════════════════════════

@bot.on_message(
    filters.text
    & filters.private
    & ~filters.command(["start", "help", "cancel"])
)
async def url_handler(client: Client, message: Message):
    url = message.text.strip()

    # ── URL validation ───────────────────────────────────────────────────────
    if not is_valid_url(url):
        await message.reply_text(
            "❌ **Invalid URL!**\n\n"
            "Sirf `http://` ya `https://` links bhejo.",
        )
        return

    # ── Status message ───────────────────────────────────────────────────────
    status = await message.reply_text(
        "⏳ **URL check ho raha hai...**",
    )

    start_time = time.monotonic()
    file_path  = None

    try:
        # ────────────────────────────────────────────────────────────────────
        #  PHASE 1 — DOWNLOAD
        # ────────────────────────────────────────────────────────────────────

        last_update   = [0.0]
        dl_start_time = [time.monotonic()]

        async def on_download_progress(downloaded: int, total: int):
            now = time.monotonic()
            if (now - last_update[0]) < PROGRESS_UPDATE_INTERVAL:
                return
            last_update[0] = now

            elapsed = now - dl_start_time[0]
            speed   = downloaded / elapsed if elapsed > 0 else 0
            eta_sec = (total - downloaded) / speed if speed > 0 and total > downloaded else 0

            bar = make_progress_bar(downloaded, total)
            total_str = human_size(total) if total > 0 else "?"

            try:
                await status.edit_text(
                    f"⬇️ **Downloading...**\n\n"
                    f"{bar}\n\n"
                    f"📥 `{human_size(downloaded)}` / `{total_str}`\n"
                    f"⚡ Speed: `{human_size(int(speed))}/s`\n"
                    f"⏱️ ETA: `{format_eta(eta_sec)}`"
                )
            except Exception:
                pass

        dl_start_time[0] = time.monotonic()

        await status.edit_text("⬇️ **Download shuru ho raha hai...**")

        file_path, filename, content_type, file_size = await download_url(
            url,
            progress_cb=on_download_progress,
        )

        log.info(f"Downloaded: {filename} ({human_size(file_size)})")

        # ────────────────────────────────────────────────────────────────────
        #  PHASE 2 — UPLOAD
        # ────────────────────────────────────────────────────────────────────

        last_update[0]   = 0.0
        ul_start_time    = [time.monotonic()]

        await status.edit_text(
            f"⬆️ **Upload ho raha hai...**\n\n"
            f"📁 `{filename}`\n"
            f"📦 {human_size(file_size)}"
        )

        async def on_upload_progress(current: int, total: int):
            now = time.monotonic()
            if (now - last_update[0]) < PROGRESS_UPDATE_INTERVAL:
                return
            last_update[0] = now

            elapsed = now - ul_start_time[0]
            speed   = current / elapsed if elapsed > 0 else 0
            eta_sec = (total - current) / speed if speed > 0 and total > current else 0

            bar = make_progress_bar(current, total)

            try:
                await status.edit_text(
                    f"⬆️ **Uploading...**\n\n"
                    f"{bar}\n\n"
                    f"📤 `{human_size(current)}` / `{human_size(total)}`\n"
                    f"⚡ Speed: `{human_size(int(speed))}/s`\n"
                    f"⏱️ ETA: `{format_eta(eta_sec)}`"
                )
            except Exception:
                pass

        ul_start_time[0] = time.monotonic()

        await upload_media(
            client=client,
            message=message,
            file_path=file_path,
            filename=filename,
            content_type=content_type,
            file_size=file_size,
            source_url=url,
            progress_cb=on_upload_progress,
        )

        # ── Done ──────────────────────────────────────────────────────────
        total_elapsed = time.monotonic() - start_time
        await status.edit_text(
            f"✅ **Kaam ho gaya!**\n\n"
            f"⏱️ Total time: `{format_eta(total_elapsed)}`"
        )

        log.info(f"Upload complete: {filename} in {total_elapsed:.1f}s")

    # ── Error Handling ────────────────────────────────────────────────────────
    except DownloadError as e:
        log.warning(f"Download error: {e}")
        await status.edit_text(
            f"❌ **Download Error!**\n\n`{e}`\n\n"
            "Direct download link check karo aur dobara try karo."
        )

    except Exception as e:
        log.exception(f"Unexpected error: {e}")
        await status.edit_text(
            f"⚠️ **Unexpected Error!**\n\n`{str(e)[:300]}`"
        )

    finally:
        # ── Cleanup: downloaded file hatao ────────────────────────────────
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                log.info(f"Cleaned up: {file_path}")
            except Exception as e:
                log.warning(f"Cleanup failed: {e}")


# ════════════════════════════════════════════════════════
#  STARTUP
# ════════════════════════════════════════════════════════

# ─── Health Check Server (Render port fix) ─────────────────────────────────

async def health_server():
    """
    Render ko port chahiye — ye simple HTTP server bas
    200 OK deta hai. Bot ke saath parallel chalta hai.
    """
    async def handle(request):
        return web.Response(text="✅ URL Uploader Bot is alive!")

    app    = web.Application()
    app.router.add_get("/", handle)
    app.router.add_get("/health", handle)

    port   = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site   = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log.info(f"🌐 Health server running on port {port}")


async def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(".sessions",   exist_ok=True)
    log.info("🚀 URL Uploader Bot starting...")
    log.info(f"📁 Download dir: {os.path.abspath(DOWNLOAD_DIR)}")
    log.info("⚡ WZGram MTProto engine (WarpCrypto/Rust) active.")

    # Bot + Health server + AutoLeech — teeno saath chalao
    await asyncio.gather(
        health_server(),
        _run_bot(),
        auto_leech_loop(bot),
    )


async def _run_bot():
    await bot.start()
    me = await bot.get_me()
    log.info(f"✅ Bot live: @{me.username} (ID: {me.id})")
    log.info("📨 URLs ka intezaar hai...")
    # Forever wait
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
