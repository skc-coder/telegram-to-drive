import configparser
import os
from pathlib import Path

class Config:
    def __init__(self, config_path="config.ini"):
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found at {self.config_path.absolute()}")
        
        self.parser = configparser.ConfigParser()
        self.parser.read(self.config_path)

        # Telegram
        self.api_id = self.parser.get("telegram", "api_id", fallback="")
        self.api_hash = self.parser.get("telegram", "api_hash", fallback="")
        self.phone_number = self.parser.get("telegram", "phone_number", fallback="")

        # Rclone
        self.rclone_remote = self.parser.get("rclone", "remote_name", fallback="gdrive")
        self.rclone_remote_folder = self.parser.get("rclone", "remote_folder", fallback="Telegram_Downloads")
        self.max_upload_speed = self.parser.get("rclone", "max_upload_speed", fallback="0")

        # Settings
        self.temp_download_dir = Path(self.parser.get("settings", "temp_download_dir", fallback="/mnt/storage/telegram_downloads"))
        self.download_workers = int(self.parser.get("settings", "download_workers", fallback="3"))
        self.upload_workers = int(self.parser.get("settings", "upload_workers", fallback="3"))
        self.min_free_disk_gb = float(self.parser.get("settings", "min_free_disk_gb", fallback="5.0"))
        self.max_retries = int(self.parser.get("settings", "max_retries", fallback="5"))
        self.max_download_speed_kb = int(self.parser.get("settings", "max_download_speed_kb", fallback="0"))
        
        allowed = self.parser.get("settings", "allowed_extensions", fallback="all").strip()
        if allowed.lower() == "all" or not allowed:
            self.allowed_extensions = None
        else:
            self.allowed_extensions = set(ext.strip().lower() for ext in allowed.split(","))

        # Channels list
        self.channels = []
        if self.parser.has_section("channels"):
            for _, val in self.parser.items("channels"):
                val = val.strip()
                if val:
                    self.channels.append(val)

    def validate(self):
        if not self.api_id or self.api_id == "YOUR_API_ID":
            raise ValueError("Please configure a valid telegram 'api_id' in config.ini")
        if not self.api_hash or self.api_hash == "YOUR_API_HASH":
            raise ValueError("Please configure a valid telegram 'api_hash' in config.ini")
        if not self.channels:
            raise ValueError("No Telegram channels found in [channels] section of config.ini")
