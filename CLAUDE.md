# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Does

This is a YouTube video downloader and clipper project with three distinct interfaces:

1. **Streamlit Web App** (`app.py`) — Browser UI using yt-dlp + moviepy for downloading and trimming video clips. Runs as a web app.
2. **Tkinter Desktop UI** (`yt-dlp/downloader_ui.pyw`) — A native GUI app (console-free via `.pyw`) that reads job configs, runs yt-dlp as a subprocess, and optionally uploads results to YouTube.
3. **Batch/Script runner** (`yt-dlp/run_download.ps1` / `yt-dlp/MacVersion/run_download.sh`) — Headless scripts that parse `download_config.txt` for batch download jobs.

All approaches share the same core flow: yt-dlp downloads video → optionally trim clip → optionally upload to YouTube via `upload_to_youtube.py`.

## Running the Apps

**Streamlit web app:**
```bash
pip install -r requirements.txt
streamlit run app.py
```

**Desktop GUI (Windows):**
```
double-click yt-dlp/launch_ui.bat
# or: pythonw yt-dlp/downloader_ui.pyw
```

**Batch script (Windows):**
```
double-click yt-dlp/run_download.bat
# or from PowerShell: .\yt-dlp\run_download.ps1
```

**Batch script (Mac):**
```bash
bash yt-dlp/MacVersion/run_download.sh
```

**Standalone clip script:**
```bash
python app2.py
```

## Dependencies

- `requirements.txt` — for the Streamlit app: `streamlit`, `yt-dlp`, `moviepy`, `imageio-ffmpeg`
- `packages.txt` — system-level: `ffmpeg`
- YouTube upload (`upload_to_youtube.py`): `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`
- Install script: `yt-dlp/install_requirements.bat`

## Architecture

### download_config.txt Format
Jobs are defined in `yt-dlp/download_config.txt` as key=value blocks separated by `---`. Keys: `URL`, `QUALITY` (720p/1080p/1440p/2160p/best), `START`/`END` (hh:mm:ss), `OUTPUT_DIR`, `FILENAME`, `UPLOAD` (yes/no), `YT_TITLE`, `YT_DESCRIPTION`, `YT_PLAYLIST`.

### yt-dlp.conf
`yt-dlp/yt-dlp.conf` sets global yt-dlp defaults (JS runtime, merge format, cookies file). The output path (`-o`) is intentionally omitted here and set per-job at runtime.

### YouTube Upload Authentication
`upload_to_youtube.py` uses OAuth 2.0. On first run it opens a browser for Google login and caches credentials in `yt-dlp/token.pickle`. `yt-dlp/client_secrets.json` must be present (downloaded from Google Cloud Console → APIs & Services → Credentials).

### Quality Format Mapping
All three runners (PS1, shell, Python UI) use the same format string pattern:
- `720p` → `bv[height=720]+ba[ext=m4a]`
- `1080p` → `bv[height=1080]+ba[ext=m4a]`
- `best` → `bv+ba[ext=m4a]`

### Streamlit App State
`app.py` uses `st.session_state` extensively to sync sliders ↔ text inputs for start/end times. `get_video_info()` is cached with `@st.cache_resource` to avoid repeated yt-dlp calls. Cookies are read from `www.youtube.com_cookies.txt` in the working directory.

### Desktop UI Threading Model
`downloader_ui.pyw` runs yt-dlp and the upload script as subprocesses in a background thread, streaming stdout into a `queue.Queue` that the main thread polls every 100ms to update the log widget. `CREATE_NO_WINDOW` flag is set on Windows to suppress console windows.
