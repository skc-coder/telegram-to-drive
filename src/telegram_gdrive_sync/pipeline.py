import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Any, List

from .config import Config
from .disk_guard import DiskGuard
from .index_db import IndexDB
from .rclone_uploader import RcloneUploader
from .tg_client import TelegramDownloader
from .ui import MultiProgressUI

logger = logging.getLogger("telegram_gdrive_sync")

class SyncPipeline:
    def __init__(self, config: Config):
        self.config = config
        self.disk_guard = DiskGuard(config.temp_download_dir, config.min_free_disk_gb)
        self.uploader = RcloneUploader(config.rclone_remote, config.rclone_remote_folder, config.max_upload_speed)
        self.downloader = TelegramDownloader(
            int(config.api_id),
            config.api_hash,
            config.phone_number,
            Path(".state")
        )
        self.ui = MultiProgressUI(config.download_workers, config.upload_workers)

    async def run(self):
        logger.info("Initializing Telegram client connection...")
        await self.downloader.connect()
        self.ui.start()

        try:
            for key, channel_link in list(self.config.channels):
                await self.process_channel(key, channel_link)
        finally:
            self.ui.stop()
            await self.downloader.disconnect()

    async def process_channel(self, channel_key: str, channel_link: str):
        try:
            entity, folder_name = await self.downloader.resolve_entity(channel_link)
        except Exception as e:
            logger.error(f"Failed to resolve channel entity for {channel_link}: {e}")
            return

        self.ui.set_channel(folder_name)
        index_db = IndexDB(Path(".state"), str(getattr(entity, 'id', folder_name)))

        # Clean up any leftover incomplete .tmp files or orphan downloads for this channel
        channel_temp_dir = self.config.temp_download_dir / folder_name
        channel_temp_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_temp(channel_temp_dir, index_db)

        # Queues for producer (downloads) -> consumer (uploads)
        upload_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

        # Slot semaphore pools
        dl_slots = asyncio.Queue()
        for i in range(self.config.download_workers):
            await dl_slots.put(i)

        ul_slots = asyncio.Queue()
        for i in range(self.config.upload_workers):
            await ul_slots.put(i)

        # Start consumer task workers for uploading
        upload_workers = []
        for _ in range(self.config.upload_workers):
            task = asyncio.create_task(self._upload_consumer(upload_queue, ul_slots, folder_name, index_db))
            upload_workers.append(task)

        # Producer: Fetch messages from channel and trigger parallel downloads
        try:
            async for msg in self.downloader.client.iter_messages(entity, reverse=True):
                if not msg.media:
                    continue

                msg_id = msg.id
                # Check if already uploaded
                if index_db.is_already_uploaded(msg_id):
                    continue

                # Get media attributes / filename
                file_name = self._get_message_filename(msg, folder_name)
                if not file_name:
                    continue

                # Neev 2026 subject filtering (sst, science, hindi, maths, english only)
                if "neev" in folder_name.lower():
                    text_context = (msg.text or "") + " " + file_name
                    allowed_keywords = ["sst", "science", "physics", "chemistry", "biology", "hindi", "math", "maths", "english"]
                    disallowed_keywords = ["sanskrit", "computer science", "information technology", "ai", "artificial intelligence"]
                    
                    text_lower = text_context.lower()
                    if any(dk in text_lower for dk in disallowed_keywords):
                        logger.info(f"Skipping disallowed subject file: {file_name}")
                        continue
                    if not any(ak in text_lower for ak in allowed_keywords):
                        logger.info(f"Skipping unlisted subject file: {file_name}")
                        continue

                # Skip GIFs (mime type image/gif or .gif extension)
                is_gif = False
                if getattr(msg, 'file', None) and getattr(msg.file, 'mime_type', None) == 'image/gif':
                    is_gif = True
                elif Path(file_name).suffix.lower() == '.gif':
                    is_gif = True
                if is_gif:
                    logger.debug(f"Skipping GIF file: {file_name}")
                    continue

                # Extension filtering check
                ext = Path(file_name).suffix.lower()
                if self.config.allowed_extensions and ext not in self.config.allowed_extensions:
                    continue

                file_size = getattr(msg.media, 'document', None)
                total_bytes = file_size.size if file_size else 0

                local_dest = channel_temp_dir / file_name

                # Storage disk guard check: Wait if free disk space is lower than threshold
                while not self.disk_guard.has_sufficient_space(total_bytes):
                    logger.warning(f"Disk space low ({self.disk_guard.get_free_gb():.2f} GB free). Pausing downloads until uploads clear space...")
                    await asyncio.sleep(5)

                # Acquire download slot
                slot_id = await dl_slots.get()
                
                # Spawn parallel download task
                asyncio.create_task(
                    self._download_producer_task(
                        msg, msg_id, file_name, total_bytes, local_dest, slot_id, dl_slots, upload_queue, index_db
                    )
                )

            # Wait for all producer tasks to complete putting items into upload_queue
            await dl_slots.join() if hasattr(dl_slots, 'join') else None
        except Exception as e:
            logger.error(f"Error fetching channel messages: {e}")

        # Signal upload workers to finish when queue is empty
        await upload_queue.join()
        for w in upload_workers:
            w.cancel()
        await asyncio.gather(*upload_workers, return_exceptions=True)

        # Mark channel as completed in config.ini
        logger.info(f"Channel '{folder_name}' sync completed! Moving from [channels] to [completed_channels] in config.ini")
        self.config.mark_channel_completed(channel_key, channel_link)

    async def _download_producer_task(
        self, msg, msg_id: int, file_name: str, total_bytes: int,
        local_dest: Path, slot_id: int, dl_slots: asyncio.Queue,
        upload_queue: asyncio.Queue, index_db: IndexDB
    ):
        try:
            # Check if file was already downloaded locally previously
            if not local_dest.exists() or local_dest.stat().st_size != total_bytes:
                index_db.mark_download_start(msg_id, file_name, total_bytes, str(local_dest))
                self.ui.add_download_task(slot_id, file_name, total_bytes)

                def _prog_cb(cur, tot):
                    self.ui.update_download_task(slot_id, cur)

                # Download with retries
                retries = 0
                while True:
                    try:
                        await self.downloader.download_media(msg, local_dest, _prog_cb)
                        break
                    except Exception as err:
                        retries += 1
                        if "file reference has expired" in str(err).lower() or "filereferenceexpirederror" in type(err).__name__.lower():
                            try:
                                logger.info(f"File reference expired for {file_name} (msg_id {msg_id}). Refetching message from channel...")
                                msg = await self.downloader.client.get_messages(msg.peer_id, ids=msg_id)
                            except Exception as re_err:
                                logger.warning(f"Could not refetch message {msg_id}: {re_err}")
                        
                        if retries >= self.config.max_retries:
                            raise err
                        logger.warning(f"Download retry {retries}/{self.config.max_retries} for {file_name}: {err}")
                        await asyncio.sleep(2 * retries)

                index_db.mark_downloaded(msg_id, str(local_dest))
            else:
                index_db.mark_downloaded(msg_id, str(local_dest))

            # Hand off item to upload queue for consumer
            await upload_queue.put({
                "msg_id": msg_id,
                "file_name": file_name,
                "local_path": local_dest,
                "total_bytes": total_bytes
            })
        except Exception as e:
            logger.error(f"Failed to download msg_id {msg_id} ({file_name}): {e}")
            index_db.mark_error(msg_id, "download", str(e))
        finally:
            self.ui.remove_download_task(slot_id)
            await dl_slots.put(slot_id)

    async def _upload_consumer(
        self, upload_queue: asyncio.Queue, ul_slots: asyncio.Queue,
        folder_name: str, index_db: IndexDB
    ):
        while True:
            item = await upload_queue.get()
            slot_id = await ul_slots.get()
            
            msg_id = item["msg_id"]
            local_path: Path = item["local_path"]
            file_name = item["file_name"]
            total_bytes = item["total_bytes"]

            try:
                self.ui.add_upload_task(slot_id, file_name, total_bytes)

                def _ul_prog_cb(cur, tot, speed, eta):
                    self.ui.update_upload_task(slot_id, cur, tot, speed, eta)

                # Execute rclone upload (move)
                remote_path = await self.uploader.upload_file(local_path, folder_name, _ul_prog_cb)
                index_db.mark_uploaded(msg_id, remote_path)
            except Exception as e:
                logger.error(f"Failed to upload msg_id {msg_id} ({file_name}): {e}")
                index_db.mark_error(msg_id, "upload", str(e))
            finally:
                self.ui.remove_upload_task(slot_id)
                await ul_slots.put(slot_id)
                upload_queue.task_done()

    def _get_message_filename(self, msg, channel_name: str = "") -> Optional[str]:
        name = None
        if getattr(msg, 'file', None) and getattr(msg.file, 'name', None):
            name = msg.file.name
        elif getattr(msg.media, 'document', None):
            for attr in msg.media.document.attributes:
                if hasattr(attr, 'file_name') and attr.file_name:
                    name = attr.file_name
                    break
        if not name:
            name = f"media_{msg.id}"
        
        import re
        rule = self.config.name_rules.get(channel_name.strip().lower(), self.config.name_rules.get("default", "clean_prefix"))

        if rule == "module_number_only":
            mod_match = re.match(r'^Module[_\s]*(\d+)[_\s]*[^/]*?(?=(Lecture|Annotated|OPTIONAL))', name, re.IGNORECASE)
            if mod_match:
                mod_num = mod_match.group(1)
                rest = name[mod_match.end():]
                cleaned_name = f"Module {mod_num} {rest}".strip()
            else:
                match = re.search(r'(Annotated Notes\b.*|Annotated_No\b.*|Annotated_Notes\b.*|Annotated\b.*|Lecture\b.*|OPTIONAL\b.*)', name, re.IGNORECASE)
                if match:
                    cleaned_name = match.group(1)
                else:
                    cleaned_name = re.sub(r'^\d*_\(?[^)]*?\)?\s*', '', name)
        else:
            # clean_prefix rule
            match = re.search(r'(Annotated Notes\b.*|Annotated_No\b.*|Annotated_Notes\b.*|Annotated\b.*|Lecture\b.*|OPTIONAL\b.*)', name, re.IGNORECASE)
            if match:
                cleaned_name = match.group(1)
            else:
                cleaned_name = re.sub(r'^\d*_\(?[^)]*?\)?\s*', '', name)

        return cleaned_name if cleaned_name else name

    def _cleanup_temp(self, temp_dir: Path, index_db: IndexDB):
        if not temp_dir.exists():
            return
        for item in temp_dir.glob("*"):
            if item.suffix == ".tmp":
                try:
                    item.unlink()
                except Exception:
                    pass
