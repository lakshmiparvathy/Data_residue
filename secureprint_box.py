import os
import time
import socket
import threading
import shutil
from pathlib import Path
from datetime import datetime

from flask import Flask, request, render_template_string, redirect, url_for, send_from_directory, abort
import qrcode
from PIL import Image, ImageTk

import tkinter as tk
from tkinter import messagebox, ttk

# =========================
# Configuration
# =========================
APP_NAME = "SecurePrint Box"
BASE_DIR = Path(r"C:\SecurePrintBox")  # change if you want
JOBS_DIR = BASE_DIR / "Jobs"
QR_DIR = BASE_DIR / "QR"
SERVER_PORT = 8080

# Auto-clean leftover jobs older than this (seconds)
LEFTOVER_TTL_SECONDS = 30 * 60  # 30 minutes

# Max upload size (bytes): 20MB
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

ALLOWED_EXT = {
    ".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx", ".txt",
    ".ppt", ".pptx", ".xls", ".xlsx"
}

# =========================
# Utility functions
# =========================
def ensure_dirs():
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    QR_DIR.mkdir(parents=True, exist_ok=True)

def get_local_ip():
    """
    Get a LAN IP to show in QR. This attempts a UDP connect trick.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def safe_filename(name: str) -> str:
    # minimal sanitization (avoid weird paths)
    name = name.replace("\\", "_").replace("/", "_").strip()
    return "".join(c for c in name if c.isalnum() or c in " ._-()").strip()

def is_allowed(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXT

def now_job_id():
    return "JOB_" + datetime.now().strftime("%Y%m%d_%H%M%S")

def write_marker(job_path: Path):
    marker = job_path / ".jobmeta"
    marker.write_text(str(int(time.time())), encoding="utf-8")

def read_marker_ts(job_path: Path):
    marker = job_path / ".jobmeta"
    if marker.exists():
        try:
            return int(marker.read_text(encoding="utf-8").strip())
        except Exception:
            return None
    return None

def basic_secure_delete_file(file_path: Path, passes: int = 1):
    """
    Basic overwrite + delete. Good for hackathon MVP.
    Note: On SSDs, perfect irrecoverability is not guaranteed due to wear leveling.
    """
    try:
        if not file_path.exists() or not file_path.is_file():
            return
        size = file_path.stat().st_size
        if size <= 0:
            file_path.unlink(missing_ok=True)
            return

        # overwrite content
        with open(file_path, "r+b") as f:
            for _ in range(max(1, passes)):
                f.seek(0)
                f.write(os.urandom(min(size, 1024 * 1024)))  # write 1MB random chunk
                # If file > 1MB, overwrite remaining with zeros for speed
                remaining = size - min(size, 1024 * 1024)
                if remaining > 0:
                    f.write(b"\x00" * remaining)
                f.flush()
                os.fsync(f.fileno())

        file_path.unlink(missing_ok=True)
    except Exception:
        # If something is locked, we still try to delete later
        try:
            file_path.unlink(missing_ok=True)
        except Exception:
            pass

def wipe_job_folder(job_path: Path):
    """
    Securely delete files inside job folder and remove folder.
    """
    if not job_path.exists():
        return

    # delete files first
    for p in job_path.rglob("*"):
        if p.is_file():
            basic_secure_delete_file(p, passes=1)

    # remove remaining structure
    try:
        shutil.rmtree(job_path, ignore_errors=True)
    except Exception:
        pass

def cleanup_leftover_jobs():
    """
    Zero-trust cleanup: wipes job folders older than TTL.
    """
    if not JOBS_DIR.exists():
        return 0

    cleaned = 0
    now_ts = int(time.time())
    for job_folder in JOBS_DIR.iterdir():
        if not job_folder.is_dir():
            continue
        marker_ts = read_marker_ts(job_folder)
        if marker_ts is None:
            # if marker missing, treat as leftover
            marker_ts = int(job_folder.stat().st_mtime)
        age = now_ts - marker_ts
        if age >= LEFTOVER_TTL_SECONDS:
            wipe_job_folder(job_folder)
            cleaned += 1
    return cleaned

# =========================
# Flask server (phone upload)
# =========================
flask_app = Flask(__name__)
flask_app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

# This will be set by the UI when job starts
CURRENT_JOB_PATH = {"path": None}

UPLOAD_PAGE = """
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SecurePrint Box Upload</title>
  <style>
    body { font-family: Arial, sans-serif; padding: 18px; }
    .card { max-width: 520px; margin: 0 auto; padding: 16px; border: 1px solid #ddd; border-radius: 10px; }
    .ok { color: green; }
    .warn { color: #b35c00; }
    input[type=file] { width: 100%; margin: 12px 0; }
    button { padding: 10px 14px; border: 0; border-radius: 8px; background: #111; color: white; width: 100%; }
    .small { font-size: 12px; color: #555; margin-top: 10px; }
  </style>
</head>
<body>
  <div class="card">
    <h2>Upload your file</h2>
    {% if status %}
      <p class="{{cls}}">{{status}}</p>
    {% endif %}
    {% if job_active %}
      <form method="POST" action="/upload" enctype="multipart/form-data">
        <input type="file" name="file" required />
        <button type="submit">Upload</button>
      </form>
      <p class="small">Allowed: PDF, JPG/PNG, DOC/DOCX, PPT/PPTX, XLS/XLSX, TXT • Max: 20MB</p>
    {% else %}
      <p class="warn">No active job session right now. Please ask the operator to click “Start Job”.</p>
    {% endif %}
  </div>
</body>
</html>
"""

@flask_app.get("/")
def index():
    job_active = CURRENT_JOB_PATH["path"] is not None
    return render_template_string(UPLOAD_PAGE, status=None, cls="ok", job_active=job_active)

@flask_app.post("/upload")
def upload():
    job_path = CURRENT_JOB_PATH["path"]
    if job_path is None:
        return render_template_string(UPLOAD_PAGE, status="No active session. Ask operator to Start Job.", cls="warn", job_active=False)

    if "file" not in request.files:
        return render_template_string(UPLOAD_PAGE, status="No file selected.", cls="warn", job_active=True)

    f = request.files["file"]
    if not f.filename:
        return render_template_string(UPLOAD_PAGE, status="No file selected.", cls="warn", job_active=True)

    name = safe_filename(f.filename)
    if not is_allowed(name):
        return render_template_string(UPLOAD_PAGE, status="File type not allowed.", cls="warn", job_active=True)

    dest = Path(job_path) / name
    # Prevent overwrite collisions
    if dest.exists():
        stem = dest.stem
        ext = dest.suffix
        dest = Path(job_path) / f"{stem}_{int(time.time())}{ext}"

    f.save(dest)
    return render_template_string(UPLOAD_PAGE, status=f"Uploaded: {dest.name}", cls="ok", job_active=True)

def run_server():
    # host 0.0.0.0 so phone can reach it
    flask_app.run(host="0.0.0.0", port=SERVER_PORT, debug=False, use_reloader=False)

# =========================
# Tkinter UI
# =========================
class SecurePrintUI:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("760x460")

        ensure_dirs()
        cleaned = cleanup_leftover_jobs()

        self.server_thread = None
        self.server_running = False

        self.current_job_id = None
        self.current_job_path = None
        self.ip = get_local_ip()
        self.upload_url = f"http://{self.ip}:{SERVER_PORT}/"

        # UI Layout
        top = ttk.Frame(root, padding=12)
        top.pack(fill="x")

        self.status_var = tk.StringVar()
        self.status_var.set(f"Startup: cleaned {cleaned} leftover job(s).")

        ttk.Label(top, text="SecurePrint Box (MVP)", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(top, textvariable=self.status_var).pack(anchor="w", pady=(4, 0))

        btns = ttk.Frame(root, padding=(12, 6))
        btns.pack(fill="x")

        self.btn_start = ttk.Button(btns, text="Start Job", command=self.start_job)
        self.btn_start.pack(side="left", padx=(0, 8))

        self.btn_refresh = ttk.Button(btns, text="Refresh File List", command=self.refresh_list, state="disabled")
        self.btn_refresh.pack(side="left", padx=(0, 8))

        self.btn_open = ttk.Button(btns, text="Open Selected", command=self.open_selected, state="disabled")
        self.btn_open.pack(side="left", padx=(0, 8))

        self.btn_end = ttk.Button(btns, text="End Job (Wipe)", command=self.end_job, state="disabled")
        self.btn_end.pack(side="left", padx=(0, 8))

        self.btn_emergency = ttk.Button(btns, text="Emergency Clean All", command=self.emergency_clean)
        self.btn_emergency.pack(side="right")

        mid = ttk.Frame(root, padding=12)
        mid.pack(fill="both", expand=True)

        left = ttk.Frame(mid)
        left.pack(side="left", fill="both", expand=True)

        right = ttk.Frame(mid)
        right.pack(side="right", fill="y")

        ttk.Label(left, text="Files in Current Job:", font=("Segoe UI", 11, "bold")).pack(anchor="w")

        self.listbox = tk.Listbox(left, height=14)
        self.listbox.pack(fill="both", expand=True, pady=(6, 0))

        ttk.Label(right, text="Upload QR (Phone → PC):", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.qr_label = ttk.Label(right)
        self.qr_label.pack(pady=(8, 8))

        self.url_label = ttk.Label(right, text=self.upload_url, wraplength=220)
        self.url_label.pack(anchor="w")

        self.job_label = ttk.Label(right, text="No active job.", wraplength=220)
        self.job_label.pack(anchor="w", pady=(10, 0))

        self._set_qr("Start a job to enable uploads.")

        # Start server once
        self.start_server_if_needed()

    def start_server_if_needed(self):
        if self.server_running:
            return
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.server_running = True
        self.status_var.set("Server started. Ready for Start Job.")

    def _set_qr(self, caption: str):
        # Generate QR for upload_url
        img = qrcode.make(self.upload_url)
        img = img.resize((220, 220))
        self.qr_imgtk = ImageTk.PhotoImage(img)
        self.qr_label.configure(image=self.qr_imgtk)
        self.url_label.configure(text=self.upload_url)
        self.job_label.configure(text=caption)

    def start_job(self):
        self.current_job_id = now_job_id()
        self.current_job_path = JOBS_DIR / self.current_job_id
        self.current_job_path.mkdir(parents=True, exist_ok=True)
        write_marker(self.current_job_path)

        CURRENT_JOB_PATH["path"] = str(self.current_job_path)

        self.status_var.set(f"Job started: {self.current_job_id}")
        self._set_qr(f"Active Job: {self.current_job_id}\nUploads go to:\n{self.current_job_path}")

        self.btn_refresh.configure(state="normal")
        self.btn_open.configure(state="normal")
        self.btn_end.configure(state="normal")
        self.refresh_list()

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        if not self.current_job_path:
            return
        for f in sorted(self.current_job_path.iterdir()):
            if f.is_file() and f.name != ".jobmeta":
                self.listbox.insert(tk.END, f.name)

    def open_selected(self):
        if not self.current_job_path:
            return
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo(APP_NAME, "Select a file first.")
            return
        filename = self.listbox.get(sel[0])
        file_path = self.current_job_path / filename
        if not file_path.exists():
            messagebox.showwarning(APP_NAME, "File not found.")
            self.refresh_list()
            return

        # Open with default app (user can print normally)
        try:
            os.startfile(str(file_path))  # Windows-only
            self.status_var.set(f"Opened: {filename} (Print as usual)")
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Could not open file:\n{e}")

    def end_job(self):
        if not self.current_job_path:
            return
        ans = messagebox.askyesno(APP_NAME, "End Job and wipe all files?")
        if not ans:
            return

        job_path = self.current_job_path

        # disable uploads immediately
        CURRENT_JOB_PATH["path"] = None

        self.status_var.set(f"Wiping: {job_path.name} ...")
        self.root.update_idletasks()

        wipe_job_folder(job_path)

        self.current_job_id = None
        self.current_job_path = None

        self.listbox.delete(0, tk.END)
        self._set_qr("No active job. Start a job to enable uploads.")
        self.status_var.set("Job wiped successfully. 0 files remaining.")

        self.btn_refresh.configure(state="disabled")
        self.btn_open.configure(state="disabled")
        self.btn_end.configure(state="disabled")

    def emergency_clean(self):
        ans = messagebox.askyesno(APP_NAME, "Emergency Clean ALL jobs folder? (Wipes everything)")
        if not ans:
            return

        # disable uploads
        CURRENT_JOB_PATH["path"] = None

        self.status_var.set("Emergency cleaning all jobs...")
        self.root.update_idletasks()

        if JOBS_DIR.exists():
            for job in JOBS_DIR.iterdir():
                if job.is_dir():
                    wipe_job_folder(job)

        self.current_job_id = None
        self.current_job_path = None
        self.listbox.delete(0, tk.END)
        self._set_qr("No active job. Start a job to enable uploads.")
        self.status_var.set("Emergency clean complete.")
        self.btn_refresh.configure(state="disabled")
        self.btn_open.configure(state="disabled")
        self.btn_end.configure(state="disabled")


def main():
    ensure_dirs()
    root = tk.Tk()
    # Use ttk styling
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    app = SecurePrintUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
