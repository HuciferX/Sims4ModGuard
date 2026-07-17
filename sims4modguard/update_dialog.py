"""
UpdateDialog — cyberpunk-themed update prompt for Sims4ModGuard.

Opens when a newer GitHub release is found.  Shows current/new version,
a changelog excerpt, and two buttons: UPDATE NOW or SKIP THIS TIME.

When UPDATE is clicked:
  • An animated neon-green progress bar fills as the exe downloads.
  • Status text updates: "Downloading v1.2... 45%", "Applying update...", "Restarting..."
  • On success: new exe is written next to the current one, relaunched, this one exits.
  • On failure: error message shown, dialog closes (app continues normally).
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Optional

import customtkinter as ctk
import tkinter as tk

# ── Theme constants (mirror gui_app.py) ────────────────────────────────────────
BG_DEEP    = "#050510"
BG_CARD    = "#0f0f25"
BG_HEADER  = "#070718"

NEON_GREEN = "#00ff9f"
NEON_CYAN  = "#00e5ff"
NEON_PINK  = "#ff00dd"
NEON_RED   = "#ff003c"

TEXT_DIM   = "#5a6080"
TEXT_MAIN  = "#d0d8f0"

FONT_TITLE  = ("Courier New", 16, "bold")
FONT_HEAD   = ("Courier New", 12, "bold")
FONT_MONO   = ("Courier New", 10)
FONT_SMALL  = ("Courier New", 9)
FONT_BTN    = ("Courier New", 11, "bold")

_CHANGELOG_MAX_CHARS = 600  # trim long release notes


def _dim_color(hex_color: str, factor: float = 0.20) -> str:
    """Return a darkened version of a hex colour for hover states."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "#0a0a1a"
    r = int(int(h[0:2], 16) * factor)
    g = int(int(h[2:4], 16) * factor)
    b = int(int(h[4:6], 16) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def _exe_dest() -> Path:
    """Return the Path where the downloaded exe should be written.

    When frozen (PyInstaller), that is sys.executable itself.
    When running from source, we write next to gui_app.py / repo root.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    # Running from source — write into the repo root so it can be tested
    return Path(__file__).parent.parent / "Sims4ModGuard.exe"


class UpdateDialog(ctk.CTkToplevel):
    """Modal dialog that offers to download and install a new release."""

    def __init__(
        self,
        parent,
        current_version: str,
        new_version: str,
        changelog: str,
        exe_url: str,
    ):
        super().__init__(parent)

        self._parent       = parent
        self._new_version  = new_version
        self._exe_url      = exe_url
        self._downloading  = False

        # ── Window setup ───────────────────────────────────────────────────────
        self.title("🦉 Hypatia — Update Available")
        self.configure(fg_color=BG_DEEP)
        self.resizable(False, False)
        self.attributes("-topmost", True)

        # Centre on parent
        self.update_idletasks()
        pw = parent.winfo_width()  or 1100
        ph = parent.winfo_height() or 780
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        dw, dh = 560, 440
        self.geometry(f"{dw}x{dh}+{px + (pw - dw)//2}+{py + (ph - dh)//2}")

        self._build_ui(current_version, new_version, changelog)

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self, current_ver: str, new_ver: str, changelog: str):
        # ── Header ─────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=BG_HEADER,
                           border_color=NEON_GREEN, border_width=1,
                           corner_radius=0)
        hdr.pack(fill="x")

        ctk.CTkLabel(hdr,
                     text="  ▶▶  UPDATE AVAILABLE",
                     font=FONT_TITLE,
                     text_color=NEON_GREEN).pack(side="left", padx=14, pady=12)

        ctk.CTkLabel(hdr,
                     text="🦉 Hypatia",
                     font=("Courier New", 10, "bold"),
                     text_color=NEON_PINK).pack(side="right", padx=14)

        # Animated scan-line
        self._sl_canvas = tk.Canvas(hdr, height=2, bg=BG_HEADER,
                                    highlightthickness=0)
        self._sl_canvas.pack(fill="x")
        self._sl_x = 0
        self._animate_scanline()

        # ── Version row ────────────────────────────────────────────────────────
        ver_row = ctk.CTkFrame(self, fg_color="transparent")
        ver_row.pack(fill="x", padx=20, pady=(16, 4))

        ctk.CTkLabel(ver_row,
                     text=f"CURRENT VERSION",
                     font=FONT_SMALL, text_color=TEXT_DIM).grid(
                         row=0, column=0, padx=(0, 30), sticky="w")
        ctk.CTkLabel(ver_row,
                     text=f"NEW VERSION",
                     font=FONT_SMALL, text_color=TEXT_DIM).grid(
                         row=0, column=1, sticky="w")

        ctk.CTkLabel(ver_row,
                     text=f"v{current_ver}",
                     font=("Courier New", 20, "bold"),
                     text_color=TEXT_DIM).grid(
                         row=1, column=0, padx=(0, 30), sticky="w")

        ctk.CTkLabel(ver_row,
                     text=f"v{new_ver.lstrip('vV')}",
                     font=("Courier New", 20, "bold"),
                     text_color=NEON_GREEN).grid(
                         row=1, column=1, sticky="w")

        # ── Changelog ──────────────────────────────────────────────────────────
        ctk.CTkLabel(self,
                     text="  RELEASE NOTES",
                     font=FONT_HEAD, text_color=NEON_CYAN).pack(
                         anchor="w", padx=20, pady=(10, 4))

        cl_frame = ctk.CTkFrame(self, fg_color=BG_CARD,
                                border_color="#003d4d", border_width=1,
                                corner_radius=6)
        cl_frame.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        excerpt = changelog.strip()
        if len(excerpt) > _CHANGELOG_MAX_CHARS:
            excerpt = excerpt[:_CHANGELOG_MAX_CHARS].rsplit("\n", 1)[0] + "\n  ..."

        self._cl_text = tk.Text(
            cl_frame,
            bg=BG_CARD, fg=TEXT_MAIN,
            font=FONT_SMALL,
            relief="flat", borderwidth=0,
            wrap=tk.WORD,
            state="disabled",
            height=8,
        )
        sb = ctk.CTkScrollbar(cl_frame, command=self._cl_text.yview,
                              button_color="#003d4d")
        sb.pack(side="right", fill="y")
        self._cl_text.configure(yscrollcommand=sb.set)
        self._cl_text.pack(fill="both", expand=True, padx=8, pady=6)
        self._cl_text.configure(state="normal")
        self._cl_text.insert("1.0", excerpt or "(No release notes provided.)")
        self._cl_text.configure(state="disabled")

        # ── Progress bar (hidden until download starts) ────────────────────────
        prog_frame = ctk.CTkFrame(self, fg_color="transparent")
        prog_frame.pack(fill="x", padx=20, pady=(0, 4))

        self._progress_bar = ctk.CTkProgressBar(
            prog_frame,
            progress_color=NEON_GREEN,
            fg_color=BG_CARD,
            height=8,
            corner_radius=2,
        )
        self._progress_bar.set(0)
        # Hidden by default; shown on update start
        self._prog_frame = prog_frame

        self._status_var = tk.StringVar(value="")
        self._status_lbl = ctk.CTkLabel(
            self, textvariable=self._status_var,
            font=FONT_SMALL, text_color=NEON_CYAN)
        self._status_lbl.pack(anchor="w", padx=22, pady=(0, 8))

        # ── Buttons ────────────────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 16))

        self._update_btn = ctk.CTkButton(
            btn_row,
            text=">> UPDATE NOW",
            command=self._start_update,
            fg_color="transparent",
            border_color=NEON_GREEN,
            border_width=2,
            text_color=NEON_GREEN,
            hover_color=_dim_color(NEON_GREEN, 0.20),
            font=FONT_BTN,
            corner_radius=4,
            height=40,
        )
        self._update_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._skip_btn = ctk.CTkButton(
            btn_row,
            text="SKIP THIS TIME",
            command=self._skip,
            fg_color="transparent",
            border_color=TEXT_DIM,
            border_width=1,
            text_color=TEXT_DIM,
            hover_color=_dim_color(TEXT_DIM, 0.15),
            font=("Courier New", 10),
            corner_radius=4,
            height=40,
        )
        self._skip_btn.pack(side="left", fill="x", expand=True)

    # ── Scan-line animation ────────────────────────────────────────────────────

    def _animate_scanline(self):
        try:
            c = self._sl_canvas
            w = c.winfo_width() or 560
            c.delete("sl")
            x = self._sl_x % (w + 200)
            c.create_line(x - 200, 1, x, 1, fill=NEON_GREEN, width=2, tags="sl")
            self._sl_x += 10
            self.after(30, self._animate_scanline)
        except Exception:
            pass  # dialog may have been destroyed

    # ── Button handlers ────────────────────────────────────────────────────────

    def _skip(self):
        """User chose to skip this update — close and continue."""
        self.destroy()

    def _start_update(self):
        """Kick off the background download thread."""
        if self._downloading:
            return
        self._downloading = True

        # Disable buttons, show progress bar
        self._update_btn.configure(state="disabled", text="⏳  Downloading...")
        self._skip_btn.configure(state="disabled")
        self._progress_bar.pack(fill="x")
        self._progress_bar.set(0)

        thread = threading.Thread(target=self._download_worker, daemon=True)
        thread.start()

    def _download_worker(self):
        """Background thread: download → replace → relaunch."""
        from sims4modguard.updater import download_asset, relaunch_exe

        dest = _exe_dest()
        new_ver = self._new_version

        def _progress(done: int, total: int):
            pct = int(done / total * 100) if total else 0
            val = done / total if total else 0
            self.after(0, lambda: self._set_progress(val, f"Downloading v{new_ver}... {pct}%"))

        self.after(0, lambda: self._status_var.set(f"Downloading v{new_ver}..."))

        success = download_asset(self._exe_url, dest, _progress)

        if not success:
            self.after(0, self._on_download_failed)
            return

        # Applying update phase
        self.after(0, lambda: self._set_progress(1.0, "Applying update..."))
        self.after(600, lambda: self._set_progress(1.0, "Restarting..."))
        self.after(1200, lambda: self._finish_update(dest))

    def _set_progress(self, value: float, status: str):
        try:
            self._progress_bar.set(value)
            self._status_var.set(status)
        except Exception:
            pass

    def _on_download_failed(self):
        self._status_var.set("⚠  Download failed — check your connection and try again.")
        self._update_btn.configure(
            state="normal",
            text=">> RETRY UPDATE",
        )
        self._skip_btn.configure(state="normal")
        self._downloading = False

    def _finish_update(self, exe_path: Path):
        """Relaunch the new exe and exit — called from the Tk main thread."""
        from sims4modguard.updater import relaunch_exe
        try:
            relaunch_exe(exe_path)
        except Exception as exc:
            self._status_var.set(f"Relaunch error: {exc}")
            self._skip_btn.configure(state="normal")
            self._downloading = False
