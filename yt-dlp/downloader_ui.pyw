"""
YouTube Clip Downloader - Popup UI  (Option 3)
Runs jobs directly via subprocess — never touches download_config.txt.
Double-click launch_ui.bat (or run with pythonw) for a console-free experience.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import threading
import queue
import os
import sys
import glob
import shutil

# ── locate script directory (works even as .pyw) ─────────────────────────────
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
UPLOAD_SCRIPT = os.path.join(SCRIPT_DIR, "upload_to_youtube.py")
CONF_FILE     = os.path.join(SCRIPT_DIR, "yt-dlp.conf")
DL_CONFIG     = os.path.join(SCRIPT_DIR, "download_config.txt")

# ── yt-dlp detection (mirrors PS1 logic) ────────────────────────────────────
def find_ytdlp():
    """Return (cmd_list, label) for the best available yt-dlp."""
    exe = shutil.which("yt-dlp")
    if exe:
        return [exe], "yt-dlp (exe)"
    py = shutil.which("python") or shutil.which("python3")
    if py:
        try:
            subprocess.check_output([py, "-m", "yt_dlp", "--version"],
                                    stderr=subprocess.DEVNULL)
            return [py, "-m", "yt_dlp"], "python -m yt_dlp"
        except Exception:
            pass
    return None, None

# ── config parser ────────────────────────────────────────────────────────────
def parse_first_job(config_path):
    """
    Read download_config.txt and return a dict for the FIRST job block.
    Jobs are separated by lines containing only '---'.
    Keys are normalised to uppercase; blank values are kept as empty strings.
    Returns {} if the file is missing or empty.
    """
    if not os.path.isfile(config_path):
        return {}
    data = {}
    try:
        with open(config_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("---"):
                    break                       # stop at job separator
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, val = line.partition("=")
                    data[key.strip().upper()] = val.strip()
    except OSError:
        pass
    return data

# ── quality format map ───────────────────────────────────────────────────────
QUALITY_FORMATS = {
    "720p":  "bv[height=720]+ba[ext=m4a]",
    "1080p": "bv[height=1080]+ba[ext=m4a]",
    "1440p": "bv[height=1440]+ba[ext=m4a]",
    "2160p": "bv[height=2160]+ba[ext=m4a]",
    "best":  "bv+ba[ext=m4a]",
}

AUDIO_QUALITY_FORMATS = {
    "128k": "bestaudio[abr<=128][ext=m4a]/bestaudio[abr<=128]",
    "192k": "bestaudio[abr<=192][ext=m4a]/bestaudio[abr<=192]",
    "320k": "bestaudio[abr<=320][ext=m4a]/bestaudio[abr<=320]",
    "best": "bestaudio[ext=m4a]/bestaudio",
}

# ─────────────────────────────────────────────────────────────────────────────
#  Main App
# ─────────────────────────────────────────────────────────────────────────────
class DownloaderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Clip Downloader")
        self.resizable(True, True)
        self.minsize(680, 700)

        self.output_queue = queue.Queue()
        self._running = False

        self._build_ui()
        self._load_config(silent=True)   # pre-populate from download_config.txt
        self._poll_queue()
        self._center_window()

    # ── layout ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        PADX, PADY = 12, 5
        BG   = "#1e1e2e"
        FG   = "#cdd6f4"
        ENTRY_BG = "#313244"
        BTN_BG   = "#89b4fa"
        BTN_FG   = "#1e1e2e"
        LOG_BG   = "#11111b"
        LOG_FG   = "#a6e3a1"
        SEP_CLR  = "#45475a"

        self.configure(bg=BG)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame",       background=BG)
        style.configure("TLabel",       background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("TEntry",       fieldbackground=ENTRY_BG, foreground=FG,
                        insertcolor=FG, borderwidth=1, relief="flat")
        style.configure("TCheckbutton", background=BG, foreground=FG, font=("Segoe UI", 10))
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("TRadiobutton", background=BG, foreground=FG, font=("Segoe UI", 10))
        style.map("TRadiobutton", background=[("active", BG)])
        style.configure("Run.TButton",  background=BTN_BG, foreground=BTN_FG,
                        font=("Segoe UI", 11, "bold"), padding=8)
        style.map("Run.TButton",
                  background=[("active", "#74c7ec"), ("disabled", SEP_CLR)],
                  foreground=[("disabled", "#6c7086")])
        style.configure("Stop.TButton", background="#f38ba8", foreground=BTN_FG,
                        font=("Segoe UI", 11, "bold"), padding=8)
        style.map("Stop.TButton", background=[("active", "#eba0ac")])
        style.configure("Browse.TButton", background="#585b70", foreground=FG,
                        font=("Segoe UI", 9), padding=4)
        style.map("Browse.TButton", background=[("active", "#7f849c")])
        style.configure("TSeparator", background=SEP_CLR)

        # ── header ────────────────────────────────────────────────────────
        hdr = ttk.Frame(self)
        hdr.pack(fill="x", padx=PADX, pady=(14, 4))
        tk.Label(hdr, text="▶  YouTube Clip Downloader",
                 bg=BG, fg=BTN_BG,
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        ttk.Button(hdr, text="↺  Reload config", style="Browse.TButton",
                   command=self._load_config).pack(side="right")

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=PADX, pady=4)

        # ── form frame ────────────────────────────────────────────────────
        form = ttk.Frame(self)
        form.pack(fill="x", padx=PADX, pady=2)
        form.columnconfigure(1, weight=1)

        row = 0

        # URL
        ttk.Label(form, text="YouTube URL *").grid(row=row, column=0, sticky="w", pady=PADY)
        self.url_var = tk.StringVar()
        url_entry = ttk.Entry(form, textvariable=self.url_var, width=55)
        url_entry.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(8,0), pady=PADY)
        row += 1

        # Mode
        ttk.Label(form, text="Mode").grid(row=row, column=0, sticky="w", pady=PADY)
        self.mode_var = tk.StringVar(value="video")
        mf = ttk.Frame(form)
        mf.grid(row=row, column=1, columnspan=2, sticky="w", padx=(8,0))
        ttk.Radiobutton(mf, text="Video", variable=self.mode_var, value="video",
                        command=self._on_mode_change).pack(side="left", padx=4)
        ttk.Radiobutton(mf, text="Audio Only", variable=self.mode_var, value="audio",
                        command=self._on_mode_change).pack(side="left", padx=4)
        row += 1

        # Quality label (shared row for both mode frames)
        self._quality_label = ttk.Label(form, text="Quality")
        self._quality_label.grid(row=row, column=0, sticky="w", pady=PADY)

        # Video quality frame
        self.quality_var = tk.StringVar(value="1080p")
        self.video_qf = ttk.Frame(form)
        self.video_qf.grid(row=row, column=1, columnspan=2, sticky="w", padx=(8,0))
        for q in ["720p", "1080p", "1440p", "2160p", "best"]:
            ttk.Radiobutton(self.video_qf, text=q, variable=self.quality_var, value=q).pack(side="left", padx=4)

        # Audio quality frame (hidden by default)
        self.audio_quality_var = tk.StringVar(value="best")
        self.audio_qf = ttk.Frame(form)
        self.audio_qf.grid(row=row, column=1, columnspan=2, sticky="w", padx=(8,0))
        for q in ["128k", "192k", "320k", "best"]:
            ttk.Radiobutton(self.audio_qf, text=q, variable=self.audio_quality_var, value=q).pack(side="left", padx=4)
        self.audio_qf.grid_remove()
        row += 1

        # Start / End
        ttk.Label(form, text="Start time").grid(row=row, column=0, sticky="w", pady=PADY)
        self.start_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.start_var, width=14).grid(
            row=row, column=1, sticky="w", padx=(8,0), pady=PADY)
        ttk.Label(form, text="(hh:mm:ss — leave blank for full video)",
                  foreground="#6c7086").grid(row=row, column=2, sticky="w", padx=6)
        row += 1

        ttk.Label(form, text="End time").grid(row=row, column=0, sticky="w", pady=PADY)
        self.end_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.end_var, width=14).grid(
            row=row, column=1, sticky="w", padx=(8,0), pady=PADY)
        row += 1

        # Output folder
        ttk.Label(form, text="Output Folder *").grid(row=row, column=0, sticky="w", pady=PADY)
        outf = ttk.Frame(form)
        outf.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(8,0), pady=PADY)
        outf.columnconfigure(0, weight=1)
        self.outdir_var = tk.StringVar()
        ttk.Entry(outf, textvariable=self.outdir_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(outf, text="Browse…", style="Browse.TButton",
                   command=self._browse_folder).grid(row=0, column=1, padx=(6,0))
        row += 1

        # Filename
        ttk.Label(form, text="Filename").grid(row=row, column=0, sticky="w", pady=PADY)
        self.filename_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.filename_var, width=40).grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=(8,0), pady=PADY)
        self._filename_hint = ttk.Label(form, text="(optional — .mp4 added automatically)",
                                        foreground="#6c7086")
        self._filename_hint.grid(row=row, column=2, sticky="w", padx=6)
        row += 1

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=PADX, pady=8)

        # Upload section
        upload_frame = ttk.Frame(self)
        upload_frame.pack(fill="x", padx=PADX, pady=2)
        upload_frame.columnconfigure(1, weight=1)

        self.upload_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(upload_frame, text="Upload to YouTube as Private after download",
                        variable=self.upload_var,
                        command=self._toggle_upload).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=PADY)

        u_row = 1
        ttk.Label(upload_frame, text="YT Title").grid(row=u_row, column=0, sticky="w", pady=PADY)
        self.yt_title_var = tk.StringVar()
        self.yt_title_entry = ttk.Entry(upload_frame, textvariable=self.yt_title_var, width=45,
                                        state="disabled")
        self.yt_title_entry.grid(row=u_row, column=1, columnspan=2, sticky="ew",
                                  padx=(8,0), pady=PADY)
        u_row += 1

        ttk.Label(upload_frame, text="YT Description").grid(row=u_row, column=0, sticky="w", pady=PADY)
        self.yt_desc_var = tk.StringVar()
        self.yt_desc_entry = ttk.Entry(upload_frame, textvariable=self.yt_desc_var, width=45,
                                       state="disabled")
        self.yt_desc_entry.grid(row=u_row, column=1, columnspan=2, sticky="ew",
                                 padx=(8,0), pady=PADY)
        u_row += 1

        ttk.Label(upload_frame, text="YT Playlist").grid(row=u_row, column=0, sticky="w", pady=PADY)
        self.yt_playlist_var = tk.StringVar()
        self.yt_playlist_entry = ttk.Entry(upload_frame, textvariable=self.yt_playlist_var, width=45,
                                           state="disabled")
        self.yt_playlist_entry.grid(row=u_row, column=1, columnspan=2, sticky="ew",
                                     padx=(8,0), pady=PADY)

        self._upload_entries = [self.yt_title_entry,
                                self.yt_desc_entry,
                                self.yt_playlist_entry]

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=PADX, pady=8)

        # ── run / stop buttons ────────────────────────────────────────────
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=PADX, pady=4)
        self.run_btn = ttk.Button(btn_frame, text="▶  Run Download",
                                  style="Run.TButton", command=self._start_job)
        self.run_btn.pack(side="left", padx=(0,8))
        self.stop_btn = ttk.Button(btn_frame, text="■  Stop",
                                   style="Stop.TButton", command=self._stop_job,
                                   state="disabled")
        self.stop_btn.pack(side="left")
        self.clear_btn = ttk.Button(btn_frame, text="Clear log",
                                    style="Browse.TButton", command=self._clear_log)
        self.clear_btn.pack(side="right")

        # ── status bar ────────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.status_var, bg=BG, fg="#6c7086",
                 font=("Segoe UI", 9), anchor="w").pack(fill="x", padx=PADX)

        # ── output log ────────────────────────────────────────────────────
        log_frame = ttk.Frame(self)
        log_frame.pack(fill="both", expand=True, padx=PADX, pady=(4, 12))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log = tk.Text(log_frame, bg=LOG_BG, fg=LOG_FG,
                           font=("Consolas", 9), wrap="word",
                           state="disabled", relief="flat",
                           selectbackground="#313244", selectforeground=FG)
        self.log.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(log_frame, command=self.log.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=sb.set)

    # ── config loading ────────────────────────────────────────────────────────
    def _load_config(self, silent=False):
        """Read the first job block from download_config.txt and populate fields."""
        data = parse_first_job(DL_CONFIG)
        if not data:
            if not silent:
                messagebox.showinfo(
                    "Config not found",
                    f"Could not read download_config.txt\nExpected at:\n{DL_CONFIG}"
                )
            self.status_var.set("Ready  (no config file found)")
            return
        self._apply_config(data)
        src = os.path.basename(DL_CONFIG)
        self.status_var.set(f"Pre-filled from {src}  —  edit fields then click Run")

    def _apply_config(self, data):
        """Apply a parsed job dict to the UI fields (only non-blank values)."""

        def set_if(var, key):
            val = data.get(key, "")
            if val:
                var.set(val)

        set_if(self.url_var,      "URL")
        set_if(self.start_var,    "START")
        set_if(self.end_var,      "END")
        set_if(self.outdir_var,   "OUTPUT_DIR")
        set_if(self.filename_var, "FILENAME")
        set_if(self.yt_title_var, "YT_TITLE")
        set_if(self.yt_desc_var,  "YT_DESCRIPTION")
        set_if(self.yt_playlist_var, "YT_PLAYLIST")

        # Mode (audio/video)
        audio_only = data.get("AUDIO_ONLY", "").lower()
        if audio_only in ("yes", "true", "1"):
            self.mode_var.set("audio")
            self._on_mode_change()
        elif audio_only in ("no", "false", "0"):
            self.mode_var.set("video")
            self._on_mode_change()

        # Quality radio — only update if value is recognised
        q = data.get("QUALITY", "").lower()
        if q in QUALITY_FORMATS:
            self.quality_var.set(q)

        # Audio quality radio
        aq = data.get("AUDIO_QUALITY", "").lower()
        if aq in AUDIO_QUALITY_FORMATS:
            self.audio_quality_var.set(aq)

        # Upload checkbox
        upload_val = data.get("UPLOAD", "").lower()
        if upload_val in ("yes", "true", "1"):
            self.upload_var.set(True)
            self._toggle_upload()
        elif upload_val in ("no", "false", "0"):
            self.upload_var.set(False)
            self._toggle_upload()

    # ── helpers ──────────────────────────────────────────────────────────────
    def _center_window(self):
        self.update_idletasks()
        w, h = 720, 750
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.outdir_var.set(folder)

    def _on_mode_change(self):
        if self.mode_var.get() == "audio":
            self.video_qf.grid_remove()
            self.audio_qf.grid()
            self._filename_hint.configure(text="(optional — .m4a added automatically)")
        else:
            self.audio_qf.grid_remove()
            self.video_qf.grid()
            self._filename_hint.configure(text="(optional — .mp4 added automatically)")

    def _toggle_upload(self):
        state = "normal" if self.upload_var.get() else "disabled"
        for e in self._upload_entries:
            e.configure(state=state)

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_running(self, running: bool):
        self._running = running
        self.run_btn.configure(state="disabled" if running else "normal")
        self.stop_btn.configure(state="normal" if running else "disabled")
        self.status_var.set("Running…" if running else "Done")

    # ── queue polling (runs in main thread) ──────────────────────────────────
    def _poll_queue(self):
        try:
            while True:
                msg = self.output_queue.get_nowait()
                if msg is None:
                    self._set_running(False)
                else:
                    self._log(msg)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    # ── validation ───────────────────────────────────────────────────────────
    def _validate(self):
        url = self.url_var.get().strip()
        outdir = self.outdir_var.get().strip()
        if not url:
            messagebox.showerror("Missing field", "YouTube URL is required.")
            return False
        if not outdir:
            messagebox.showerror("Missing field", "Output Folder is required.")
            return False
        if not os.path.isdir(outdir):
            if messagebox.askyesno("Folder not found",
                                   f"'{outdir}' does not exist.\nCreate it?"):
                try:
                    os.makedirs(outdir, exist_ok=True)
                except OSError as e:
                    messagebox.showerror("Error", f"Could not create folder:\n{e}")
                    return False
            else:
                return False
        return True

    # ── job runner (background thread) ───────────────────────────────────────
    def _start_job(self):
        if not self._validate():
            return

        url           = self.url_var.get().strip()
        mode          = self.mode_var.get()
        quality       = self.quality_var.get()
        audio_quality = self.audio_quality_var.get()
        start         = self.start_var.get().strip()
        end           = self.end_var.get().strip()
        outdir        = self.outdir_var.get().strip()
        filename      = self.filename_var.get().strip()
        do_upload     = self.upload_var.get()
        yt_title      = self.yt_title_var.get().strip()
        yt_desc       = self.yt_desc_var.get().strip()
        yt_playlist   = self.yt_playlist_var.get().strip()

        self._set_running(True)
        self.status_var.set("Running…")

        self._proc = None   # will hold the active Popen

        t = threading.Thread(
            target=self._run_job,
            args=(url, mode, quality, audio_quality, start, end, outdir, filename,
                  do_upload, yt_title, yt_desc, yt_playlist),
            daemon=True
        )
        t.start()

    def _stop_job(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            self.output_queue.put("  [Stopped by user]")
        self.output_queue.put(None)

    def _run_job(self, url, mode, quality, audio_quality, start, end, outdir, filename,
                 do_upload, yt_title, yt_desc, yt_playlist):
        q = self.output_queue
        is_audio = (mode == "audio")

        q.put("  ======================================")
        q.put("    YouTube Clip Downloader")
        q.put("  ======================================")
        q.put(f"  URL     : {url}")
        q.put(f"  Mode    : {'Audio Only' if is_audio else 'Video'}")
        q.put(f"  Quality : {audio_quality if is_audio else quality}")

        # ── locate yt-dlp ─────────────────────────────────────────────────
        ytdlp_cmd, ytdlp_label = find_ytdlp()
        if not ytdlp_cmd:
            q.put("  ERROR: yt-dlp not found.")
            q.put("  Install with:  pip install yt-dlp[default]")
            q.put(None)
            return
        q.put(f"  yt-dlp  : {ytdlp_label}")

        # ── build output path ─────────────────────────────────────────────
        ext = "m4a" if is_audio else "mp4"
        if filename:
            base = os.path.splitext(filename)[0]
            output_arg = os.path.join(outdir, base + f".{ext}")
        else:
            output_arg = os.path.join(outdir, f"%(title)s.{ext}")

        q.put(f"  Output  : {output_arg}")

        # ── clip range ────────────────────────────────────────────────────
        has_section = bool(start and end)
        if has_section:
            q.put(f"  Clip    : {start} → {end}")
        else:
            q.put("  Clip    : Full video")

        q.put("")
        q.put("  Starting download…")

        # ── build yt-dlp args ─────────────────────────────────────────────
        if is_audio:
            fmt = AUDIO_QUALITY_FORMATS.get(audio_quality, AUDIO_QUALITY_FORMATS["best"])
            ytdlp_args = ytdlp_cmd + [
                "--config-locations", CONF_FILE,
                "-f", fmt,
                "-x", "--audio-format", "m4a",
                "-o", output_arg,
            ]
        else:
            fmt = QUALITY_FORMATS.get(quality, QUALITY_FORMATS["1080p"])
            ytdlp_args = ytdlp_cmd + [
                "--config-locations", CONF_FILE,
                "-f", fmt,
                "-o", output_arg,
            ]
        if has_section:
            ytdlp_args += ["--download-sections", f"*{start}-{end}"]
        ytdlp_args.append(url)

        exit_code = self._run_cmd(ytdlp_args, q)

        if exit_code != 0:
            q.put(f"  FAILED — yt-dlp exited with code {exit_code}")
            q.put("  ======================================")
            q.put(None)
            return

        q.put(f"  OK — Saved to: {output_arg}")

        # ── upload ────────────────────────────────────────────────────────
        if do_upload:
            q.put("")
            q.put("  Upload requested — locating file…")

            if filename:
                upload_file = output_arg
            else:
                glob_pattern = f"*.{ext}"
                files = sorted(glob.glob(os.path.join(outdir, glob_pattern)),
                               key=os.path.getmtime, reverse=True)
                upload_file = files[0] if files else None

            if not upload_file or not os.path.isfile(upload_file):
                q.put(f"  ERROR: Could not find downloaded file in {outdir}")
                q.put("  ======================================")
                q.put(None)
                return

            q.put(f"  Uploading: {upload_file}")

            py_cmd = shutil.which("python") or shutil.which("python3") or sys.executable
            py_args = [py_cmd, UPLOAD_SCRIPT, "--file", upload_file]
            if yt_title:    py_args += ["--title",       yt_title]
            if yt_desc:     py_args += ["--description", yt_desc]
            if yt_playlist: py_args += ["--playlist",    yt_playlist]

            up_code = self._run_cmd(py_args, q)
            if up_code == 0:
                q.put("  Upload OK")
            else:
                q.put("  Upload FAILED — check output above")

        q.put("")
        q.put("  ======================================")
        q.put("  Done!")
        q.put("  ======================================")
        q.put(None)

    # ── run a subprocess and stream output into queue ─────────────────────────
    def _run_cmd(self, args, q):
        try:
            self._proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=SCRIPT_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            for line in self._proc.stdout:
                q.put("  " + line.rstrip())
            self._proc.wait()
            return self._proc.returncode
        except FileNotFoundError as e:
            q.put(f"  ERROR: {e}")
            return 1
        except Exception as e:
            q.put(f"  ERROR: {e}")
            return 1


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = DownloaderApp()
    app.mainloop()
