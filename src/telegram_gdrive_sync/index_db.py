import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional

class IndexDB:
    """Per-channel SQLite index tracking downloaded & uploaded files for dynamic resumability."""
    def __init__(self, state_dir: Path, channel_identifier: str):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        # Clean safe database name for channel
        safe_name = "".join(c if c.isalnum() else "_" for c in str(channel_identifier))
        self.db_path = self.state_dir / f"index_{safe_name}.sqlite"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_index (
                    message_id INTEGER PRIMARY KEY,
                    file_name TEXT,
                    file_size INTEGER,
                    download_status TEXT DEFAULT 'pending', -- pending, downloaded, error
                    upload_status TEXT DEFAULT 'pending',   -- pending, uploaded, error
                    local_path TEXT,
                    remote_path TEXT,
                    download_time TEXT,
                    upload_time TEXT,
                    error_message TEXT
                )
            """)
            conn.commit()

    def get_record(self, message_id: int) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM file_index WHERE message_id = ?", (message_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def is_already_uploaded(self, message_id: int) -> bool:
        rec = self.get_record(message_id)
        return rec is not None and rec.get("upload_status") == "uploaded"

    def is_already_downloaded(self, message_id: int) -> bool:
        rec = self.get_record(message_id)
        return rec is not None and rec.get("download_status") in ("downloaded", "uploaded")

    def mark_download_start(self, message_id: int, file_name: str, file_size: int, local_path: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO file_index (message_id, file_name, file_size, local_path, download_status)
                VALUES (?, ?, ?, ?, 'downloading')
                ON CONFLICT(message_id) DO UPDATE SET
                    file_name=excluded.file_name,
                    file_size=excluded.file_size,
                    local_path=excluded.local_path,
                    download_status='downloading'
            """, (message_id, file_name, file_size, local_path))
            conn.commit()

    def mark_downloaded(self, message_id: int, local_path: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE file_index
                SET download_status = 'downloaded',
                    local_path = ?,
                    download_time = datetime('now')
                WHERE message_id = ?
            """, (local_path, message_id))
            conn.commit()

    def mark_uploaded(self, message_id: int, remote_path: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE file_index
                SET upload_status = 'uploaded',
                    remote_path = ?,
                    upload_time = datetime('now')
                WHERE message_id = ?
            """, (remote_path, message_id))
            conn.commit()

    def mark_error(self, message_id: int, stage: str, error_msg: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            field = "download_status" if stage == "download" else "upload_status"
            cursor.execute(f"""
                UPDATE file_index
                SET {field} = 'error',
                    error_message = ?
                WHERE message_id = ?
            """, (error_msg, message_id))
            conn.commit()
