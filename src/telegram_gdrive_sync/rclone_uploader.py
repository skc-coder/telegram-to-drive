import asyncio
import logging
import re
import subprocess
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("telegram_gdrive_sync")

class RcloneUploader:
    def __init__(self, remote_name: str, remote_folder: str, max_upload_speed: str = "0"):
        self.remote_name = remote_name.rstrip(":")
        self.remote_folder = remote_folder.strip("/")
        self.max_upload_speed = max_upload_speed

    async def upload_file(
        self,
        local_path: Path,
        channel_folder_name: str,
        progress_callback: Optional[Callable[[int, int, float, str], None]] = None
    ) -> str:
        """
        Uploads (moves) local_path to Google Drive under <remote_name>:<remote_folder>/<channel_folder_name>/
        """
        dest_remote_dir = f"{self.remote_name}:{self.remote_folder}/{channel_folder_name}"
        
        cmd = [
            "rclone", "move",
            str(local_path),
            dest_remote_dir,
            "-P",  # Progress
            "--stats", "500ms"
        ]

        if self.max_upload_speed and self.max_upload_speed != "0":
            cmd.extend(["--bwlimit", self.max_upload_speed])

        logger.info(f"Starting rclone move: {local_path.name} -> {dest_remote_dir}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Parse rclone progress output from stdout/stderr
        total_size = local_path.stat().st_size if local_path.exists() else 0

        # Pattern matches e.g. Transferred: 5.2 MiB / 10 MiB, 52%, 1.2 MiB/s, ETA 4s
        transferred_pattern = re.compile(r"Transferred:\s+([\d.]+)\s*(\w+)\s*/\s*([\d.]+)\s*(\w+),\s*(\d+)%,\s*([\d.]+)\s*(\w+/s),\s*ETA\s*(.+)")

        stderr_lines = []
        async def read_stream(stream, is_err=False):
            nonlocal total_size
            while True:
                line = await stream.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="ignore").strip()
                if is_err and line_str:
                    stderr_lines.append(line_str)
                if progress_callback and "Transferred:" in line_str:
                    match = transferred_pattern.search(line_str)
                    if match:
                        cur_val, cur_unit, tot_val, tot_unit, pct, speed_val, speed_unit, eta = match.groups()
                        cur_bytes = self._to_bytes(float(cur_val), cur_unit)
                        tot_bytes = self._to_bytes(float(tot_val), tot_unit)
                        speed_str = f"{speed_val} {speed_unit}"
                        progress_callback(cur_bytes, tot_bytes if tot_bytes > 0 else total_size, speed_str, eta)

        await asyncio.gather(
            read_stream(proc.stdout),
            read_stream(proc.stderr, is_err=True)
        )

        returncode = await proc.wait()
        if returncode != 0:
            err_msg = "\n".join(stderr_lines[-5:]) if stderr_lines else "Unknown rclone error"
            raise RuntimeError(f"rclone move failed (code {returncode}): {err_msg}")

        remote_target_path = f"{dest_remote_dir}/{local_path.name}"
        logger.info(f"Upload complete: {remote_target_path}")
        return remote_target_path

    def _to_bytes(self, val: float, unit: str) -> int:
        unit = unit.lower()
        multiplier = 1
        if "k" in unit:
            multiplier = 1024
        elif "m" in unit:
            multiplier = 1024 * 1024
        elif "g" in unit:
            multiplier = 1024 * 1024 * 1024
        elif "t" in unit:
            multiplier = 1024 * 1024 * 1024 * 1024
        return int(val * multiplier)
