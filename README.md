# Telegram to Google Drive Smart Auto-Sync Daemon (`telegram-gdrive-sync`)

A high-performance, producer-consumer daemon that downloads media from Telegram channels and uploads them to Google Drive in parallel, using per-channel indexing for full resumability.

## Key Features

- **Producer-Consumer Concurrent Pipeline**: Downloads up to 3 files in parallel while uploading completed files to Google Drive with up to 3 `rclone` workers.
- **Per-Channel Resumable Indexing**: Separate SQLite index per channel ensures files are never re-downloaded or re-uploaded across discontinuous runs.
- **Storage Disk Guard**: Automatically pauses downloads if available disk space in `/mnt/storage/telegram_downloads` drops below configured threshold (e.g. 5 GB).
- **Network Drop Auto-Retry**: Exponential backoff handles network glitches and Telegram rate limits cleanly.
- **Startup Temp Cleanup**: Automatically removes partial `.tmp` files from interrupted runs.
- **Rich Multi-Progress Terminal UI**: Shows channel name, download speed & progress (Telethon), and upload speed & ETA (`rclone`).
- **Autostart Service**: Runs automatically in the background on system login via systemd user service.

---

## Setup & Installation

```bash
# 1. Install dependencies using uv
uv sync

# 2. Configure Telegram API credentials & channels in config.ini
nano config.ini
```

In `config.ini`:
- Fill in `api_id`, `api_hash`, and `phone_number` (obtainable from [my.telegram.org](https://my.telegram.org)).
- Configure `rclone` remote (default: `gdrive`).
- Add channel links under `[channels]`.

---

## Running Interactive Mode (Initial Setup & Authentication)

Run interactively the first time so Telethon can prompt for your Telegram login code and create the session file:

```bash
uv run python main.py
```

---

## Background Autostart Service Setup

To make the system run automatically in the background whenever you log in:

```bash
./install_service.sh
```

### Managing the Background Daemon:
- **Check Status**: `systemctl --user status telegram-gdrive-sync.service`
- **View Live Daemon Logs**: `journalctl --user -u telegram-gdrive-sync.service -f`
- **Stop Daemon**: `systemctl --user stop telegram-gdrive-sync.service`
- **Start Daemon**: `systemctl --user start telegram-gdrive-sync.service`

---

## Update & Sync

```bash
git pull && uv sync
```
