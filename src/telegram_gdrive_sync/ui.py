import time
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn, TaskID
from rich.layout import Layout
from rich.table import Table

class MultiProgressUI:
    def __init__(self, download_slots: int = 3, upload_slots: int = 3):
        self.console = Console()
        self.download_slots = download_slots
        self.upload_slots = upload_slots

        self.dl_progress = Progress(
            TextColumn("[bold cyan]{task.fields[filename]}"),
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>3.0f}%",
            "•",
            DownloadColumn(),
            "•",
            TransferSpeedColumn(),
            "•",
            TimeRemainingColumn(),
        )

        self.ul_progress = Progress(
            TextColumn("[bold green]{task.fields[filename]}"),
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>3.0f}%",
            "•",
            DownloadColumn(),
            "•",
            TextColumn("[yellow]{task.fields[speed]}"),
            "•",
            TextColumn("[cyan]ETA: {task.fields[eta]}"),
        )

        self.dl_tasks = {}
        self.ul_tasks = {}
        self.channel_title = "Initializing..."
        self.live = None

    def start(self):
        self.live = Live(self._generate_layout(), refresh_per_second=4, console=self.console)
        self.live.start()

    def stop(self):
        if self.live:
            self.live.stop()

    def set_channel(self, name: str):
        self.channel_title = name
        if self.live:
            self.live.update(self._generate_layout())

    def set_channel_name(self, name: str):
        self.set_channel(name)

    def add_download_task(self, slot_id: int, filename: str, total_bytes: int) -> TaskID:
        # Truncate filename for display
        disp_name = (filename[:25] + '..') if len(filename) > 27 else filename
        if slot_id in self.dl_tasks:
            self.dl_progress.reset(self.dl_tasks[slot_id], total=total_bytes, filename=disp_name)
            self.dl_progress.update(self.dl_tasks[slot_id], visible=True)
        else:
            task_id = self.dl_progress.add_task("download", filename=disp_name, total=total_bytes)
            self.dl_tasks[slot_id] = task_id
        return self.dl_tasks[slot_id]

    def update_download_task(self, slot_id: int, completed_bytes: int):
        if slot_id in self.dl_tasks:
            self.dl_progress.update(self.dl_tasks[slot_id], completed=completed_bytes)

    def remove_download_task(self, slot_id: int):
        if slot_id in self.dl_tasks:
            self.dl_progress.update(self.dl_tasks[slot_id], visible=False)

    def add_upload_task(self, slot_id: int, filename: str, total_bytes: int) -> TaskID:
        disp_name = (filename[:25] + '..') if len(filename) > 27 else filename
        if slot_id in self.ul_tasks:
            self.ul_progress.reset(self.ul_tasks[slot_id], total=total_bytes, filename=disp_name, speed="0 B/s", eta="--")
            self.ul_progress.update(self.ul_tasks[slot_id], visible=True)
        else:
            task_id = self.ul_progress.add_task("upload", filename=disp_name, total=total_bytes, speed="0 B/s", eta="--")
            self.ul_tasks[slot_id] = task_id
        return self.ul_tasks[slot_id]

    def update_upload_task(self, slot_id: int, completed_bytes: int, total_bytes: int, speed: str, eta: str):
        if slot_id in self.ul_tasks:
            self.ul_progress.update(
                self.ul_tasks[slot_id],
                completed=completed_bytes,
                total=total_bytes if total_bytes > 0 else None,
                speed=speed,
                eta=eta
            )

    def remove_upload_task(self, slot_id: int):
        if slot_id in self.ul_tasks:
            self.ul_progress.update(self.ul_tasks[slot_id], visible=False)

    def _generate_layout(self) -> Table:
        table = Table.grid(expand=True)
        table.add_row(Panel(f"[bold magenta]Telegram Channel:[/] [yellow]{self.channel_title}[/]", border_style="blue"))
        table.add_row(Panel(self.dl_progress, title="[bold cyan]⚡ Downloads (Telethon)[/]", border_style="cyan"))
        table.add_row(Panel(self.ul_progress, title="[bold green]☁️ Uploads (Rclone -> GDrive)[/]", border_style="green"))
        return table
