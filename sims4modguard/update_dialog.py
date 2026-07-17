"""
update_dialog.py
Cyberpunk-themed update notification dialog for Sims4ModGuard.
Shows when a new GitHub release is available.
"""

import threading
import tkinter as tk
import customtkinter as ctk
from sims4modguard import updater

BG       = "#050510"
BG_CARD  = "#0f0f25"
NEON_GRN = "#00ff9f"
NEON_CYN = "#00e5ff"
NEON_RED = "#ff003c"
NEON_AMB = "#ffaa00"
TEXT_DIM = "#5a6080"
FONT_TTL = ("Courier New", 16, "bold")
FONT_LBL = ("Courier New", 10)
FONT_BTN = ("Courier New", 11, "bold")
FONT_SML = ("Courier New", 8)


class UpdateDialog(ctk.CTkToplevel):
    def __init__(self, parent, release_info: dict):
        super().__init__(parent)
        self.release_info = release_info
        self.title("Sims4ModGuard — Update Available")
        self.geometry("520x380")
        self.configure(fg_color=BG)
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self.focus_force()

        # Center on parent
        self.update_idletasks()
        px = parent.winfo_x() + parent.winfo_width() // 2 - 260
        py = parent.winfo_y() + parent.winfo_height() // 2 - 190
        self.geometry(f"+{px}+{py}")

        self._build_ui()

    def _build_ui(self):
        info = self.release_info

        # Header
        hdr = ctk.CTkFrame(self, fg_color="#070718", corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text=">> UPDATE AVAILABLE",
                     font=FONT_TTL, text_color=NEON_GRN).pack(pady=12)

        # Version info
        ver_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=6)
        ver_frame.pack(fill="x", padx=16, pady=(12, 0))
        ctk.CTkLabel(ver_frame,
                     text=f"  Current: v{info['current_version']}   →   New: v{info['new_version']}",
                     font=FONT_LBL, text_color=NEON_CYN, anchor="w").pack(fill="x", padx=8, pady=6)

        # Changelog
        if info.get("changelog"):
            ctk.CTkLabel(self, text="WHAT'S NEW:", font=FONT_SML,
                         text_color=TEXT_DIM).pack(anchor="w", padx=16, pady=(10, 2))
            log_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=6)
            log_frame.pack(fill="x", padx=16)
            log_txt = tk.Text(log_frame, height=5, bg=BG_CARD, fg=TEXT_DIM,
                              font=("Courier New", 8), relief="flat", bd=0, wrap=tk.WORD)
            log_txt.insert("1.0", info["changelog"])
            log_txt.configure(state="disabled")
            log_txt.pack(fill="x", padx=6, pady=4)

        # Progress bar (hidden until download starts)
        self._progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._progress_frame.pack(fill="x", padx=16, pady=(8, 0))
        self._status_label = ctk.CTkLabel(self._progress_frame, text="",
                                          font=FONT_SML, text_color=NEON_AMB)
        self._status_label.pack(anchor="w")
        self._progress = ctk.CTkProgressBar(self._progress_frame,
                                             progress_color=NEON_GRN,
                                             fg_color=BG_CARD, height=8, corner_radius=3)
        self._progress.set(0)
        self._progress_frame.pack_forget()  # hidden initially

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=12)

        self._update_btn = ctk.CTkButton(
            btn_frame, text=">> UPDATE NOW", font=FONT_BTN,
            fg_color="transparent", border_color=NEON_GRN, border_width=2,
            text_color=NEON_GRN, hover_color="#002d1e", corner_radius=4,
            command=self._start_download
        )
        self._update_btn.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text="SKIP", font=FONT_BTN,
            fg_color="transparent", border_color=TEXT_DIM, border_width=1,
            text_color=TEXT_DIM, hover_color="#0a0a1a", corner_radius=4,
            command=self.destroy
        ).pack(side="left")

    def _start_download(self):
        if not self.release_info.get("download_url"):
            import webbrowser
            webbrowser.open(self.release_info.get("html_url", "https://github.com/HuciferX/Sims4ModGuard/releases"))
            self.destroy()
            return

        self._update_btn.configure(state="disabled", text="DOWNLOADING...")
        self._progress_frame.pack(fill="x", padx=16, pady=(8, 0))
        self._progress.pack(fill="x", pady=(2, 0))
        self._status_label.configure(text="Connecting to GitHub...")

        def _download():
            def _on_progress(pct: float):
                self.after(0, lambda: self._set_progress(pct))

            path = updater.download_update(self.release_info["download_url"], _on_progress)
            self.after(0, lambda: self._on_download_done(path))

        threading.Thread(target=_download, daemon=True).start()

    def _set_progress(self, pct: float):
        self._progress.set(pct)
        pct_int = int(pct * 100)
        if pct < 1.0:
            self._status_label.configure(text=f"Downloading v{self.release_info['new_version']}... {pct_int}%")
        else:
            self._status_label.configure(text="Applying update...")

    def _on_download_done(self, path):
        if path:
            self._status_label.configure(text="Restarting...", text_color=NEON_GRN)
            self.after(800, lambda: updater.apply_update(path))
        else:
            self._status_label.configure(text="Download failed. Opening GitHub...", text_color=NEON_RED)
            import webbrowser
            webbrowser.open(self.release_info.get("html_url", ""))
            self.after(1500, self.destroy)
