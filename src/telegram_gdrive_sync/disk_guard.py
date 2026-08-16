import shutil
from pathlib import Path
import logging

logger = logging.getLogger("telegram_gdrive_sync")

class DiskGuard:
    def __init__(self, target_path: Path, min_free_gb: float = 5.0):
        self.target_path = Path(target_path)
        self.min_free_bytes = min_free_gb * 1024 * 1024 * 1024

    def get_free_bytes(self) -> int:
        # Ensure path or parent exists
        check_path = self.target_path
        while not check_path.exists() and check_path.parent != check_path:
            check_path = check_path.parent
        total, used, free = shutil.disk_usage(check_path)
        return free

    def get_free_gb(self) -> float:
        return self.get_free_bytes() / (1024 * 1024 * 1024)

    def has_sufficient_space(self, required_bytes: int = 0) -> bool:
        free = self.get_free_bytes()
        return (free - required_bytes) >= self.min_free_bytes
