# Telegram to Google Drive Smart Auto-Sync Daemon (`telegram-gdrive-sync`)

A high-performance, producer-consumer daemon that downloads media from Telegram channels and uploads them to Google Drive in parallel, using per-channel indexing for full resumability.

---

## Standardization & Plan Architecture (`name_standardization`)

The system includes a **dynamic name & folder standardization module** capable of parsing both structured syllabus JSON files (e.g. GATE course detail plans) and lecture planner PDFs/text schedules:

- **Per-Channel Standardization Modes**:
  - `module_number_only`: Retains module prefix (`Module N ...`) while standardizing inner lecture titles.
  - `clean_prefix`: Strips channel/number prefixes, standardizing files to `<number> <topic_name>` format.
  - `neev_class_9`: Applies subject filtering (**SST, Science, Hindi, Maths, English**), skipping unwanted subjects (Sanskrit, AI, IT, Computer Science) and GIFs.
- **Syllabus / Lecture Plan Mapping**: Automatically aligns raw Telegram file names with official course titles from `course_details.json` or lecture planners (PDFs in `~/Downloads/mega/`), ensuring clean folder hierarchy on Google Drive before uploading.

---

## 🚀 Running on GitHub Codespaces (One-Line Setup)

When launching a new Codespace:

```bash
export RCLONE_CONF_BASE64="<YOUR_RCLONE_B64>" && export TG_SESSION_BASE64="<YOUR_TG_SESSION_B64>" && ./setup_codespace.sh
```

Then run the pipeline:
```bash
uv run python main.py
```

### Protection Against Duplicate Downloads / Uploads:
- **SQLite Index Databases (`.state/index_<channel_id>.sqlite`)**: Tracks every message ID's `download_status` and `upload_status`.
- **Pre-Check Guard**: Before initiating any download, the pipeline checks the SQLite index. If a message ID is already `downloaded`, `uploaded`, or currently `downloading`, it is automatically skipped.
- **Rclone Verification**: Performs remote checks so incomplete local uploads are resumed seamlessly without re-downloading.

---

## Setup & Installation (Local Machine)

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

```bash
uv run python main.py
```

---

## Background Autostart Service Setup (Systemd User Daemon)

```bash
./install_service.sh
```

### Managing the Daemon:
- **Check Status**: `systemctl --user status telegram-gdrive-sync.service`
- **View Live Daemon Logs**: `journalctl --user -u telegram-gdrive-sync.service -f`
- **Stop Daemon**: `systemctl --user stop telegram-gdrive-sync.service`
- **Start Daemon**: `systemctl --user start telegram-gdrive-sync.service`

---

## Update & Sync

```bash
git pull && uv sync
```
