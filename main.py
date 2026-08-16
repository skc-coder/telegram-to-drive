import asyncio
import logging
import sys
from pathlib import Path

from telegram_gdrive_sync.config import Config
from telegram_gdrive_sync.pipeline import SyncPipeline

def setup_logging():
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    file_handler = logging.FileHandler(log_dir / "sync.log", encoding="utf-8")
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(name)s: %(message)s")
    file_handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)

def main():
    setup_logging()
    logger = logging.getLogger("telegram_gdrive_sync")
    logger.info("=== Starting Telegram to Google Drive Auto-Sync ===")

    config_file = "config.ini"
    if len(sys.argv) > 1:
        config_file = sys.argv[1]

    try:
        config = Config(config_file)
        config.validate()
    except Exception as e:
        print(f"\n[!] Configuration Error: {e}")
        print("Please edit 'config.ini' with your Telegram API credentials and channel list.\n")
        sys.exit(1)

    pipeline = SyncPipeline(config)
    try:
        asyncio.run(pipeline.run())
        print("\n[+] All channel sync operations completed successfully!\n")
    except KeyboardInterrupt:
        print("\n[!] Process interrupted by user. State saved.\n")
    except Exception as e:
        logger.exception("Fatal error during sync execution")
        print(f"\n[!] Fatal Error: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
