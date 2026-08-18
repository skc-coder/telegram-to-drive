import asyncio
import logging
import sqlite3
import subprocess
from pathlib import Path
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_remote_state")

def sync_gdrive_to_state():
    remote_folder = "Telegram_Downloads"
    remote_name = "gdrive"
    
    state_dir = Path(".state")
    state_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Fetch remote files list from GDrive via rclone
    cmd = ["rclone", "lsf", "-R", f"{remote_name}:{remote_folder}"]
    logger.info(f"Executing: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    if res.returncode != 0:
        logger.error(f"Failed to list rclone directory: {res.stderr}")
        return

    remote_files = set()
    for line in res.stdout.splitlines():
        line = line.strip()
        if line and not line.endswith("/"):
            # Normalize path or filename
            filename = Path(line).name
            remote_files.add(filename)
            # Also store full relative path just in case
            remote_files.add(line)

    logger.info(f"Found {len(remote_files)} items on Google Drive.")

    # 2. Iterate through all .sqlite state files in .state/
    db_files = list(state_dir.glob("index_*.sqlite"))
    if not db_files:
        logger.warning("No index_*.sqlite databases found in .state/")
        return

    updated_count = 0
    for db_path in db_files:
        logger.info(f"Checking database: {db_path.name}")
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT message_id, file_name, download_status, upload_status FROM file_index")
            rows = cursor.fetchall()
            
            for row in rows:
                msg_id = row["message_id"]
                fname = row["file_name"]
                d_status = row["download_status"]
                u_status = row["upload_status"]

                if fname in remote_files:
                    if d_status != "uploaded" or u_status != "uploaded":
                        cursor.execute("""
                            UPDATE file_index
                            SET download_status = 'uploaded',
                                upload_status = 'uploaded'
                            WHERE message_id = ?
                        """, (msg_id,))
                        updated_count += 1
                        logger.info(f"Marked msg_id {msg_id} ({fname}) as uploaded.")
            conn.commit()

    logger.info(f"Successfully updated {updated_count} record(s) in local state database.")

if __name__ == "__main__":
    sync_gdrive_to_state()
