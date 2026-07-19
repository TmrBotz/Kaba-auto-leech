"""
URL Uploader Bot — Upload Engine
Media ko Telegram pe MTProto se upload karo (no Bot API limit).
"""

import os
from typing import Callable, Optional

from pyrogram import Client
from pyrogram.types import Message

from helpers import detect_media_type, human_size


async def upload_media(
    client: Client,
    message: Message,
    file_path: str,
    filename: str,
    content_type: str,
    file_size: int,
    source_url: str,
    progress_cb: Optional[Callable] = None,
) -> None:
    """
    File ko detect karke sahi media type mein upload karo.

    - Video  → send_video  (stream support ke saath)
    - Audio  → send_audio
    - GIF    → send_animation
    - Photo  → send_photo
    - Baaki  → send_document (fallback)
    """

    media_type = detect_media_type(content_type, filename)
    short_url  = source_url[:60] + ("..." if len(source_url) > 60 else "")

    caption = (
        f"✅ **Upload Complete!**\n\n"
        f"📁 **File:** `{filename}`\n"
        f"📦 **Size:** {human_size(file_size)}\n"
        f"🎞️ **Type:** {media_type.capitalize()}\n"
        f"🔗 **Source:** `{short_url}`"
    )

    # Common kwargs
    common = dict(
        chat_id=message.chat.id,
        caption=caption,
        reply_to_message_id=message.id,
        progress=progress_cb,
    )

    # ── Send based on type ─────────────────────────────────────────────────
    if media_type == "video":
        await client.send_video(
            video=file_path,
            supports_streaming=True,    # Telegram player mein stream ho
            **common,
        )

    elif media_type == "audio":
        await client.send_audio(
            audio=file_path,
            **common,
        )

    elif media_type == "gif":
        await client.send_animation(
            animation=file_path,
            **common,
        )

    elif media_type == "photo":
        await client.send_photo(
            photo=file_path,
            caption=caption,
            reply_to_message_id=message.id,
            progress=progress_cb,
        )

    else:
        # Unknown type → document ke roop mein bhejo
        await client.send_document(
            document=file_path,
            file_name=filename,
            force_document=False,     # Telegram khud best format choose kare
            **common,
        )
