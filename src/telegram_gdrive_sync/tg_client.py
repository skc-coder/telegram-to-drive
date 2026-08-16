import asyncio
import os
import logging
from pathlib import Path
from typing import Optional, Callable
from telethon import TelegramClient
from telethon.tl.types import Message, Document, Channel, Chat

logger = logging.getLogger("telegram_gdrive_sync")

class TelegramDownloader:
    def __init__(self, api_id: int, api_hash: str, phone_number: str, session_dir: Path):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        session_path = str(self.session_dir / "tg_session")
        
        self.client = TelegramClient(session_path, self.api_id, self.api_hash)

    async def connect(self):
        await self.client.connect()
        if not await self.client.is_user_authorized():
            logger.info("Telegram client not authorized. Starting authentication prompt...")
            if self.phone_number and self.phone_number != "YOUR_PHONE_NUMBER":
                await self.client.start(phone=self.phone_number)
            else:
                await self.client.start()

    async def disconnect(self):
        await self.client.disconnect()

    async def resolve_entity(self, channel_link: str):
        # Extract channel link username or ID
        link_str = channel_link.strip()
        if "#" in link_str:
            # Handle web.telegram.org link e.g. https://web.telegram.org/k/#-2377806273
            parts = link_str.split("#")
            channel_id_str = parts[-1].strip()
            if channel_id_str.startswith("-100"):
                entity_id = int(channel_id_str)
            elif channel_id_str.startswith("-"):
                # Append -100 for supergroups/channels
                entity_id = int(f"-100{channel_id_str[1:]}")
            else:
                try:
                    entity_id = int(channel_id_str)
                except ValueError:
                    entity_id = channel_id_str
            entity = await self.client.get_entity(entity_id)
        else:
            entity = await self.client.get_entity(link_str)

        title = getattr(entity, 'title', None) or getattr(entity, 'first_name', str(channel_link))
        # Make a safe folder name for Google Drive
        safe_folder_name = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in title).strip()
        return entity, safe_folder_name

    async def download_media(
        self,
        message: Message,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Path:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Telethon progress callback signature: (current, total)
        def _cb(cur, tot):
            if progress_callback:
                progress_callback(cur, tot)

        result_file = await self.client.download_media(
            message.media,
            file=str(dest_path),
            progress_callback=_cb
        )
        return Path(result_file)
