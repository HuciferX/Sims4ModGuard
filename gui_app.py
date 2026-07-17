"""
Sims4ModGuard -- GUI
Cyberpunk Hacker Console for Sims 4 Mod Management

By Hucifer & Hypatia
"""

import sys
import os
import shutil
import threading
import queue
import time
import random
import subprocess
import re
import webbrowser
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk

from sims4modguard.cache_manager  import find_s4_folder, read_game_version, get_cache_state, clear_caches
from sims4modguard.scanner        import scan_all_scripts, SEVERITY_CRITICAL, SEVERITY_WARNING
from sims4modguard.cc_cleaner     import scan_all_packages
from sims4modguard.log_parser     import parse_log
from sims4modguard.quarantine     import QuarantineManager
from sims4modguard.dlc_database   import DLC_CATALOG, TYPE_COLOR, dlc_summary
from sims4modguard.game_index     import GameIndex, DEFAULT_GAME_ROOT
from sims4modguard.boot_engine    import BootEngine, PHASES
from sims4modguard.save_analyzer  import SaveAnalyzer
from sims4modguard.run_logger     import RunLogger
from sims4modguard.mod_database   import lookup_mod
from sims4modguard.step_indicator  import StepIndicator, ConnectorLine
from sims4modguard              import updater as _updater

# -- Theme constants ------------------------------------------------------------
BG_DEEP     = "#050510"
BG_PANEL    = "#0a0a1a"
BG_CARD     = "#0f0f25"
BG_HEADER   = "#070718"

NEON_GREEN  = "#00ff9f"
NEON_CYAN   = "#00e5ff"
NEON_PINK   = "#ff00dd"
NEON_AMBER  = "#ffaa00"
NEON_RED    = "#ff003c"
NEON_PURPLE = "#9d00ff"

TEXT_MAIN   = "#d0d8f0"
TEXT_DIM    = "#5a6080"
TEXT_BRIGHT = "#ffffff"

FONT_MONO   = ("Courier New", 10)
FONT_MONO_S = ("Courier New", 9)
FONT_TITLE  = ("Courier New", 22, "bold")
FONT_HEAD   = ("Courier New", 13, "bold")
FONT_LABEL  = ("Courier New", 10)
FONT_BTN    = ("Courier New", 11, "bold")
FONT_SMALL  = ("Courier New", 8)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

PLUMBOB = """
    <>
   <><><>
  <><><><><>
   <><><>
    <>
""".strip()

BANNER_ART = "** SIMS 4 MOD GUARDIAN **"

# -- Utility helpers ------------------------------------------------------------

# ── Toast notification ─────────────────────────────────────────────────────────

class Toast:
    """
    Small slide-in notification in the bottom-right corner.
    Auto-dismisses after `duration` ms.  Multiple toasts stack upward.
    """
    _stack: list = []          # class-level stack of active toasts
    _OFFSET_Y = 48             # vertical spacing between stacked toasts

    def __init__(self, parent, message: str, sev: str = "ok", duration: int = 3500):
        colors = {
            "ok":       ("#00ff9f", "#001a0d"),
            "warning":  ("#ffaa00", "#1a0d00"),
            "critical": ("#ff003c", "#1a000a"),
            "info":     ("#00e5ff", "#001a1a"),
        }
        fg, bg = colors.get(sev, colors["ok"])

        self._win = ctk.CTkToplevel(parent)
        self._win.withdraw()
        self._win.overrideredirect(True)
        self._win.configure(fg_color=bg)
        self._win.attributes("-topmost", True)
        self._win.attributes("-alpha", 0.0)

        # Content
        frame = ctk.CTkFrame(self._win, fg_color=bg,
                             border_color=fg, border_width=1,
                             corner_radius=6)
        frame.pack(padx=0, pady=0)
        ctk.CTkLabel(frame, text=message,
                     font=("Courier New", 10, "bold"),
                     text_color=fg,
                     wraplength=340).pack(padx=14, pady=10)

        Toast._stack.append(self)
        parent.update_idletasks()
        self._win.update_idletasks()

        # Position bottom-right
        sw = parent.winfo_screenwidth()
        sh = parent.winfo_screenheight()
        tw = max(self._win.winfo_reqwidth(), 300)
        th = self._win.winfo_reqheight()
        stack_idx = len(Toast._stack) - 1
        tx = sw - tw - 24
        ty = sh - 80 - (th + self._OFFSET_Y) * stack_idx - th
        self._win.geometry(f"{tw}x{th}+{tx}+{ty}")
        self._win.deiconify()

        # Fade in
        self._fade(parent, 0.0, 1.0, 150, duration)

    def _fade(self, parent, current_alpha: float, target: float,
              step_ms: int, dismiss_after_ms: int):
        new_alpha = current_alpha + (0.1 if target > current_alpha else -0.1)
        new_alpha = max(0.0, min(1.0, new_alpha))
        try:
            self._win.attributes("-alpha", new_alpha)
        except Exception:
            self._dismiss(); return

        if abs(new_alpha - target) > 0.05:
            parent.after(step_ms, lambda: self._fade(parent, new_alpha, target,
                                                      step_ms, dismiss_after_ms))
        elif target == 1.0:
            # Fully visible — schedule dismiss
            parent.after(dismiss_after_ms,
                         lambda: self._fade(parent, 1.0, 0.0, 60, 0))
        else:
            # Faded out
            self._dismiss()

    def _dismiss(self):
        try:
            self._win.destroy()
        except Exception:
            pass
        if self in Toast._stack:
            Toast._stack.remove(self)


def _dim_color(hex_color: str, factor: float = 0.25) -> str:
    """
    Return a darkened 6-char hex color suitable for button hover states.
    Tkinter does NOT support 8-char hex (RGBA) — this replaces the broken
    `color + "22"` pattern that caused repeated CTk errors.
    """
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "#0a0a1a"
    r = int(int(h[0:2], 16) * factor)
    g = int(int(h[2:4], 16) * factor)
    b = int(int(h[4:6], 16) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def neon_frame(parent, color=NEON_GREEN, **kwargs):
    """Frame with colored border."""
    f = ctk.CTkFrame(parent, fg_color=BG_CARD,
                     border_color=color, border_width=1, **kwargs)
    return f


class NeonButton(ctk.CTkButton):
    def __init__(self, parent, text, command=None, color=NEON_GREEN, **kwargs):
        super().__init__(
            parent,
            text=text,
            command=command,
            fg_color="transparent",
            border_color=color,
            border_width=2,
            text_color=color,
            hover_color=_dim_color(color, 0.25),
            font=FONT_BTN,
            corner_radius=4,
            **kwargs,
        )


class ConsoleText(tk.Text):
    """Scrollable terminal output widget with neon styling."""
    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            bg=BG_DEEP,
            fg=NEON_GREEN,
            font=FONT_MONO,
            insertbackground=NEON_GREEN,
            selectbackground="#002d1e",
            wrap=tk.WORD,
            relief="flat",
            borderwidth=0,
            **kwargs,
        )
        self.tag_config("critical", foreground=NEON_RED)
        self.tag_config("warning",  foreground=NEON_AMBER)
        self.tag_config("ok",       foreground=NEON_GREEN)
        self.tag_config("info",     foreground=NEON_CYAN)
        self.tag_config("dim",      foreground=TEXT_DIM)
        self.tag_config("pink",     foreground=NEON_PINK)
        self.tag_config("bold",     foreground=TEXT_BRIGHT, font=("Courier New", 10, "bold"))
        self.tag_config("header",   foreground=NEON_CYAN,   font=("Courier New", 11, "bold"))

    def append(self, text: str, tag: str = ""):
        self.configure(state="normal")
        if tag:
            self.insert(tk.END, text + "\n", tag)
        else:
            self.insert(tk.END, text + "\n")
        self.see(tk.END)
        self.configure(state="disabled")

    def clear(self):
        self.configure(state="normal")
        self.delete("1.0", tk.END)
        self.configure(state="disabled")


# -- Stat card -----------------------------------------------------------------

class StatCard(ctk.CTkFrame):
    def __init__(self, parent, label: str, value: str = "--",
                 color: str = NEON_CYAN, **kwargs):
        super().__init__(parent, fg_color=BG_CARD,
                         border_color=color, border_width=1,
                         corner_radius=6, **kwargs)
        self._color = color
        self._lbl_var = tk.StringVar(value=value)
        ctk.CTkLabel(self, text=label, font=FONT_SMALL,
                     text_color=TEXT_DIM).pack(pady=(8, 0))
        ctk.CTkLabel(self, textvariable=self._lbl_var,
                     font=("Courier New", 18, "bold"),
                     text_color=color).pack(pady=(0, 8))

    def set(self, value: str):
        self._lbl_var.set(value)


# -- Main Application ----------------------------------------------------------

class Sims4ModGuardApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("[ SIMS4 MOD GUARDIAN ]  by Hucifer + Hypatia")
        self.geometry("1100x780")
        self.minsize(900, 650)
        self.configure(fg_color=BG_DEEP)

        self.s4_folder:  Path | None = None
        self.mods_folder: Path | None = None
        self.qm: QuarantineManager | None = None
        self._q = queue.Queue()
        self._scan_results = None
        self._cc_data = None

        # Build UI
        self._build_ui()

        # Auto-detect on start
        self.after(300, self._auto_detect)
        self.after(100, self._poll_queue)

        # Boot sequence
        self.after(600, self._boot_sequence)

        # Auto-update check (runs 2 s after launch so the UI appears first)
        self.after(2000, self._check_for_updates)

    # -- Build UI --------------------------------------------------------------

    def _build_ui(self):
        # Header
        self._build_header()

        # Content area
        content = ctk.CTkFrame(self, fg_color=BG_DEEP)
        content.pack(fill="both", expand=True, padx=8, pady=4)
        content.columnconfigure(0, weight=1)

        # Folder + stats row
        self._build_folder_row(content)

        # Tabs
        self._build_tabs(content)

        # Status bar
        self._build_statusbar()

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=BG_HEADER,
                            border_color=NEON_GREEN, border_width=1,
                            corner_radius=0)
        hdr.pack(fill="x", padx=0, pady=0)

        # Left: plumbob + title
        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left", padx=16, pady=8)

        ctk.CTkLabel(left,
                     text="<>",
                     font=("Courier New", 32, "bold"),
                     text_color=NEON_GREEN).pack(side="left", padx=(0, 10))

        title_box = ctk.CTkFrame(left, fg_color="transparent")
        title_box.pack(side="left")
        ctk.CTkLabel(title_box,
                     text="SIMS4 MOD GUARDIAN",
                     font=("Courier New", 20, "bold"),
                     text_color=NEON_GREEN).pack(anchor="w")
        ctk.CTkLabel(title_box,
                     text="Patch Compatibility Scanner & Auto-Repair Console",
                     font=("Courier New", 9),
                     text_color=TEXT_DIM).pack(anchor="w")

        # Right: branding
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right", padx=16, pady=8)

        ctk.CTkLabel(right,
                     text="by  Hucifer  &  Hypatia",
                     font=("Courier New", 11, "bold"),
                     text_color=NEON_PINK).pack(anchor="e")
        ctk.CTkLabel(right,
                     text="v1.0  *  Community Edition",
                     font=("Courier New", 8),
                     text_color=TEXT_DIM).pack(anchor="e")

        # Animated scan line
        self._scanline_canvas = tk.Canvas(hdr, height=2, bg=BG_HEADER,
                                          highlightthickness=0)
        self._scanline_canvas.pack(fill="x")
        self._scanline_x = 0
        self._animate_scanline()

    def _animate_scanline(self):
        c = self._scanline_canvas
        w = c.winfo_width() or 1100
        c.delete("line")
        x = self._scanline_x % (w + 200)
        c.create_line(x - 200, 1, x, 1, fill=NEON_GREEN, width=2, tags="line")
        self._scanline_x += 8
        self.after(30, self._animate_scanline)

    def _build_folder_row(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.grid(row=0, column=0, sticky="ew", pady=(6, 4))
        row.columnconfigure(1, weight=1)

        # Folder icon + label
        ctk.CTkLabel(row, text="ðŸ“ SIMS4 FOLDER:",
                     font=FONT_LABEL, text_color=NEON_CYAN).grid(
            row=0, column=0, padx=(0, 8), sticky="w")

        self._folder_var = tk.StringVar(value="Auto-detecting...")
        folder_entry = ctk.CTkEntry(row, textvariable=self._folder_var,
                                    font=FONT_MONO_S, fg_color=BG_CARD,
                                    border_color=NEON_CYAN, border_width=1,
                                    text_color=NEON_GREEN)
        folder_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))

        NeonButton(row, "BROWSE", self._browse_folder,
                   color=NEON_CYAN, width=90).grid(row=0, column=2, padx=(0, 8))
        NeonButton(row, "AUTO", self._auto_detect,
                   color=NEON_GREEN, width=70).grid(row=0, column=3)

        # Stats row
        stats_row = ctk.CTkFrame(parent, fg_color="transparent")
        stats_row.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        for i in range(6):
            stats_row.columnconfigure(i, weight=1)

        self._stat_version  = StatCard(stats_row, "GAME VERSION", color=NEON_CYAN)
        self._stat_scripts  = StatCard(stats_row, "SCRIPTS",      color=NEON_GREEN)
        self._stat_packages = StatCard(stats_row, "PACKAGES",     color=NEON_GREEN)
        self._stat_disabled = StatCard(stats_row, "QUARANTINED",  color=NEON_AMBER)
        self._stat_issues   = StatCard(stats_row, "ISSUES FOUND", color=NEON_RED)
        self._stat_cache    = StatCard(stats_row, "CACHE (MB)",   color=TEXT_DIM)

        for i, card in enumerate([self._stat_version, self._stat_scripts,
                                   self._stat_packages, self._stat_disabled,
                                   self._stat_issues, self._stat_cache]):
            card.grid(row=0, column=i, padx=4, sticky="nsew")

    def _build_tabs(self, parent):
        # Tab bar
        tab_bar = ctk.CTkFrame(parent, fg_color=BG_PANEL,
                               border_color="#003d26", border_width=1,
                               corner_radius=6)
        tab_bar.grid(row=2, column=0, sticky="nsew", pady=(0, 0))
        parent.rowconfigure(2, weight=1)

        # Left: tab buttons
        tab_btn_col = ctk.CTkFrame(tab_bar, fg_color=BG_HEADER, width=210)
        tab_btn_col.pack(side="left", fill="y", padx=(0, 1))
        tab_btn_col.pack_propagate(False)

        self._tab_content = ctk.CTkFrame(tab_bar, fg_color=BG_PANEL)
        self._tab_content.pack(side="left", fill="both", expand=True)

        self._tab_frames = {}
        self._tab_btns   = {}

        # (icon, key, label, builder)
        tabs = [
            ("\u2756", "wizard",     "WIZARD",       self._build_wizard_tab),
            ("\U0001f50d", "scan",       "SCAN SCRIPTS", self._build_scan_tab),
            ("\u2699",  "cc",         "CC CLEANER",   self._build_cc_tab),
            ("\U0001f4cb", "logs",       "LOG ANALYZER", self._build_logs_tab),
            ("\U0001f527", "fix",        "FIX & REPAIR", self._build_fix_tab),
            ("\U0001f4e6", "inventory",  "INVENTORY",    self._build_inventory_tab),
            ("\u25b6",  "bootsim",    "BOOT SIM",     self._build_bootsim_tab),
            ("\U0001f4be", "savedoctor", "SAVE DOCTOR",  self._build_savedoctor_tab),
            ("\U0001f4c4", "report",     "REPORT",       self._build_report_tab),
            (">_",      "console",    "CONSOLE",      self._build_console_tab),
            ("\U0001f680", "launcher",   "LAUNCHER",     self._build_launcher_tab),
            ("\u24d8",  "about",      "ABOUT",        self._build_about_tab),
        ]

        # Nav header
        hdr_f = ctk.CTkFrame(tab_btn_col, fg_color="#050520",
                             height=44, corner_radius=0)
        hdr_f.pack(fill="x")
        hdr_f.pack_propagate(False)
        ctk.CTkLabel(hdr_f, text="\U0001f989 HYPATIA",
                     font=("Courier New", 11, "bold"),
                     text_color=NEON_GREEN).pack(side="left", padx=10, pady=10)

        for icon, key, label, builder in tabs:
            frame = ctk.CTkFrame(self._tab_content, fg_color=BG_PANEL)
            builder(frame)
            self._tab_frames[key] = frame

            btn_frame = ctk.CTkFrame(tab_btn_col, fg_color="transparent",
                                      corner_radius=0, height=40)
            btn_frame.pack(fill="x", padx=0, pady=0)
            btn_frame.pack_propagate(False)
            btn_frame.columnconfigure(1, weight=1)

            icon_lbl = ctk.CTkLabel(btn_frame, text=icon,
                                     font=("Segoe UI Emoji", 14),
                                     text_color=TEXT_DIM, width=36)
            icon_lbl.grid(row=0, column=0, padx=(8, 0))

            text_lbl = ctk.CTkLabel(btn_frame, text=label,
                                     font=("Courier New", 9, "bold"),
                                     text_color=TEXT_DIM, anchor="w")
            text_lbl.grid(row=0, column=1, sticky="ew", padx=(4, 8))

            # Left accent bar (hidden by default, shown when active)
            accent = ctk.CTkFrame(btn_frame, fg_color=TEXT_DIM,
                                   width=3, corner_radius=0)
            accent.place(x=0, y=0, relheight=1)

            def _on_click(k=key, bf=btn_frame, ac=accent,
                          il=icon_lbl, tl=text_lbl):
                self._switch_tab(k)

            btn_frame.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))
            icon_lbl.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))
            text_lbl.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))
            btn_frame.bind("<Enter>",
                lambda e, bf=btn_frame: bf.configure(fg_color="#0a0a20"))
            btn_frame.bind("<Leave>",
                lambda e, bf=btn_frame: bf.configure(
                    fg_color=BG_CARD if bf.cget('fg_color') == "#0a0a20" or
                    bf.cget('fg_color') == "#0a0a20" else "transparent"))

            self._tab_btns[key] = {
                "frame": btn_frame, "icon": icon_lbl,
                "text": text_lbl, "accent": accent,
            }

        # Show wizard tab first
        self._switch_tab("wizard")

    def _switch_tab(self, key: str):
        for k, f in self._tab_frames.items():
            f.pack_forget()
        # Reset all nav buttons to dim
        for k, bdict in self._tab_btns.items():
            bdict["frame"].configure(fg_color="transparent")
            bdict["icon"].configure(text_color=TEXT_DIM)
            bdict["text"].configure(text_color=TEXT_DIM)
            bdict["accent"].configure(fg_color="transparent")

        self._tab_frames[key].pack(fill="both", expand=True, padx=8, pady=8)

        # Highlight active nav button
        active = self._tab_btns[key]
        active["frame"].configure(fg_color=BG_CARD)
        active["icon"].configure(text_color=NEON_GREEN)
        active["text"].configure(text_color=NEON_GREEN)
        active["accent"].configure(fg_color=NEON_GREEN)

    # -- Tab builders ----------------------------------------------------------

    def _build_scan_tab(self, parent):
        # Action row
        action_row = ctk.CTkFrame(parent, fg_color="transparent")
        action_row.pack(fill="x", pady=(0, 8))

        NeonButton(action_row, ">> SCAN SCRIPTS",
                   command=self._run_script_scan,
                   color=NEON_GREEN, height=40, width=180).pack(side="left", padx=4)
        NeonButton(action_row, "XX  QUARANTINE ALL CRITICAL",
                   command=self._quarantine_critical,
                   color=NEON_RED, height=40, width=220).pack(side="left", padx=4)
        NeonButton(action_row, "~~ CLEAR CACHE",
                   command=self._clear_cache,
                   color=NEON_AMBER, height=40, width=150).pack(side="left", padx=4)

        # Progress
        self._scan_progress = ctk.CTkProgressBar(
            parent, progress_color=NEON_GREEN, fg_color=BG_CARD,
            height=6, corner_radius=2)
        self._scan_progress.pack(fill="x", pady=(0, 8))
        self._scan_progress.set(0)

        # Results pane
        results_frame = neon_frame(parent, color="#003d26")
        results_frame.pack(fill="both", expand=True)

        # Results header
        hdr = ctk.CTkFrame(results_frame, fg_color=BG_HEADER)
        hdr.pack(fill="x")

        for col, width, color in [
            ("STATUS",   8,  NEON_AMBER),
            ("FILENAME", 45, NEON_CYAN),
            ("ISSUE",    47, TEXT_DIM),
        ]:
            ctk.CTkLabel(hdr, text=col, font=("Courier New", 9, "bold"),
                         text_color=color, width=width*8, anchor="w").pack(
                             side="left", padx=6, pady=4)

        # Results list (scrollable)
        scroll_frame = ctk.CTkScrollableFrame(results_frame, fg_color=BG_DEEP,
                                              scrollbar_button_color="#002d1e")
        scroll_frame.pack(fill="both", expand=True)
        self._script_results_frame = scroll_frame

        # Placeholder
        ctk.CTkLabel(scroll_frame,
                     text="Run a scan to see results...",
                     font=FONT_LABEL, text_color=TEXT_DIM).pack(pady=40)

    def _build_cc_tab(self, parent):
        action_row = ctk.CTkFrame(parent, fg_color="transparent")
        action_row.pack(fill="x", pady=(0, 8))

        NeonButton(action_row, "[##] SCAN CC PACKAGES",
                   command=self._run_cc_scan,
                   color=NEON_CYAN, height=40, width=200).pack(side="left", padx=4)
        ctk.CTkLabel(action_row,
                     text="âš  Full CC scan may take 2-5 minutes on large collections",
                     font=FONT_SMALL, text_color=NEON_AMBER).pack(
                         side="left", padx=12)

        # Progress
        self._cc_progress = ctk.CTkProgressBar(
            parent, progress_color=NEON_CYAN, fg_color=BG_CARD,
            height=6, corner_radius=2)
        self._cc_progress.pack(fill="x", pady=(0, 8))
        self._cc_progress.set(0)

        # CC stats cards
        cc_stats_row = ctk.CTkFrame(parent, fg_color="transparent")
        cc_stats_row.pack(fill="x", pady=(0, 8))
        for i in range(5):
            cc_stats_row.columnconfigure(i, weight=1)

        self._cc_corrupt = StatCard(cc_stats_row, "CORRUPT",    color=NEON_RED)
        self._cc_dupname = StatCard(cc_stats_row, "DUP NAMES",  color=NEON_AMBER)
        self._cc_duphash = StatCard(cc_stats_row, "DUP FILES",  color=NEON_AMBER)
        self._cc_tuning  = StatCard(cc_stats_row, "TUNING âš ",  color=NEON_PINK)
        self._cc_ww      = StatCard(cc_stats_row, "WW PACKAGES",color=NEON_PURPLE)
        for i, c in enumerate([self._cc_corrupt, self._cc_dupname,
                               self._cc_duphash, self._cc_tuning, self._cc_ww]):
            c.grid(row=0, column=i, padx=4, sticky="nsew")

        # CC results
        results_frame = neon_frame(parent, color="#003d4d")
        results_frame.pack(fill="both", expand=True)
        scroll = ctk.CTkScrollableFrame(results_frame, fg_color=BG_DEEP,
                                        scrollbar_button_color="#002d3d")
        scroll.pack(fill="both", expand=True)
        self._cc_results_frame = scroll
        ctk.CTkLabel(scroll, text="Run CC scan to see results...",
                     font=FONT_LABEL, text_color=TEXT_DIM).pack(pady=40)

    def _build_logs_tab(self, parent):
        action_row = ctk.CTkFrame(parent, fg_color="transparent")
        action_row.pack(fill="x", pady=(0, 8))

        NeonButton(action_row, "[!!] PARSE LAST EXCEPTION LOG",
                   command=self._parse_logs,
                   color=NEON_AMBER, height=40, width=240).pack(side="left", padx=4)

        # Log output
        frame = neon_frame(parent, color="#3d2900")
        frame.pack(fill="both", expand=True)

        self._log_text = ConsoleText(frame)
        sb = ctk.CTkScrollbar(frame, command=self._log_text.yview,
                               button_color="#3d2900")
        sb.pack(side="right", fill="y")
        self._log_text.configure(yscrollcommand=sb.set)
        self._log_text.pack(fill="both", expand=True, padx=4, pady=4)
        self._log_text.append("Click 'PARSE LAST EXCEPTION LOG' to analyze your game errors.", "dim")

    def _build_fix_tab(self, parent):
        # Big action buttons
        ctk.CTkLabel(parent, text=">> REPAIR CONSOLE >>",
                     font=FONT_HEAD, text_color=NEON_GREEN).pack(pady=(4, 12))

        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.pack(fill="x", pady=4)
        grid.columnconfigure((0, 1), weight=1)

        actions = [
            ("[!!] QUARANTINE ALL CRITICAL SCRIPTS", NEON_RED,    self._quarantine_critical),
            ("~~  CLEAR ALL CACHES",               NEON_AMBER,  self._clear_cache),
            ("[OK] RESTORE ALL QUARANTINED",         NEON_GREEN,  self._restore_all),
            ("ðŸ“ OPEN MODS FOLDER",                NEON_CYAN,   self._open_mods_folder),
            ("XX  REMOVE DUPLICATE PACKAGES",      NEON_PINK,   self._remove_duplicates),
            ("[!!] SHOW QUARANTINE MANIFEST",        TEXT_DIM,    self._show_manifest),
        ]

        for i, (label, color, cmd) in enumerate(actions):
            r, c = divmod(i, 2)
            NeonButton(grid, label, cmd, color=color, height=52).grid(
                row=r, column=c, padx=8, pady=6, sticky="ew")

        # Fix console output
        frame = neon_frame(parent, color="#003d26")
        frame.pack(fill="both", expand=True, pady=(12, 0))
        self._fix_text = ConsoleText(frame)
        sb = ctk.CTkScrollbar(frame, command=self._fix_text.yview,
                               button_color="#002d1e")
        sb.pack(side="right", fill="y")
        self._fix_text.configure(yscrollcommand=sb.set)
        self._fix_text.pack(fill="both", expand=True, padx=4, pady=4)
        self._fix_text.configure(state="normal")
        self._fix_text.insert(tk.END, "Ready for commands...\n", "dim")
        self._fix_text.configure(state="disabled")

    def _build_console_tab(self, parent):
        frame = neon_frame(parent, color="#002d1e")
        frame.pack(fill="both", expand=True)

        toolbar = ctk.CTkFrame(frame, fg_color=BG_HEADER)
        toolbar.pack(fill="x")
        ctk.CTkLabel(toolbar, text="â–¶ LIVE OUTPUT CONSOLE",
                     font=("Courier New", 10, "bold"),
                     text_color=NEON_GREEN).pack(side="left", padx=8, pady=4)
        NeonButton(toolbar, "CLEAR", self._clear_console,
                   color=TEXT_DIM, width=70, height=28).pack(side="right", padx=8, pady=4)

        self._console = ConsoleText(frame)
        sb = ctk.CTkScrollbar(frame, command=self._console.yview,
                               button_color="#002d1e")
        sb.pack(side="right", fill="y")
        self._console.configure(yscrollcommand=sb.set)
        self._console.pack(fill="both", expand=True, padx=4, pady=4)


    def _build_launcher_tab(self, parent):
        """Game launcher with real-time process and error monitoring."""
        self._game_exe = None
        self._game_pid = None
        self._launcher_running = False
        self._log_error_count  = 0
        self._launch_time      = None

        # --- Top: find game exe ---
        exe_row = ctk.CTkFrame(parent, fg_color="transparent")
        exe_row.pack(fill="x", pady=(0, 8))
        exe_row.columnconfigure(1, weight=1)
        ctk.CTkLabel(exe_row, text="GAME EXE:", font=FONT_LABEL,
                     text_color=NEON_CYAN).grid(row=0, column=0, padx=(0, 8), sticky="w")
        self._exe_var = tk.StringVar(value="Click FIND to locate TS4_x64.exe")
        ctk.CTkEntry(exe_row, textvariable=self._exe_var, font=FONT_MONO_S,
                     fg_color=BG_CARD, border_color=NEON_CYAN, border_width=1,
                     text_color=NEON_GREEN).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        NeonButton(exe_row, "FIND", self._find_game_exe,
                   color=NEON_CYAN, width=70).grid(row=0, column=2, padx=(0, 8))

        # --- Launch / Kill buttons ---
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 8))
        self._launch_btn = NeonButton(btn_row, ">> LAUNCH SIMS 4",
                                      command=self._launch_game,
                                      color=NEON_GREEN, height=52, width=200)
        self._launch_btn.pack(side="left", padx=4)
        self._kill_btn = NeonButton(btn_row, "XX KILL GAME",
                                    command=self._kill_game,
                                    color=NEON_RED, height=52, width=150)
        self._kill_btn.pack(side="left", padx=4)

        # --- Status cards ---
        stat_row = ctk.CTkFrame(parent, fg_color="transparent")
        stat_row.pack(fill="x", pady=(0, 8))
        for i in range(4):
            stat_row.columnconfigure(i, weight=1)
        self._game_status_card  = StatCard(stat_row, "GAME STATUS",  value="OFFLINE", color=TEXT_DIM)
        self._game_uptime_card  = StatCard(stat_row, "UPTIME",       value="--",       color=NEON_CYAN)
        self._game_errors_card  = StatCard(stat_row, "LOG ERRORS",   value="--",       color=NEON_AMBER)
        self._game_crash_card   = StatCard(stat_row, "CRASH DETECT", value="--",       color=NEON_RED)
        for i, c in enumerate([self._game_status_card, self._game_uptime_card,
                                self._game_errors_card, self._game_crash_card]):
            c.grid(row=0, column=i, padx=4, sticky="nsew")

        # --- Live log output ---
        frame = neon_frame(parent, color="#003d26")
        frame.pack(fill="both", expand=True)
        toolbar = ctk.CTkFrame(frame, fg_color=BG_HEADER)
        toolbar.pack(fill="x")
        ctk.CTkLabel(toolbar, text=">> LIVE GAME LOG", font=("Courier New", 10, "bold"),
                     text_color=NEON_GREEN).pack(side="left", padx=8, pady=4)
        ctk.CTkLabel(toolbar, text="Monitors lastException.txt in real-time",
                     font=FONT_SMALL, text_color=TEXT_DIM).pack(side="left", padx=4, pady=4)
        self._launcher_log = ConsoleText(frame)
        sb = ctk.CTkScrollbar(frame, command=self._launcher_log.yview, button_color="#002d1e")
        sb.pack(side="right", fill="y")
        self._launcher_log.configure(yscrollcommand=sb.set)
        self._launcher_log.pack(fill="both", expand=True, padx=4, pady=4)
        self._launcher_log.append("Launcher ready. Find and launch The Sims 4.", "dim")
        self._launcher_log.append("Errors from lastException.txt will appear here in real-time.", "dim")

        # Auto-find game on open
        self.after(200, self._find_game_exe_auto)

    def _find_game_exe_auto(self):
        """Auto-detect Sims 4 exe from common locations."""
        candidates = [
            Path(r'C:/Program Files/EA Games/The Sims 4/Game/Bin/TS4_x64.exe'),
            Path(r'C:/Program Files (x86)/EA Games/The Sims 4/Game/Bin/TS4_x64.exe'),
            Path(r'D:/EA Games/The Sims 4/Game/Bin/TS4_x64.exe'),
            Path(r'E:/EA Games/The Sims 4/Game/Bin/TS4_x64.exe'),
        ]
        # Also check registry
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Maxis\The Sims 4')
            d = winreg.QueryValueEx(key, 'Install Dir')[0]
            candidates.insert(0, Path(d) / 'Game' / 'Bin' / 'TS4_x64.exe')
        except Exception:
            pass
        for p in candidates:
            if p.exists():
                self._game_exe = p
                self._exe_var.set(str(p))
                self._launcher_log.append(f"Game found: {p}", "ok")
                return
        self._launcher_log.append("Game exe not auto-found. Click FIND to browse.", "warning")

    def _find_game_exe(self):
        path = filedialog.askopenfilename(
            title="Select TS4_x64.exe",
            filetypes=[("Sims 4 Executable", "TS4_x64.exe"), ("All", "*.*")],
            initialdir="C:/Program Files",
        )
        if path:
            self._game_exe = Path(path)
            self._exe_var.set(path)
            self._launcher_log.append(f"Game set: {path}", "ok")

    def _launch_game(self):
        if not self._game_exe or not self._game_exe.exists():
            self._find_game_exe()
            if not self._game_exe:
                return
        self._launcher_log.clear()
        self._launcher_log.append(">> Launching The Sims 4...", "header")
        self._launcher_log.append(f"   {self._game_exe}", "dim")
        try:
            proc = subprocess.Popen([str(self._game_exe)],
                                    cwd=str(self._game_exe.parent))
            self._game_pid    = proc.pid
            self._launch_time = time.time()
            self._launcher_running = True
            self._log_error_count  = 0
            self._last_log_mtime   = 0
            self._last_error_count = 0
            self._game_status_card.set("RUNNING")
            self._game_crash_card.set("NONE")
            self._launcher_log.append(f"   PID: {proc.pid}", "dim")
            self._launcher_log.append("   Monitoring started - errors will appear below", "info")
            # Start monitor thread
            threading.Thread(target=self._monitor_game, args=(proc,), daemon=True).start()
            self._tick_launcher()
        except Exception as e:
            self._launcher_log.append(f"Launch failed: {e}", "critical")

    def _kill_game(self):
        if self._game_pid:
            try:
                subprocess.run(['taskkill', '/PID', str(self._game_pid), '/F'],
                               capture_output=True)
                self._launcher_log.append(f"XX Game killed (PID {self._game_pid})", "warning")
                self._game_pid = None
                self._launcher_running = False
                self._game_status_card.set("KILLED")
            except Exception as e:
                self._launcher_log.append(f"Kill failed: {e}", "critical")

    def _monitor_game(self, proc):
        """Background thread: watch process and log file."""
        log_path = (self.s4_folder or Path.home()) / 'Documents' / 'Electronic Arts' / 'The Sims 4' / 'lastException.txt'
        if self.s4_folder:
            log_path = self.s4_folder / 'lastException.txt'

        last_mtime  = 0
        last_errors = 0
        no_progress = 0

        while self._launcher_running:
            # Check process still alive
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {self._game_pid}', '/FO', 'CSV'],
                capture_output=True, text=True
            )
            if str(self._game_pid) not in result.stdout:
                self._q.put({'action': 'launcher_event', 'event': 'crashed'})
                break

            # Check log for new errors
            if log_path.exists():
                mtime = log_path.stat().st_mtime
                if mtime != last_mtime:
                    last_mtime = mtime
                    no_progress = 0
                    try:
                        content = log_path.read_text(encoding='utf-8', errors='replace')
                        errors = content.count('<report>')
                        if errors != last_errors:
                            new = errors - last_errors
                            last_errors = errors
                            self._q.put({'action': 'launcher_event', 'event': 'errors',
                                         'count': errors, 'new': new})
                    except Exception:
                        pass
                else:
                    no_progress += 1

            # Hang detection: if loading screen active > 8 minutes with no log updates
            elapsed = time.time() - self._launch_time
            if elapsed > 480 and no_progress > 60:
                self._q.put({'action': 'launcher_event', 'event': 'hang',
                             'elapsed': int(elapsed)})
                no_progress = 0  # reset, keep watching

            time.sleep(5)

        self._launcher_running = False

    def _tick_launcher(self):
        """Update uptime display every second while game is running."""
        if self._launcher_running and self._launch_time:
            elapsed = int(time.time() - self._launch_time)
            m, s = divmod(elapsed, 60)
            self._game_uptime_card.set(f"{m:02d}:{s:02d}")
            self.after(1000, self._tick_launcher)
        elif not self._launcher_running:
            self._game_uptime_card.set("--")

    def _build_about_tab(self, parent):
        parent.columnconfigure(0, weight=1)

        ctk.CTkLabel(parent,
                     text="""
[>>]  SIMS4 MOD GUARDIAN  [>>]

The cyberpunk hacker console for Sims 4 players.

Built to survive patch 1.121 and every patch that follows.
""",
                     font=("Courier New", 11), text_color=NEON_GREEN,
                     justify="center").pack(pady=(20, 4))

        ctk.CTkLabel(parent,
                     text="*  Crafted by  *\n\nHucifer  &  Hypatia",
                     font=("Courier New", 16, "bold"),
                     text_color=NEON_PINK,
                     justify="center").pack(pady=8)

        ctk.CTkLabel(parent,
                     text="Community Edition -- Free Forever",
                     font=("Courier New", 10),
                     text_color=NEON_AMBER).pack()

        ctk.CTkLabel(parent,
                     text="""
--------------------------------------------------

WHAT THIS DOES

  [!!]  Scans .ts4script files for broken injection patterns
  [!!]  Detects APIs removed by EA in patch 1.121
  [~~]  Finds WickedWhims dependencies without WW installed
  [~~]  Validates every CC package DBPF header
  [~~]  Finds duplicate packages by name and content hash
  ðŸ”µ  Parses lastException.txt into plain English
  [OK]  Safe quarantine with full restore support
  [OK]  One-click cache clearing

--------------------------------------------------

WHAT IT CANNOT DO

  âœ—  Fix compiled .pyc mods (no source code available)
  âœ—  Restore saves corrupted by old mods
  âœ—  Auto-update every mod to its latest version
  âœ—  Replace mods that require Patreon login

--------------------------------------------------

github.com/HuciferX/Sims4ModGuard
""",
                     font=("Courier New", 9),
                     text_color=TEXT_DIM,
                     justify="left").pack(pady=8)

    def _build_statusbar(self):
        sb = ctk.CTkFrame(self, fg_color=BG_HEADER,
                          border_color="#002016", border_width=1,
                          corner_radius=0, height=28)
        sb.pack(fill="x", side="bottom", padx=0, pady=0)
        sb.pack_propagate(False)

        self._status_var = tk.StringVar(value="* READY -- Select a Sims 4 folder to begin")
        ctk.CTkLabel(sb, textvariable=self._status_var,
                     font=FONT_SMALL, text_color=NEON_GREEN).pack(
                         side="left", padx=10, pady=4)

        self._time_var = tk.StringVar()
        ctk.CTkLabel(sb, textvariable=self._time_var,
                     font=FONT_SMALL, text_color=TEXT_DIM).pack(
                         side="right", padx=10, pady=4)
        self._tick_time()

    def _tick_time(self):
        self._time_var.set(datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self._tick_time)

    # -- Queue poller ----------------------------------------------------------

    def _poll_queue(self):
        try:
            while True:
                msg = self._q.get_nowait()
                action = msg.get("action", "")
                if action == "log":
                    self._console.append(msg["text"], msg.get("tag", ""))
                elif action == "status":
                    self._status_var.set(msg["text"])
                elif action == "progress":
                    bar = msg.get("bar", "scan")
                    val = msg.get("val", 0)
                    if bar == "scan":
                        self._scan_progress.set(val)
                    else:
                        self._cc_progress.set(val)
                elif action == "done_scan":
                    self._finish_scan(msg["results"])
                elif action == "launcher_event":
                    ev = msg.get("event", "")
                    if ev == "crashed":
                        self._game_status_card.set("CRASHED")
                        self._game_crash_card.set("YES")
                        self._launcher_running = False
                        if hasattr(self, '_launcher_log'):
                            self._launcher_log.append("[!!] GAME CRASHED - check log", "critical")
                    elif ev == "errors":
                        c = msg.get("count", 0)
                        n = msg.get("new", 0)
                        self._game_errors_card.set(str(c))
                        if hasattr(self, '_launcher_log') and n > 0:
                            self._launcher_log.append(f"  +{n} new errors (total {c})", "warning")
                    elif ev == "hang":
                        sec = msg.get("elapsed", 0)
                        self._game_crash_card.set("HANG?")
                        if hasattr(self, '_launcher_log'):
                            self._launcher_log.append(f"[!!] POSSIBLE HANG: {sec}s on loading screen", "critical")
                elif action == "done_cc":
                    self._finish_cc(msg["data"])
                elif action == "boot_phase":
                    self._on_boot_phase(msg)
                elif action == "boot_done":
                    self._on_boot_done(msg["report"])
                elif action == "save_log":
                    self._save_console.append(msg["text"], msg.get("tag", "info"))
                elif action == "save_done":
                    self._on_save_analyzed(msg["report"])
                elif action == "save_cleaned":
                    self._on_save_cleaned(msg)
        except queue.Empty:
            pass
        self.after(50, self._poll_queue)

    def _log(self, text: str, tag: str = ""):
        self._q.put({"action": "log", "text": text, "tag": tag})

    def _status(self, text: str):
        self._q.put({"action": "status", "text": text})

    # -- Auto-detect -----------------------------------------------------------

    def _auto_detect(self):
        folder = find_s4_folder()
        if folder:
            self._set_folder(folder)
        else:
            self._status("* Could not auto-detect Sims 4 folder -- click BROWSE")

    def _browse_folder(self):
        path = filedialog.askdirectory(
            title="Select your Sims 4 user data folder",
            initialdir=str(Path.home() / "Documents" / "Electronic Arts"),
        )
        if path:
            self._set_folder(Path(path))

    def _set_folder(self, folder: Path):
        self.s4_folder   = folder
        self.mods_folder = folder / "Mods"
        self.qm = QuarantineManager(folder)
        self._folder_var.set(str(folder))

        version = read_game_version(folder)
        cache   = get_cache_state(folder)

        scripts  = sum(1 for _ in self.mods_folder.rglob("*.ts4script")
                       if "MODS_DISABLED" not in str(_)) if self.mods_folder.exists() else 0
        packages = sum(1 for _ in self.mods_folder.rglob("*.package")
                       if "MODS_DISABLED" not in str(_)) if self.mods_folder.exists() else 0
        disabled = sum(1 for _ in (folder / "MODS_DISABLED").rglob("*")
                       if _.is_file()) if (folder / "MODS_DISABLED").exists() else 0

        self._stat_version.set(version.split(".")[0] + "." +
                               version.split(".")[1] if "." in version else version)
        self._stat_scripts.set(str(scripts))
        self._stat_packages.set(f"{packages:,}")
        self._stat_disabled.set(str(disabled))
        self._stat_cache.set(str(cache["thumbnail_cache_mb"]))

        self._status(f"* Sims 4 folder loaded -- {scripts} scripts, {packages:,} packages")
        self._console.append(f"[LOADED] {folder}", "info")
        self._console.append(f"  Game: {version}  Scripts: {scripts}  Packages: {packages:,}", "dim")

    # -- Boot sequence ---------------------------------------------------------

    def _boot_sequence(self):
        msgs = [
            ("* SIMS4 MOD GUARDIAN ONLINE *", "header"),
            ("by Hucifer & Hypatia -- Community Edition", "pink"),
            ("-" * 55, "dim"),
            ("Initializing mod scanner engine...", "info"),
            ("Loading patch 1.121 detection rules...", "info"),
            ("DBPF parser: READY", "ok"),
            ("Script scanner: READY", "ok"),
            ("CC cleaner: READY", "ok"),
            ("Log parser: READY", "ok"),
            ("Quarantine manager: READY", "ok"),
            ("-" * 55, "dim"),
            ("All systems ONLINE. Select a scan to begin.", "bold"),
        ]
        def send(i=0):
            if i < len(msgs):
                self._console.append(*msgs[i])
                self.after(random.randint(40, 100), lambda: send(i + 1))
        send()

    # -- Auto-updater ----------------------------------------------------------

    def _check_for_updates(self):
        """Called 2 s after launch.  Delegates to the updater module which runs
        the GitHub API check on a background thread and opens UpdateDialog on
        the main thread only when a newer release is available.
        """
        try:
            _updater.check_and_prompt(self)
        except Exception:
            pass  # never block the app if the updater itself errors

    # -- Scan ------------------------------------------------------------------

    def _run_script_scan(self):
        if not self.mods_folder:
            messagebox.showwarning("No Folder", "Select a Sims 4 folder first.")
            return
        self._log("-" * 55, "dim")
        self._log(">> Starting script scan...", "header")
        self._scan_progress.set(0)
        self._switch_tab("console")

        def worker():
            self._status("* SCANNING SCRIPTS...")
            results = scan_all_scripts(self.mods_folder)
            self._q.put({"action": "done_scan", "results": results})

        threading.Thread(target=worker, daemon=True).start()

        # Animate progress while scanning
        self._fake_progress("scan")

    def _fake_progress(self, bar: str, val: float = 0.0):
        if val < 0.9:
            val += random.uniform(0.02, 0.08)
            self._q.put({"action": "progress", "bar": bar, "val": min(val, 0.9)})
            self.after(200, lambda: self._fake_progress(bar, val))

    def _finish_scan(self, results):
        self._scan_results = results
        self._scan_progress.set(1.0)

        critical = [r for r in results if r.severity == SEVERITY_CRITICAL]
        clean    = [r for r in results if r.is_clean]

        self._stat_issues.set(str(len(critical)))

        self._log(f"Script scan complete: {len(results)} scanned", "bold")
        self._log(f"  Clean: {len(clean)}  Critical: {len(critical)}", "info")

        # Populate scan results tab
        frame = self._script_results_frame
        for w in frame.winfo_children():
            w.destroy()

        if not results:
            ctk.CTkLabel(frame, text="No scripts found.", font=FONT_LABEL,
                         text_color=TEXT_DIM).pack(pady=40)
            return

        for r in sorted(results, key=lambda x: (0 if x.severity == SEVERITY_CRITICAL else 1, x.name)):
            color = (NEON_RED if r.severity == SEVERITY_CRITICAL
                     else NEON_AMBER if r.severity == SEVERITY_WARNING
                     else NEON_GREEN if r.is_clean else TEXT_DIM)
            status = ("âœ— CRITICAL" if r.severity == SEVERITY_CRITICAL
                      else "âš  WARNING" if r.severity == SEVERITY_WARNING
                      else "âœ“ OK")
            issue_text = r.issues[0].message if r.issues else "No issues"

            row = ctk.CTkFrame(frame, fg_color=BG_CARD if r.issues else "transparent",
                               corner_radius=4)
            row.pack(fill="x", padx=4, pady=1)

            ctk.CTkLabel(row, text=status, font=FONT_SMALL,
                         text_color=color, width=80).pack(side="left", padx=6, pady=4)
            ctk.CTkLabel(row, text=r.name[:42], font=FONT_MONO_S,
                         text_color=NEON_CYAN, anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(row, text=issue_text[:50], font=FONT_SMALL,
                         text_color=TEXT_DIM if not r.issues else NEON_AMBER,
                         anchor="w").pack(side="left", padx=4)

            if r.issues:
                self._log(f"  [{status.strip()}] {r.name}", "critical" if r.severity == SEVERITY_CRITICAL else "warning")

        self._switch_tab("scan")
        self._status(f"* Scan done -- {len(critical)} critical, {len(clean)} clean")

    # -- CC Scan ---------------------------------------------------------------

    def _run_cc_scan(self):
        if not self.mods_folder:
            messagebox.showwarning("No Folder", "Select a Sims 4 folder first.")
            return
        self._log("-" * 55, "dim")
        self._log("[##] Starting CC package scan...", "header")
        self._log("  This may take several minutes on large collections.", "dim")
        self._cc_progress.set(0)
        self._switch_tab("console")

        def worker():
            self._status(">> SCANNING CC PACKAGES...")
            def _progress_cb(current, total):
                val = current / total if total > 0 else 0
                self._q.put({"action": "progress", "bar": "cc", "val": val})
                self._q.put({"action": "status",
                             "text": f">> CC SCAN: {current:,} / {total:,} packages"})
            data = scan_all_packages(self.mods_folder, progress_callback=_progress_cb)
            self._q.put({"action": "done_cc", "data": data})

        threading.Thread(target=worker, daemon=True).start()

    def _finish_cc(self, data):
        self._cc_data = data
        self._cc_progress.set(1.0)
        s = data["summary"]

        self._cc_corrupt.set(str(s["corrupt"]))
        self._cc_dupname.set(str(s["duplicate_names"]))
        self._cc_duphash.set(str(s["duplicate_hashes"]))
        self._cc_tuning.set(str(s["tuning_conflicts"]))
        self._cc_ww.set(str(s["ww_packages"]))

        self._log(f"CC scan complete: {s['total']:,} packages", "bold")
        self._log(f"  Corrupt: {s['corrupt']}  Dups: {s['duplicate_names']}  Tuning âš : {s['tuning_conflicts']}", "info")

        frame = self._cc_results_frame
        for w in frame.winfo_children():
            w.destroy()

        def add_section(title, items, color, detail_fn):
            if not items:
                return
            ctk.CTkLabel(frame, text=f"-- {title} ({len(items)}) --",
                         font=("Courier New", 10, "bold"),
                         text_color=color).pack(anchor="w", padx=8, pady=(8, 2))
            for r in items[:20]:
                detail = detail_fn(r)
                row_f = ctk.CTkFrame(frame, fg_color=BG_CARD, corner_radius=3)
                row_f.pack(fill="x", padx=8, pady=1)
                ctk.CTkLabel(row_f, text=r.name[:52], font=FONT_MONO_S,
                             text_color=color, anchor="w").pack(side="left", padx=6, pady=3)
                ctk.CTkLabel(row_f, text=detail, font=FONT_SMALL,
                             text_color=TEXT_DIM, anchor="w").pack(side="left", padx=4)
            if len(items) > 20:
                ctk.CTkLabel(frame, text=f"  ... and {len(items)-20} more",
                             font=FONT_SMALL, text_color=TEXT_DIM).pack(anchor="w", padx=8)

        add_section("CORRUPT PACKAGES",      data["corrupt"],
                    NEON_RED,    lambda r: "Invalid DBPF")
        add_section("TUNING CONFLICTS",      data["tuning_conflicts"],
                    NEON_PINK,   lambda r: f"{r.file_size//1024}KB")
        add_section("WW PACKAGES",           data["ww_packages"],
                    NEON_PURPLE, lambda r: "WickedWhims content")

        if not any([data["corrupt"], data["tuning_conflicts"], data["ww_packages"]]):
            ctk.CTkLabel(frame, text="âœ“ No major issues found in CC packages!",
                         font=FONT_HEAD, text_color=NEON_GREEN).pack(pady=30)

        self._switch_tab("cc")
        self._status(f"* CC scan done -- {s['corrupt']} corrupt, {s['duplicate_names']} dup names")

    # -- Log parsing -----------------------------------------------------------

    def _parse_logs(self):
        if not self.s4_folder:
            messagebox.showwarning("No Folder", "Select a Sims 4 folder first.")
            return
        self._log_text.clear()
        log_path = self.s4_folder / "lastException.txt"
        self._log_text.append("* Parsing lastException.txt...", "header")

        def worker():
            summary = parse_log(log_path)
            self.after(0, lambda: self._show_log_summary(summary))

        threading.Thread(target=worker, daemon=True).start()

    def _show_log_summary(self, summary):
        t = self._log_text
        t.append(f"Game version: {summary.game_version}", "bold")
        t.append(f"Sessions: {summary.sessions}  Total errors: {summary.total_errors}", "info")

        if not summary.tuning_finished:
            t.append("âš   TUNING DID NOT FINISH LOADING -- this caused the crash!", "critical")

        if summary.grouped:
            t.append("", "")
            t.append("ERROR CATEGORIES:", "header")
            for cat, errors in summary.grouped.items():
                count = sum(e.count for e in errors)
                t.append(f"  {cat}: {count} occurrences", "info")

        if summary.root_causes:
            t.append("", "")
            t.append("TOP ROOT CAUSES:", "header")
            for err in summary.root_causes[:10]:
                ct = f" (Ã—{err.count})" if err.count > 1 else ""
                t.append(f"  â€¢ {err.description[:90]}{ct}", "warning")
                if err.explanation:
                    t.append(f"    â†’ {err.explanation}", "dim")

        self._status(f"* Log parsed -- {summary.total_errors} errors, "
                     f"{'CRASH DETECTED' if not summary.tuning_finished else 'no crash'}")

    # -- Fix actions -----------------------------------------------------------

    def _quarantine_critical(self):
        if not self._scan_results:
            messagebox.showinfo("Scan First", "Run a script scan first.")
            return
        if not self.qm:
            return

        critical = [r for r in self._scan_results if r.severity == SEVERITY_CRITICAL]
        if not critical:
            self._fix_log("âœ“ No critical scripts to quarantine.", "ok")
            return

        if not messagebox.askyesno("Confirm",
                f"Quarantine {len(critical)} critical script(s)?\nThey can be restored later."):
            return

        moved = 0
        for r in critical:
            reason = r.issues[0].message if r.issues else "Critical issue detected"
            dest = self.qm.quarantine(r.path, reason, auto=True)
            if dest:
                moved += 1
                self._fix_log(f"  âœ— Quarantined: {r.name}", "critical")

        self._fix_log(f"* Done. {moved} scripts quarantined.", "bold")
        self._clear_cache_silent()
        self._status(f"* {moved} scripts quarantined -- clearing cache")

    def _clear_cache(self):
        if not self.s4_folder:
            return
        self._fix_log("~~ Clearing Sims 4 caches...", "info")
        result = clear_caches(self.s4_folder, verbose=False)
        mb = result["bytes_freed"] // (1024 * 1024)
        self._fix_log(f"  Cleared {len(result['files'])} cache files ({mb} MB freed)", "ok")
        self._stat_cache.set("0")
        self._status("* Caches cleared")
        Toast(self, f"✓ Caches cleared  ({mb} MB freed)", sev="ok")

    def _clear_cache_silent(self):
        if self.s4_folder:
            clear_caches(self.s4_folder, verbose=False)
            self._stat_cache.set("0")

    def _restore_all(self):
        if not self.qm:
            return
        active = self.qm.get_quarantined()
        if not active:
            messagebox.showinfo("Nothing", "No quarantined files to restore.")
            return
        if messagebox.askyesno("Restore", f"Restore all {len(active)} quarantined files?"):
            restored = 0
            for e in active:
                if self.qm.restore(e["destination"]):
                    self._fix_log(f"  âœ“ Restored: {e['name']}", "ok")
                    restored += 1
            self._fix_log(f"* {restored} files restored.", "bold")
            self._status(f"* {restored} files restored from quarantine")

    def _open_mods_folder(self):
        if self.mods_folder and self.mods_folder.exists():
            import subprocess
            subprocess.Popen(["explorer", str(self.mods_folder)])

    def _remove_duplicates(self):
        if not self._cc_data:
            messagebox.showinfo("CC Scan First", "Run a CC scan first to find duplicates.")
            return
        dup_names = self._cc_data["duplicate_names"]
        dup_hashes = self._cc_data["duplicate_hashes"]
        total_dups = sum(len(ps) - 1 for ps in dup_names.values()) + \
                     sum(len(ps) - 1 for ps in dup_hashes.values())
        if total_dups == 0:
            messagebox.showinfo("No Duplicates", "No duplicate packages found.")
            return
        if messagebox.askyesno("Remove Duplicates",
                f"Quarantine {total_dups} duplicate packages? (Keeps newest copy)"):
            moved = 0
            for name, paths in dup_names.items():
                for p in sorted(paths, key=lambda x: x.stat().st_mtime)[:-1]:
                    if self.qm.quarantine(p, f"Duplicate filename: {name}", auto=True):
                        moved += 1
            self._fix_log(f"* {moved} duplicate packages quarantined.", "bold")

    def _show_manifest(self):
        if not self.qm:
            return
        active = self.qm.get_quarantined()
        win = ctk.CTkToplevel(self)
        win.title("Quarantine Manifest")
        win.geometry("700x500")
        win.configure(fg_color=BG_DEEP)

        ctk.CTkLabel(win, text=f"QUARANTINED FILES ({len(active)})",
                     font=FONT_HEAD, text_color=NEON_AMBER).pack(pady=8)
        frame = neon_frame(win, color="#3d2900")
        frame.pack(fill="both", expand=True, padx=8, pady=4)
        t = ConsoleText(frame)
        sb = ctk.CTkScrollbar(frame, command=t.yview)
        sb.pack(side="right", fill="y")
        t.configure(yscrollcommand=sb.set)
        t.pack(fill="both", expand=True, padx=4, pady=4)
        t.configure(state="normal")
        for e in active:
            t.insert(tk.END, f"  {e['name']}\n", "warning")
            t.insert(tk.END, f"    {e['reason'][:90]}\n", "dim")
            t.insert(tk.END, f"    {e['timestamp'][:19]}\n\n", "dim")
        t.configure(state="disabled")

    def _fix_log(self, text: str, tag: str = ""):
        self._fix_text.configure(state="normal")
        if tag:
            self._fix_text.insert(tk.END, text + "\n", tag)
        else:
            self._fix_text.insert(tk.END, text + "\n")
        self._fix_text.see(tk.END)
        self._fix_text.configure(state="disabled")
        self._console.append(text, tag)

    def _clear_console(self):
        self._console.clear()

    # ═══════════════════════════════════════════════════════════════════════════
    # ── WIZARD TAB ─────────────────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════════════════

    # Step states
    _WIZ_PENDING  = "PENDING"
    _WIZ_RUNNING  = "RUNNING"
    _WIZ_DONE_OK  = "COMPLETE"
    _WIZ_DONE_WARN= "ISSUES FOUND"
    _WIZ_DONE_FAIL= "CRITICAL"
    _WIZ_SKIP     = "SKIPPED"

    # Status badge colors
    _WIZ_COLORS = {
        "PENDING":      TEXT_DIM,
        "RUNNING":      NEON_AMBER,
        "COMPLETE":     NEON_GREEN,
        "ISSUES FOUND": NEON_AMBER,
        "CRITICAL":     NEON_RED,
        "SKIPPED":      TEXT_DIM,
    }

    def _build_wizard_tab(self, parent):
        """Guided accordion stepper wizard."""
        # State tracking
        self._wiz_states      = {}
        self._wiz_widgets     = {}
        self._wiz_indicators  = {}   # key -> StepIndicator
        self._wiz_connectors  = {}   # key -> ConnectorLine
        self._wiz_game_root   = DEFAULT_GAME_ROOT
        self._wiz_boot_report = None
        self._wiz_index       = None
        self._wiz_active_step = None

        # ── Header bar ─────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(parent, fg_color="#020218", corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr,
                     text="  ❖  SETUP WIZARD",
                     font=("Courier New", 14, "bold"),
                     text_color=NEON_GREEN).pack(side="left", padx=14, pady=10)
        ctk.CTkLabel(hdr,
                     text="Complete each step in order to prepare your game for a clean boot  ",
                     font=("Courier New", 9),
                     text_color=TEXT_DIM).pack(side="right")

        # ── Overall progress bar ─────────────────────────────────────────────────────
        prog_row = ctk.CTkFrame(parent, fg_color="transparent")
        prog_row.pack(fill="x", padx=16, pady=(6, 0))
        self._wiz_overall_bar = ctk.CTkProgressBar(
            prog_row, progress_color=NEON_GREEN, fg_color="#0a0a1a",
            height=4, corner_radius=2)
        self._wiz_overall_bar.pack(fill="x")
        self._wiz_overall_bar.set(0)
        self._wiz_prog_lbl = ctk.CTkLabel(
            prog_row, text="",
            font=FONT_SMALL, text_color=TEXT_DIM)
        self._wiz_prog_lbl.pack(anchor="e")

        # ── Scrollable stepper ─────────────────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(parent, fg_color=BG_DEEP,
                                         scrollbar_button_color="#002d1e")
        scroll.pack(fill="both", expand=True, pady=(8, 0))
        self._wiz_scroll = scroll

        steps = [
            {"key": "detect",   "num": "1", "color": NEON_CYAN,
             "icon": "\U0001f4c1",
             "title": "Detect Sims 4 Folders",
             "subtitle": "Locate your Mods folder and game installation",
             "bullets": ["Finds your Sims 4 user data (Mods, saves, logs)",
                         "Finds your game installation (EA's actual game files)",
                         "Required before any other step can run"],
             "btn_label": "Auto-Detect Folders",
             "action": self._wiz_step_detect, "time": "Instant"},

            {"key": "index",    "num": "2", "color": NEON_PURPLE,
             "icon": "\U0001f4ca",
             "title": "Index Real Game Files",
             "subtitle": "Read 3,500+ Python modules and base-game resources from your install",
             "bullets": ["Extracts all game Python module names from simulation.zip",
                         "Builds a resource ID table from SimulationFullBuild0.package",
                         "Cached after first run — instant on future runs"],
             "btn_label": "Build Game Index",
             "action": self._wiz_step_index, "time": "~45 sec first run, instant after (cached)"},

            {"key": "simulate", "num": "3", "color": NEON_GREEN,
             "icon": "\U0001f52c",
             "title": "Simulate Full Boot",
             "subtitle": "Run all 7 phases of the game boot sequence without launching",
             "bullets": ["Checks every mod .py for broken APIs and bad injection patterns",
                         "Validates mod imports against the real 3,589-module game registry",
                         "Detects resource conflicts between mods and EA base game",
                         "Flags CC buried too deep in subfolders (silently ignored by game)",
                         "Scores crash probability and ranks issues by severity"],
             "btn_label": "Run Boot Simulation",
             "action": self._wiz_step_simulate, "time": "10–30 min for 13,000+ mods"},

            {"key": "fix",      "num": "4", "color": NEON_RED,
             "icon": "\U0001f6e1",
             "title": "Fix Critical Issues",
             "subtitle": "Safely quarantine broken mods — files are never deleted",
             "bullets": ["Moves CRITICAL mods to MODS_DISABLED folder",
                         "Also removes near-exact duplicate CC (same content twice)",
                         "Restore any file any time from the Fix & Repair tab"],
             "btn_label": "Quarantine All Critical",
             "action": self._wiz_step_fix, "time": "Instant"},

            {"key": "cache",    "num": "5", "color": NEON_AMBER,
             "icon": "\U0001f5d1",
             "title": "Clear Game Caches",
             "subtitle": "Delete stale cache files that cause loading-screen crashes",
             "bullets": ["Deletes localthumbcache.package",
                         "Clears cachestr/ slot files",
                         "Must do this every time you add, remove, or update any mod"],
             "btn_label": "Clear All Caches",
             "action": self._wiz_step_cache, "time": "Instant"},

            {"key": "save",     "num": "6", "color": NEON_PINK,
             "icon": "\U0001f4be",
             "title": "Check Save File",
             "subtitle": "Optional: scan for orphaned mod references that corrupt saves",
             "bullets": ["Your save remembers every mod resource it's ever touched",
                         "Removed mods leave 'orphaned' references that cause crashes",
                         "Generates a clean copy with orphans removed (original kept)"],
             "btn_label": "Show My Save Files",
             "action": self._wiz_step_save, "time": "2–5 min per save"},
        ]

        for i, step in enumerate(steps):
            self._wiz_build_accordion_step(scroll, step, is_last=(i == len(steps)-1))
            self._wiz_states[step["key"]] = self._WIZ_PENDING

        # ── Launch-ready banner ──────────────────────────────────────────────────────
        self._wiz_ready_frame = ctk.CTkFrame(
            scroll, fg_color="#001a0d",
            border_color=NEON_GREEN, border_width=2, corner_radius=8)
        ctk.CTkLabel(self._wiz_ready_frame,
                     text="Complete steps 1–5 above to unlock the launch panel",
                     font=("Courier New", 11), text_color=TEXT_DIM).pack(pady=14)
        self._wiz_ready_frame.pack(fill="x", padx=12, pady=(8, 12))

        self.after(800, lambda: self._wiz_set_active("detect"))

    def _wiz_build_accordion_step(self, parent, step: dict, is_last: bool = False):
        """
        Build one accordion step.
        Layout: [StepIndicator] [content area — expands when active, collapses when done]
        A ConnectorLine sits between steps.
        """
        key   = step["key"]
        color = step["color"]

        # ── Outer row: indicator + content ──
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=0)
        row.columnconfigure(1, weight=1)

        # ── Left column: indicator + connector ──
        left_col = ctk.CTkFrame(row, fg_color="transparent", width=52)
        left_col.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        left_col.grid_propagate(False)

        indicator = StepIndicator(left_col, step_num=step["num"],
                                   step_color=color, state="PENDING", size=52)
        indicator.pack()
        self._wiz_indicators[key] = indicator

        # ── Right column: content area ──
        content = ctk.CTkFrame(row, fg_color="transparent")
        content.grid(row=0, column=1, sticky="nsew", pady=4)

        # Header row: icon + title + status badge
        hdr_row = ctk.CTkFrame(content, fg_color="transparent")
        hdr_row.pack(fill="x")
        hdr_row.columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr_row, text=step["icon"],
                     font=("Segoe UI Emoji", 16),
                     text_color=TEXT_DIM).grid(row=0, column=0, padx=(0, 6))

        title_lbl = ctk.CTkLabel(hdr_row,
                                  text=step["title"],
                                  font=("Courier New", 12, "bold"),
                                  text_color=TEXT_DIM, anchor="w")
        title_lbl.grid(row=0, column=1, sticky="ew")

        status_badge = ctk.CTkLabel(hdr_row, text="PENDING",
                                     font=("Courier New", 8, "bold"),
                                     text_color=TEXT_DIM,
                                     fg_color="#0a0a1a",
                                     corner_radius=4, padx=8, pady=3)
        status_badge.grid(row=0, column=2, padx=(8, 0))

        # Subtitle (always visible)
        subtitle_lbl = ctk.CTkLabel(content,
                                     text=step["subtitle"],
                                     font=("Courier New", 9),
                                     text_color=TEXT_DIM, anchor="w")
        subtitle_lbl.pack(fill="x", pady=(2, 0))

        # ── Expanded detail frame (ACTIVE state) ──
        detail_frame = ctk.CTkFrame(content, fg_color="#080820",
                                     border_color=color, border_width=1,
                                     corner_radius=6)
        # Bullets
        for bullet in step.get("bullets", []):
            ctk.CTkLabel(detail_frame, text=f"  •  {bullet}",
                         font=("Courier New", 9), text_color="#8888aa",
                         justify="left", anchor="w").pack(
                             fill="x", padx=10, pady=1)
        # Time estimate
        ctk.CTkLabel(detail_frame,
                     text=f"  ⏱  Typical time: {step.get('time','')}",
                     font=("Courier New", 8),
                     text_color=TEXT_DIM).pack(anchor="w", padx=10, pady=(4, 2))
        # Action button
        btn_row_f = ctk.CTkFrame(detail_frame, fg_color="transparent")
        btn_row_f.pack(fill="x", padx=10, pady=(4, 10))
        btn = NeonButton(btn_row_f, f"  ▶  {step['btn_label']}  ",
                         command=step["action"],
                         color=color, height=38)
        btn.pack(side="left")
        arrow_lbl = ctk.CTkLabel(btn_row_f, text="",
                                  font=("Courier New", 9, "bold"),
                                  text_color=NEON_GREEN)
        arrow_lbl.pack(side="left", padx=10)

        # ── Result summary (shown after done) ──
        result_lbl = ctk.CTkLabel(content, text="",
                                   font=("Courier New", 9, "bold"),
                                   text_color=NEON_GREEN,
                                   justify="left", anchor="w",
                                   wraplength=700)

        # ── Divider line ──
        div = ctk.CTkFrame(parent, fg_color="#0a0a1a", height=1)
        div.pack(fill="x", padx=20, pady=0)

        # ── Connector line below (links to next step) ──
        if not is_last:
            connector_row = ctk.CTkFrame(parent, fg_color="transparent")
            connector_row.pack(fill="x", padx=8)
            conn = ConnectorLine(connector_row, done=False, height=20)
            conn.pack(side="left")
            self._wiz_connectors[key] = conn

        # Store all widget refs
        self._wiz_widgets[key] = {
            "row":          row,
            "left_col":     left_col,
            "indicator":    indicator,
            "content":      content,
            "title_lbl":    title_lbl,
            "subtitle_lbl": subtitle_lbl,
            "status_badge": status_badge,
            "detail_frame": detail_frame,
            "result_lbl":   result_lbl,
            "btn":          btn,
            "arrow_lbl":    arrow_lbl,
            "color":        color,
        }

    # Keep old method signature for compatibility but delegate to accordion
    def _wiz_build_step_card(self, parent, step: dict):
        """Build one wizard step card."""
        key   = step["key"]
        color = step["color"]

        # Outer card
        card = ctk.CTkFrame(parent, fg_color=BG_CARD,
                            border_color=TEXT_DIM, border_width=1,
                            corner_radius=8)
        card.pack(fill="x", padx=6, pady=5)
        card.columnconfigure(1, weight=1)

        # Left: step number circle
        num_frame = ctk.CTkFrame(card, fg_color=_dim_color(color, 0.15),
                                  width=48, height=48, corner_radius=24)
        num_frame.grid(row=0, column=0, rowspan=3, padx=(12, 8), pady=12, sticky="n")
        num_frame.pack_propagate(False)
        ctk.CTkLabel(num_frame, text=step["num"],
                     font=("Courier New", 20, "bold"),
                     text_color=color).pack(expand=True)

        # Title row
        title_row = ctk.CTkFrame(card, fg_color="transparent")
        title_row.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(10, 0))
        title_row.columnconfigure(0, weight=1)

        ctk.CTkLabel(title_row, text=step["title"],
                     font=("Courier New", 11, "bold"),
                     text_color=color, anchor="w").grid(row=0, column=0, sticky="w")

        status_lbl = ctk.CTkLabel(title_row, text="PENDING",
                                   font=("Courier New", 9, "bold"),
                                   text_color=TEXT_DIM,
                                   fg_color=BG_DEEP, corner_radius=4,
                                   padx=6, pady=2)
        status_lbl.grid(row=0, column=1, padx=(8, 0), sticky="e")

        # Time estimate
        ctk.CTkLabel(card, text=f"  Time: {step['time']}",
                     font=FONT_SMALL, text_color=TEXT_DIM,
                     anchor="w").grid(row=1, column=1, sticky="w", padx=(0, 12))

        # "What this does" text
        ctk.CTkLabel(card, text=step["what"],
                     font=("Courier New", 9), text_color=TEXT_MAIN,
                     justify="left", anchor="w",
                     wraplength=660).grid(row=2, column=1, sticky="ew",
                                         padx=(0, 12), pady=(4, 0))

        # Detail / result line (shows after step completes)
        detail_lbl = ctk.CTkLabel(card, text="",
                                   font=("Courier New", 9, "bold"),
                                   text_color=NEON_GREEN,
                                   justify="left", anchor="w",
                                   wraplength=660)
        detail_lbl.grid(row=3, column=1, sticky="ew", padx=(0, 12), pady=(2, 0))

        # Action button row
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.grid(row=4, column=1, sticky="w", padx=(0, 12), pady=(8, 12))

        btn = NeonButton(btn_row, step["btn_label"],
                         command=step["action"],
                         color=color, height=38, width=280)
        btn.pack(side="left")

        # "Next →" arrow (hidden until complete)
        arrow_lbl = ctk.CTkLabel(btn_row,
                                  text="",
                                  font=("Courier New", 10, "bold"),
                                  text_color=NEON_GREEN)
        arrow_lbl.pack(side="left", padx=12)

        # Store refs
        self._wiz_widgets[key] = {
            "card":       card,
            "status_lbl": status_lbl,
            "detail_lbl": detail_lbl,
            "btn":        btn,
            "arrow_lbl":  arrow_lbl,
            "color":      color,
        }

    def _wiz_set_state(self, key: str, state: str, detail: str = "",
                       next_key: str = ""):
        """Update a step's visual state — drives StepIndicator + accordion content."""
        self._wiz_states[key] = state
        w = self._wiz_widgets.get(key, {})
        if not w:
            return

        # Map wizard states to StepIndicator states
        indicator_map = {
            self._WIZ_PENDING:   "PENDING",
            self._WIZ_RUNNING:   "RUNNING",
            self._WIZ_DONE_OK:   "DONE",
            self._WIZ_DONE_WARN: "WARNING",
            self._WIZ_DONE_FAIL: "CRITICAL",
            "RUNNING":            "RUNNING",
            "COMPLETE":           "DONE",
        }
        ind_state = indicator_map.get(state, "PENDING")
        if key in self._wiz_indicators:
            self._wiz_indicators[key].set_state(ind_state)

        # Status badge text + color
        badge_colors = {
            self._WIZ_PENDING:   ("PENDING",      TEXT_DIM,    "#0a0a1a"),
            self._WIZ_RUNNING:   ("RUNNING...",    NEON_AMBER,  _dim_color(NEON_AMBER, 0.12)),
            self._WIZ_DONE_OK:   ("COMPLETE ✔",    NEON_GREEN,  _dim_color(NEON_GREEN, 0.12)),
            self._WIZ_DONE_WARN: ("ISSUES FOUND",  NEON_AMBER,  _dim_color(NEON_AMBER, 0.12)),
            self._WIZ_DONE_FAIL: ("CRITICAL ✗",    NEON_RED,    _dim_color(NEON_RED,   0.12)),
        }
        badge_text, badge_fg, badge_bg = badge_colors.get(
            state, (state, TEXT_DIM, "#0a0a1a"))
        w["status_badge"].configure(text=badge_text, text_color=badge_fg,
                                     fg_color=badge_bg)
        w["title_lbl"].configure(text_color=badge_fg)

        # Show result summary and hide detail frame for done states
        is_done = state in (self._WIZ_DONE_OK, self._WIZ_DONE_WARN, self._WIZ_DONE_FAIL)
        is_active = state in (self._WIZ_RUNNING, self._WIZ_PENDING)

        if is_done:
            w["detail_frame"].pack_forget()
            if detail:
                w["result_lbl"].configure(text=detail)
                w["result_lbl"].pack(fill="x", padx=2, pady=(2, 8))
            # Update connector line
            if key in self._wiz_connectors:
                self._wiz_connectors[key].set_done(True)
            # Re-enable button for re-run
            w["btn"].configure(state="normal")
            if next_key:
                w["arrow_lbl"].configure(text=f"  → {next_key.title()} ready")
                self._wiz_set_active(next_key)

        elif state == self._WIZ_RUNNING:
            w["btn"].configure(state="disabled", text="  ⏳  Running...")

        # Update overall progress bar
        done_count = sum(1 for s in self._wiz_states.values()
                         if s in (self._WIZ_DONE_OK, self._WIZ_DONE_WARN,
                                  self._WIZ_DONE_FAIL))
        total = max(len(self._wiz_states), 1)
        progress = done_count / total
        if hasattr(self, '_wiz_overall_bar'):
            self._wiz_overall_bar.set(progress)
            self._wiz_prog_lbl.configure(
                text=f"Step {done_count} of {total} complete")

    def _wiz_set_active(self, key: str):
        """Expand the active step, compact all others."""
        self._wiz_active_step = key
        for k, w in self._wiz_widgets.items():
            if k == key:
                # Expand: show detail frame, highlight title
                color = w["color"]
                w["title_lbl"].configure(text_color=color)
                w["detail_frame"].pack(fill="x", padx=2, pady=(4, 4))
                w["result_lbl"].pack_forget()
                w["btn"].configure(state="normal",
                                    text=f"  ▶  {w['btn'].cget('text').split('▶')[-1].strip() or 'Go'}  ")
                if k in self._wiz_indicators:
                    self._wiz_indicators[k].set_state("ACTIVE")
            elif self._wiz_states.get(k) == self._WIZ_PENDING:
                # Compact: hide detail frame
                w["detail_frame"].pack_forget()
                w["title_lbl"].configure(text_color=TEXT_DIM)

    # ── Step actions ─────────────────────────────────────────────────────────

    def _wiz_step_detect(self):
        """Step 1: auto-detect Sims 4 folder and game root."""
        self._wiz_set_state("detect", self._WIZ_RUNNING)
        self._status("* Detecting Sims 4 folders...")

        def worker():
            s4 = find_s4_folder()
            game_root = DEFAULT_GAME_ROOT
            game_ok   = game_root.exists()
            self.after(0, lambda: self._wiz_detect_done(s4, game_root, game_ok))

        threading.Thread(target=worker, daemon=True).start()

    def _wiz_detect_done(self, s4, game_root, game_ok):
        w = self._wiz_widgets["detect"]
        w["btn"].configure(text=">> AUTO-DETECT FOLDERS")

        if s4 and game_ok:
            self._set_folder(s4)
            self._wiz_game_root = game_root
            detail = (f"✓  Sims 4 data:  {s4}\n"
                      f"✓  Game install: {game_root}")
            self._wiz_set_state("detect", self._WIZ_DONE_OK, detail, "index")
        elif s4:
            self._set_folder(s4)
            detail = (f"✓  Sims 4 data:  {s4}\n"
                      f"⚠  Game install not found at {game_root}\n"
                      f"   Simulation will run in pattern-only mode.")
            self._wiz_set_state("detect", self._WIZ_DONE_WARN, detail, "index")
        else:
            self._wiz_set_state(
                "detect", self._WIZ_DONE_FAIL,
                "✗  Could not find Sims 4 data folder.\n"
                "   Open the EXPERT tabs and click BROWSE to set it manually.")
            self._wiz_widgets["detect"]["btn"].configure(
                text=">> TRY AGAIN / BROWSE",
                command=self._wiz_detect_browse)

    def _wiz_show_fix_all_card(self, report):
        """Insert a prominent FIX ALL card after step 3 in the wizard scroll."""
        # Remove old one if exists
        for child in self._wiz_scroll.winfo_children():
            if getattr(child, '_is_fix_all', False):
                child.destroy()

        near_dups = [d for d in report.dup_file_pairs if d.is_near_duplicate]
        crit = report.critical_count
        total_fix = crit + len(near_dups)

        card = ctk.CTkFrame(self._wiz_scroll,
                            fg_color="#0d001a",
                            border_color=NEON_PINK, border_width=2,
                            corner_radius=8)
        card._is_fix_all = True
        # Use 'row' (new accordion) or 'card' (old design) as reference widget
        sim_w = self._wiz_widgets.get("simulate", {})
        ref   = sim_w.get("row") or sim_w.get("card")
        if ref:
            card.pack(fill="x", padx=6, pady=6, after=ref)
        else:
            card.pack(fill="x", padx=6, pady=6)

        ctk.CTkLabel(card,
                     text="  ⚡ ONE-CLICK FIX ALL",
                     font=("Courier New", 13, "bold"),
                     text_color=NEON_PINK).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(card,
                     text=f"  Quarantines {crit} critical mod(s) + {len(near_dups)} near-exact "
                          f"duplicate(s), then clears caches. "
                          f"Total: {total_fix} file(s) moved to MODS_DISABLED.",
                     font=FONT_SMALL, text_color=TEXT_DIM,
                     wraplength=700, justify="left").pack(anchor="w", padx=12, pady=(0, 6))

        NeonButton(card, f"  ⚡ FIX ALL {total_fix} ISSUES NOW  ",
                   command=lambda r=report: self._wiz_fix_all(r),
                   color=NEON_PINK, height=44).pack(
                       padx=12, pady=(0, 12), fill="x")

    def _wiz_fix_all(self, report):
        """One-shot: quarantine criticals + near-exact dupes + clear cache."""
        if not self.qm or not self.s4_folder:
            messagebox.showwarning("No Folder", "Select a Sims 4 folder first.")
            return

        near_dups = [d for d in report.dup_file_pairs if d.is_near_duplicate]
        crit_files = list({i.file.split("::")[0]
                           for i in report.all_issues
                           if i.severity == "CRITICAL" and
                              (i.file.endswith(".ts4script") or
                               i.file.endswith(".package"))})
        dup_files  = list({d.remove_path for d in near_dups})
        all_files  = list(set(crit_files + dup_files))

        if not all_files:
            messagebox.showinfo("Nothing to Fix", "No files to quarantine.")
            return

        if not messagebox.askyesno(
                "FIX ALL",
                f"Safely quarantine {len(all_files)} file(s)?\n"
                f"  • {len(crit_files)} critical script(s)\n"
                f"  • {len(dup_files)} near-exact duplicate(s)\n\n"
                f"Caches will also be cleared automatically.\n"
                f"Files are NEVER deleted — restore from Fix & Repair."):
            return

        moved = 0
        for path_str in all_files:
            p = Path(path_str)
            if p.exists():
                reason = ("Critical — boot simulator" if path_str in crit_files
                          else "Near-exact duplicate CC")
                if self.qm.quarantine(p, reason, auto=True):
                    moved += 1

        self._clear_cache_silent()

        summary = (f"✓ Fixed! {moved} of {len(all_files)} files quarantined. "
                   f"Caches cleared. Proceed to Step 5 to verify.")

        # Update step 4 and 5 state
        self._wiz_set_state("fix",   self._WIZ_DONE_OK,
                            f"✓ {moved} files quarantined via FIX ALL.", "cache")
        Toast(self, f"⚡ FIX ALL complete — {moved} files quarantined", sev="ok")
        self._status(f"* FIX ALL: {moved} files quarantined + caches cleared")
        messagebox.showinfo("FIX ALL Complete", summary)

    def _wiz_detect_browse(self):
        path = filedialog.askdirectory(
            title="Select your Sims 4 user data folder",
            initialdir=str(Path.home() / "Documents" / "Electronic Arts"),
        )
        if path:
            self._set_folder(Path(path))
            detail = f"✓  Sims 4 data: {path}"
            self._wiz_set_state("detect", self._WIZ_DONE_OK, detail, "index")

    def _wiz_step_index(self):
        """Step 2: build real game index."""
        if not self.s4_folder:
            messagebox.showwarning("Step 1 First",
                "Complete Step 1 (Detect Folders) before indexing.")
            return
        w = self._wiz_widgets["index"]
        self._wiz_set_state("index", self._WIZ_RUNNING)
        # Update subtitle with progress info (result_lbl is in new accordion design)
        if "result_lbl" in w:
            w["result_lbl"].configure(
                text="Reading game Python ZIPs and DBPF packages...\n"
                     "This takes ~45 seconds and is cached for future runs.",
                text_color=NEON_AMBER)
            w["result_lbl"].pack(fill="x", padx=2, pady=(2, 4))

        def worker():
            idx = GameIndex(self._wiz_game_root)

            def progress(msg):
                if "result_lbl" in w:
                    self.after(0, lambda m=msg: w["result_lbl"].configure(
                        text=m, text_color=TEXT_DIM) if w["result_lbl"].winfo_exists() else None)

            if idx.needs_rebuild():
                idx.build(progress_cb=progress)
            else:
                idx.ensure_loaded(progress_cb=progress)

            self._wiz_index = idx
            # Also store for other tabs
            self._game_index_cached = idx
            self.after(0, lambda: self._wiz_index_done(idx))

        threading.Thread(target=worker, daemon=True).start()

    def _wiz_index_done(self, idx):
        w = self._wiz_widgets["index"]
        w["btn"].configure(text=">> BUILD GAME INDEX")
        detail = (f"✓  {idx.module_count:,} game Python modules indexed\n"
                  f"✓  {idx.resource_count:,} base-game resource IDs indexed\n"
                  f"   Simulation will now check imports against real game APIs.")
        self._wiz_set_state("index", self._WIZ_DONE_OK, detail, "simulate")

    def _wiz_step_simulate(self):
        """Step 3: run full boot simulation."""
        if not self.s4_folder:
            messagebox.showwarning("Step 1 First",
                "Complete Step 1 first.")
            return
        if not self._wiz_index and not hasattr(self, '_game_index_cached'):
            if not messagebox.askyesno(
                    "Skip Index?",
                    "Step 2 (Build Game Index) was not run.\n"
                    "The simulation will use pattern-only mode (less accurate).\n\n"
                    "Continue anyway?"):
                return

        w = self._wiz_widgets["simulate"]
        self._wiz_set_state("simulate", self._WIZ_RUNNING)
        if "result_lbl" in w:
            w["result_lbl"].configure(
                text="Running 7-phase simulation... check the BOOT SIM tab for live progress.",
                text_color=NEON_AMBER)
            w["result_lbl"].pack(fill="x", padx=2, pady=(2, 4))
        self._switch_tab("bootsim")

        # Trigger the boot sim tab's runner (which uses the same backend)
        self._boot_running   = False
        self._boot_run_btn.configure(state="normal")
        self.after(200, self._run_boot_sim_from_wizard)

    def _run_boot_sim_from_wizard(self):
        """Run boot sim and hook result back to wizard."""
        self._wiz_boot_done_pending = True
        self._run_boot_sim()

    def _wiz_step_fix(self):
        """Step 4: quarantine all critical issues found by simulation."""
        if not self._wiz_boot_report and not self._boot_report:
            messagebox.showwarning("Step 3 First",
                "Run the Boot Simulation (Step 3) first to identify issues.")
            return

        report = self._wiz_boot_report or self._boot_report
        critical_count = report.critical_count if report else 0

        if critical_count == 0:
            self._wiz_set_state("fix", self._WIZ_DONE_OK,
                                "✓  No critical issues found — nothing to quarantine!",
                                "cache")
            return

        if not messagebox.askyesno(
                "Quarantine Critical Mods",
                f"Safely quarantine {critical_count} critical script(s)?\n\n"
                f"They are NEVER deleted — restore any time from\n"
                f"the FIX & REPAIR tab."):
            return

        self._wiz_set_state("fix", self._WIZ_RUNNING)
        w_fix = self._wiz_widgets["fix"]
        if "result_lbl" in w_fix:
            w_fix["result_lbl"].configure(text="Quarantining critical mods...",
                                           text_color=NEON_AMBER)
            w_fix["result_lbl"].pack(fill="x", padx=2, pady=(2, 4))

        def worker():
            moved = 0
            if report and self.qm:
                for issue in report.all_issues:
                    if issue.severity != "CRITICAL":
                        continue
                    fname = issue.file.split("::")[0]
                    if not (fname.endswith(".ts4script") or fname.endswith(".package")):
                        continue
                    p = Path(fname) if Path(fname).exists() else None
                    if not p:
                        for f in (self.mods_folder or Path()).rglob(
                                Path(fname).name):
                            p = f; break
                    if p and p.exists():
                        if self.qm.quarantine(p, issue.message, auto=True):
                            moved += 1
            self.after(0, lambda: self._wiz_fix_done(moved))

        threading.Thread(target=worker, daemon=True).start()

    def _wiz_fix_done(self, moved: int):
        w = self._wiz_widgets["fix"]
        w["btn"].configure(text=">> QUARANTINE ALL CRITICAL")
        detail = (f"✓  {moved} critical file{'s' if moved != 1 else ''} quarantined\n"
                  f"   They are in MODS_DISABLED and can be restored any time.\n"
                  f"   Now clear the game caches (Step 5) before launching.")
        state = self._WIZ_DONE_OK if moved >= 0 else self._WIZ_DONE_WARN
        self._wiz_set_state("fix", state, detail, "cache")

    def _wiz_step_cache(self):
        """Step 5: clear game caches."""
        if not self.s4_folder:
            messagebox.showwarning("Step 1 First", "Complete Step 1 first.")
            return
        self._wiz_set_state("cache", self._WIZ_RUNNING)
        result = clear_caches(self.s4_folder, verbose=False)
        mb     = result["bytes_freed"] // (1024 * 1024)
        n      = len(result["files"])
        self._stat_cache.set("0")
        detail = (f"✓  Cleared {n} cache file{'s' if n != 1 else ''} ({mb} MB freed)\n"
                  f"   You are now ready to launch the game!\n"
                  f"   Optionally run Step 6 to check your save file first.")
        self._wiz_set_state("cache", self._WIZ_DONE_OK, detail, "save")
        Toast(self, f"✓ Caches cleared ({mb} MB freed) — ready to launch!", sev="ok")
        # Unlock the ready banner
        self._wiz_update_ready_banner()

    # ── Step 6: inline Save Doctor ─────────────────────────────────────────────────

    def _wiz_step_save(self):
        """Step 6: inline save selector, scan, and auto-fix inside the step card."""
        if not self.s4_folder:
            messagebox.showwarning("Step 1 First", "Complete Step 1 first.")
            return

        w       = self._wiz_widgets["save"]
        # Use 'content' (new accordion) or 'card' (old design) as parent
        parent_frame = w.get("content") or w.get("card") or w.get("row")

        # Clean up any previous inline save sub-frame
        for child in parent_frame.winfo_children():
            if getattr(child, '_is_save_sub', False):
                child.destroy()

        # Init state
        self._wiz_selected_save: Path | None = None
        self._wiz_save_report   = None
        self._wiz_sa            = None

        # ── Sub-frame appended below the detail_frame in content area ──
        sub = ctk.CTkFrame(parent_frame, fg_color="#0d0022",
                           border_color=NEON_PINK, border_width=1,
                           corner_radius=6)
        sub._is_save_sub = True
        sub.pack(fill="x", padx=0, pady=(4, 8))

        # ─ Header
        ctk.CTkLabel(sub,
                     text="  Select a save file to check:",
                     font=("Courier New", 10, "bold"),
                     text_color=NEON_PINK).pack(anchor="w", padx=4, pady=(8, 4))

        # ─ Save list
        game_root = (Path(self._inv_root_var.get())
                     if hasattr(self, '_inv_root_var') else DEFAULT_GAME_ROOT)
        sa = SaveAnalyzer(self.s4_folder, game_root,
                          game_index=getattr(self, '_game_index_cached', None))
        self._wiz_sa = sa
        saves = sa.list_saves()

        if not saves:
            ctk.CTkLabel(sub, text="  No .save files found in your saves folder.",
                         font=FONT_SMALL, text_color=TEXT_DIM).pack(
                             anchor="w", padx=8, pady=(0, 8))
            self._wiz_set_state("save", self._WIZ_DONE_WARN,
                                "⚠  No save files found. Nothing to check.")
            return

        # Scrollable list of save buttons
        list_frame = ctk.CTkScrollableFrame(sub, fg_color=BG_DEEP,
                                             height=min(130, len(saves) * 36 + 12),
                                             scrollbar_button_color="#2a001a")
        list_frame.pack(fill="x", padx=8, pady=(0, 6))

        self._wiz_save_btns: dict[str, ctk.CTkButton] = {}

        for save_path in saves[:12]:
            try:
                size_mb = save_path.stat().st_size / (1024 * 1024)
                mtime   = datetime.fromtimestamp(
                    save_path.stat().st_mtime).strftime("%Y-%m-%d  %H:%M")
            except Exception:
                size_mb, mtime = 0.0, "?"
            label = f"  {save_path.name}   ({size_mb:.0f} MB  |  {mtime})"
            btn = ctk.CTkButton(
                list_frame, text=label,
                font=("Courier New", 9),
                fg_color=BG_CARD,
                border_color=NEON_PINK, border_width=1,
                text_color=TEXT_DIM,
                hover_color=_dim_color(NEON_PINK, 0.18),
                anchor="w", corner_radius=4, height=32,
                command=lambda p=save_path: self._wiz_save_select(p))
            btn.pack(fill="x", padx=4, pady=2)
            self._wiz_save_btns[str(save_path)] = btn

        # ─ Action row: SCAN + AUTO FIX
        act_row = ctk.CTkFrame(sub, fg_color="transparent")
        act_row.pack(fill="x", padx=8, pady=(0, 4))

        self._wiz_save_scan_btn = NeonButton(
            act_row, ">> SCAN SELECTED SAVE",
            command=self._wiz_run_save_scan,
            color=NEON_PINK, height=38, width=230)
        self._wiz_save_scan_btn.pack(side="left", padx=(0, 6))
        self._wiz_save_scan_btn.configure(state="disabled")

        self._wiz_save_fix_btn = NeonButton(
            act_row, "⚡ AUTO FIX — GENERATE CLEAN SAVE",
            command=self._wiz_run_save_fix,
            color=NEON_GREEN, height=38, width=280)
        self._wiz_save_fix_btn.pack(side="left")
        self._wiz_save_fix_btn.configure(state="disabled")

        # ─ Results label
        self._wiz_save_result_lbl = ctk.CTkLabel(
            sub, text="←  Click a save above to select it, then SCAN.",
            font=("Courier New", 9), text_color=TEXT_DIM,
            justify="left", anchor="w", wraplength=730)
        self._wiz_save_result_lbl.pack(fill="x", padx=8, pady=(0, 8))

        # Mark step as active/open
        badge = w.get("status_badge") or w.get("status_lbl")
        if badge:
            badge.configure(text="SELECT SAVE", text_color=NEON_PINK,
                            fg_color=_dim_color(NEON_PINK, 0.15))
        w["btn"].configure(text="  ▶  Show My Save Files  ")  # re-enable

    def _wiz_save_select(self, save_path: Path):
        """Highlight a save file selection and enable the scan button."""
        self._wiz_selected_save = save_path
        self._wiz_save_report   = None

        # Highlight selected, dim others
        for path_str, btn in self._wiz_save_btns.items():
            if path_str == str(save_path):
                btn.configure(border_color=NEON_GREEN,
                              text_color=NEON_GREEN,
                              fg_color=_dim_color(NEON_GREEN, 0.08))
            else:
                btn.configure(border_color=NEON_PINK,
                              text_color=TEXT_DIM,
                              fg_color=BG_CARD)

        size_mb = save_path.stat().st_size / (1024 * 1024)
        self._wiz_save_result_lbl.configure(
            text=f"✓ Selected: {save_path.name}  ({size_mb:.0f} MB)\n"
                 f"  Click SCAN SELECTED SAVE to check for broken mod references.",
            text_color=NEON_GREEN)
        self._wiz_save_scan_btn.configure(state="normal")
        self._wiz_save_fix_btn.configure(state="disabled")

    def _wiz_run_save_scan(self):
        """Scan the selected save file for orphaned references (background thread)."""
        if not self._wiz_selected_save or not self._wiz_sa:
            return
        self._wiz_save_scan_btn.configure(state="disabled", text="SCANNING...")
        self._wiz_save_fix_btn.configure(state="disabled")
        self._wiz_save_result_lbl.configure(
            text="Scanning save file for orphaned mod references...\n"
                 "This compares every resource ID in your save against\n"
                 "your installed mods and the base game. Please wait.",
            text_color=NEON_AMBER)

        save_path = self._wiz_selected_save
        sa        = self._wiz_sa

        def worker():
            def log(m):
                self.after(0, lambda msg=m:
                    self._wiz_save_result_lbl.configure(text=msg, text_color=TEXT_DIM)
                    if self._wiz_save_result_lbl.winfo_exists() else None)
            report = sa.analyze(save_path, progress_cb=log)
            self.after(0, lambda r=report: self._wiz_save_scan_done(r))

        threading.Thread(target=worker, daemon=True).start()

    def _wiz_save_scan_done(self, report):
        """Handle save scan completion — show results inline."""
        self._wiz_save_report = report
        self._wiz_save_scan_btn.configure(
            state="normal", text=">> SCAN SELECTED SAVE")

        if report.is_clean:
            result = (
                f"✓  SAVE IS CLEAN — no orphaned references found!\n"
                f"   {report.total_resources:,} resources checked and all accounted for.\n"
                f"   This save is safe to load with your current mod set."
            )
            self._wiz_save_result_lbl.configure(text=result, text_color=NEON_GREEN)
            self._wiz_set_state("save", self._WIZ_DONE_OK,
                                f"✓  Save is clean — {report.total_resources:,} resources verified.")
            Toast(self, f"✓ {report.save_path.split(chr(92))[-1] if chr(92) in report.save_path else report.save_path} is clean!", sev="ok")
            self._wiz_update_ready_banner()
        else:
            crit = report.critical_orphans
            warn = report.warning_orphans
            # Build type breakdown summary
            top_types = sorted(report.orphan_by_type.items(),
                               key=lambda x: -x[1])[:4]
            type_summary = "  |  ".join(f"{t}: {n}" for t, n in top_types)

            result = (
                f"⚠  Found {report.orphaned_resources} orphaned references in this save.\n"
                f"   Critical (will cause issues): {crit}\n"
                f"   Warnings (minor impact):      {warn}\n"
                f"   Top types: {type_summary}\n\n"
                f"   What this means: when you load this save, the game will try to find\n"
                f"   resources from mods that are no longer installed. This can cause\n"
                f"   corrupted Sims, missing traits, and loading crashes.\n\n"
                f"   ↓  Click AUTO FIX to generate a cleaned copy of this save.\n"
                f"   Your original is backed up to .save.bak before any changes."
            )
            self._wiz_save_result_lbl.configure(text=result, text_color=NEON_AMBER)
            self._wiz_save_fix_btn.configure(state="normal")
            self._wiz_set_state("save", self._WIZ_DONE_WARN,
                                f"⚠  {report.orphaned_resources} orphaned refs found — click AUTO FIX below")
            Toast(self, f"⚠ Save has {report.orphaned_resources} orphaned references", sev="warning")

    def _wiz_run_save_fix(self):
        """Generate a clean save (background thread)."""
        if not self._wiz_save_report or not self._wiz_sa:
            return
        report = self._wiz_save_report
        if not messagebox.askyesno(
                "Generate Clean Save",
                f"Remove {report.orphaned_resources} orphaned references from\n"
                f"{Path(report.save_path).name}?\n\n"
                f"What happens:\n"
                f"  • Original backed up to .save.bak (NEVER deleted)\n"
                f"  • Clean copy written as {Path(report.save_path).stem}_clean.save\n"
                f"  • Affected Sims may lose traits/careers from removed mods\n"
                f"  • Building objects from removed mods will disappear from lots"):
            return

        self._wiz_save_fix_btn.configure(state="disabled", text="GENERATING...")
        self._wiz_save_scan_btn.configure(state="disabled")

        sa     = self._wiz_sa
        result = self._wiz_save_result_lbl

        def worker():
            def log(m):
                self.after(0, lambda msg=m:
                    result.configure(text=msg, text_color=NEON_CYAN)
                    if result.winfo_exists() else None)
            try:
                out_path = sa.generate_clean_save(report, progress_cb=log)
                self.after(0, lambda p=out_path: self._wiz_save_fix_done(report, p))
            except Exception as e:
                self.after(0, lambda err=str(e): (
                    self._wiz_save_fix_btn.configure(
                        state="normal", text="⚡ AUTO FIX — GENERATE CLEAN SAVE"),
                    self._wiz_save_scan_btn.configure(state="normal"),
                    messagebox.showerror("Fix Failed", f"Clean save failed:\n{err}")))

        threading.Thread(target=worker, daemon=True).start()

    def _wiz_save_fix_done(self, report, out_path: Path):
        """Show clean-save success inline."""
        self._wiz_save_fix_btn.configure(
            state="normal", text="⚡ AUTO FIX — GENERATE CLEAN SAVE")
        self._wiz_save_scan_btn.configure(state="normal")

        out_name = out_path.name
        detail = (
            f"✓  CLEAN SAVE WRITTEN: {out_name}\n"
            f"   {report.resources_removed} orphaned entries removed.\n"
            f"   Original backed up to: {Path(report.save_path).name}.bak\n"
            f"   Load {out_name} next time you start the game."
        )
        self._wiz_save_result_lbl.configure(text=detail, text_color=NEON_GREEN)
        self._wiz_set_state("save", self._WIZ_DONE_OK,
                            f"✓  Clean save written: {out_name}  ({report.resources_removed} entries removed)")
        Toast(self, f"✓ Clean save ready: {out_name}", sev="ok")
        self._wiz_update_ready_banner()

    def _wiz_update_ready_banner(self):
        """Show/update the launch-ready banner at the bottom of the wizard."""
        report  = self._wiz_boot_report or self._boot_report
        prob    = report.crash_probability if report else 0
        verdict = report.verdict_label     if report else "READY"
        color   = report.verdict_color     if report else NEON_GREEN
        grade   = report.health_grade      if report else "A"
        gc      = report.health_grade_color if report else NEON_GREEN

        for w in self._wiz_ready_frame.winfo_children():
            w.destroy()

        top = ctk.CTkFrame(self._wiz_ready_frame, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(12, 4))

        # Grade circle
        ctk.CTkLabel(top,
                     text=grade,
                     font=("Courier New", 48, "bold"),
                     text_color=gc).pack(side="left", padx=(0, 16))

        right = ctk.CTkFrame(top, fg_color="transparent")
        right.pack(side="left", anchor="w")
        ctk.CTkLabel(right,
                     text="SYSTEM STATUS — READY TO BOOT",
                     font=("Courier New", 13, "bold"),
                     text_color=NEON_GREEN).pack(anchor="w")
        ctk.CTkLabel(right,
                     text=f"{verdict}   |   Crash risk: {prob}%   |   Grade: {grade}",
                     font=("Courier New", 11, "bold"),
                     text_color=color).pack(anchor="w")
        ctk.CTkLabel(right,
                     text="Caches cleared. Mods checked. Launch when ready.",
                     font=FONT_SMALL, text_color=TEXT_DIM).pack(anchor="w")

        NeonButton(self._wiz_ready_frame,
                   ">> LAUNCH SIMS 4  —  OPEN LAUNCHER",
                   command=lambda: self._switch_tab("launcher"),
                   color=NEON_GREEN, height=44).pack(
                       pady=(4, 4), padx=20, fill="x")
        NeonButton(self._wiz_ready_frame,
                   "OPEN FULL HTML REPORT",
                   command=self._rpt_open_browser,
                   color=NEON_CYAN, height=36).pack(
                       pady=(0, 12), padx=20, fill="x")

    # ─── Hook wizard into boot_done and save_done results ────────────────────

    def _wiz_on_boot_done(self, report):
        """Called after boot simulation completes — update wizard step 3."""
        self._wiz_boot_report = report
        crit = report.critical_count
        warn = report.warning_count
        prob = report.crash_probability

        if crit > 0:
            state  = self._WIZ_DONE_FAIL
            detail = (f"✗  {crit} CRITICAL issue{'s' if crit>1 else ''} detected — "
                      f"game WILL likely crash!\n"
                      f"   Crash probability: {prob}%  |  {warn} warnings also found\n"
                      f"   → Proceed to Step 4 to quarantine the broken mods.")
            next_key = "fix"
        elif warn > 0:
            state  = self._WIZ_DONE_WARN
            detail = (f"⚠  {warn} warning{'s' if warn>1 else ''} found "
                      f"(crash probability: {prob}%)\n"
                      f"   No critical issues — you may skip Step 4.\n"
                      f"   → Proceed to Step 5 to clear caches.")
            next_key = "cache"
        else:
            state  = self._WIZ_DONE_OK
            detail = (f"✓  CLEAN BOOT — no issues detected!\n"
                      f"   Crash probability: {prob}%\n"
                      f"   → Proceed to Step 5 to clear caches.")
            next_key = "cache"

        w = self._wiz_widgets.get("simulate", {})
        if w:
            w["btn"].configure(text=">> RUN BOOT SIMULATION")
        self._wiz_set_state("simulate", state, detail, next_key)

        # Show FIX ALL card if there are issues
        if report.critical_count > 0 or sum(1 for d in report.dup_file_pairs if d.is_near_duplicate) > 0:
            self._wiz_show_fix_all_card(report)

        Toast(self,
              f"✓ Simulation done: {report.verdict_label}  Grade: {report.health_grade}",
              sev="ok" if report.crash_probability < 30 else
                  "warning" if report.crash_probability < 60 else "critical")
        # Switch back to wizard
        self._switch_tab("wizard")

    # ═══════════════════════════════════════════════════════════════════════════
    # ── REPORT VIEWER TAB ─────────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_report_tab(self, parent):
        """In-app styled report viewer with Print and Export."""
        self._rpt_text = None

        # Toolbar
        toolbar = ctk.CTkFrame(parent, fg_color=BG_HEADER)
        toolbar.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(toolbar, text="  LAST AUDIT REPORT",
                     font=("Courier New", 11, "bold"),
                     text_color=NEON_GREEN).pack(side="left", padx=4, pady=6)
        NeonButton(toolbar, "REFRESH",
                   command=self._rpt_refresh,
                   color=NEON_GREEN, width=100, height=30).pack(side="left", padx=4, pady=4)
        NeonButton(toolbar, "OPEN HTML",
                   command=self._rpt_open_browser,
                   color=NEON_CYAN, width=110, height=30).pack(side="left", padx=4, pady=4)
        NeonButton(toolbar, "PRINT",
                   command=self._rpt_print,
                   color=NEON_AMBER, width=80, height=30).pack(side="left", padx=4, pady=4)
        NeonButton(toolbar, "EXPORT...",
                   command=self._rpt_export,
                   color=NEON_PURPLE, width=100, height=30).pack(side="left", padx=4, pady=4)

        # Text area
        frame = neon_frame(parent, color=NEON_GREEN)
        frame.pack(fill="both", expand=True)
        self._rpt_text = ConsoleText(frame)
        sb = ctk.CTkScrollbar(frame, command=self._rpt_text.yview,
                               button_color="#002d1e")
        sb.pack(side="right", fill="y")
        self._rpt_text.configure(yscrollcommand=sb.set)
        self._rpt_text.pack(fill="both", expand=True, padx=4, pady=4)
        self._rpt_text.append("Run a Boot Simulation to generate a report.", "dim")
        self._rpt_text.append("Then click REFRESH to view it here.", "dim")

    def _rpt_refresh(self):
        """Render the most recent BootReport as styled text in the Report Viewer."""
        if not hasattr(self, '_rpt_text') or not self._rpt_text:
            return
        report = getattr(self, '_boot_report', None)
        if not report:
            return

        t = self._rpt_text
        t.clear()

        # Header
        t.append("═" * 60, "dim")
        t.append(f"  SIMS4 MOD GUARDIAN  —  AUDIT REPORT", "header")
        t.append(f"  Game: {report.game_version}   Mods: {report.total_packages:,} packages", "dim")
        t.append("═" * 60, "dim")

        # Verdict + grade
        grade_tag = {"A": "ok", "B": "ok", "C": "warning", "D": "warning",
                     "F": "critical"}.get(report.health_grade, "dim")
        t.append(f"", "")
        t.append(f"  CC GRADE: {report.health_grade}   —   {report.verdict_label}", grade_tag)
        t.append(f"  Crash probability: {report.crash_probability}%   "
                 f"Critical: {report.critical_count}   "
                 f"Warnings: {report.warning_count}",
                 "critical" if report.crash_probability >= 60 else
                 "warning"  if report.crash_probability >= 30 else "ok")
        near = sum(1 for d in report.dup_file_pairs if d.is_near_duplicate)
        t.append(f"  Near-exact duplicates: {near}   Total pairs: {len(report.dup_file_pairs)}", "info")
        t.append("", "")

        # Phase table
        t.append("─" * 60, "dim")
        t.append(f"  {'PHASE':<22} {'STATUS':<10} {'ISSUES':>7}  KEY STAT", "bold")
        t.append("─" * 60, "dim")
        for ph in report.phases:
            tag  = {"PASS": "ok", "WARN": "warning", "FAIL": "critical"}.get(ph.status, "dim")
            from sims4modguard.run_logger import _phase_key_stat
            t.append(f"  {ph.name:<22} {ph.status:<10} {len(ph.issues):>7}  {_phase_key_stat(ph)}", tag)
        t.append("", "")

        # Critical issues
        criticals = [i for i in report.all_issues if i.severity == "CRITICAL"]
        if criticals:
            t.append("─" * 60, "dim")
            t.append(f"  CRITICAL ISSUES ({len(criticals)}) — WILL CAUSE CRASHES", "critical")
            t.append("─" * 60, "dim")
            for iss in criticals:
                t.append(f"  FILE: {iss.file[:65]}", "info")
                t.append(f"  [!!] {iss.message}", "critical")
                if iss.fix:
                    t.append(f"  FIX: {iss.fix}", "ok")
                mod = lookup_mod(iss.file)
                if mod:
                    t.append(f"  GET UPDATE: {mod['display_name']} ({mod['update_url']})", "info")
                t.append("", "")
        else:
            t.append("  ✓ No critical issues — scripts are clean!", "ok")
            t.append("", "")

        # Near-exact duplicates
        near_dups = [d for d in report.dup_file_pairs if d.is_near_duplicate]
        if near_dups:
            t.append("─" * 60, "dim")
            t.append(f"  NEAR-EXACT DUPLICATES ({len(near_dups)}) — same CC twice", "warning")
            t.append("─" * 60, "dim")
            for rank, dup in enumerate(near_dups[:30], 1):
                remove = Path(dup.remove_path).name
                keep   = dup.name_a if dup.remove_path == dup.file_b else dup.name_b
                t.append(f"  {rank:>3}. Shared: {dup.shared_ids:,}  Type: {dup.dominant_type}", "dim")
                t.append(f"       KEEP:   {keep[:65]}", "ok")
                t.append(f"       REMOVE: {remove[:65]}", "warning")
                mod_a = lookup_mod(dup.file_a)
                mod_b = lookup_mod(dup.file_b)
                mod   = mod_a or mod_b
                if mod:
                    t.append(f"       UPDATE: {mod['display_name']}: {mod['update_url']}", "info")
                t.append("", "")
            if len(near_dups) > 30:
                t.append(f"  ... and {len(near_dups)-30} more. Open HTML report for full list.", "dim")

        t.append("═" * 60, "dim")
        t.append("  Click OPEN HTML for the full report with clickable URLs.", "dim")
        t.append("═" * 60, "dim")

    def _rpt_open_browser(self):
        path = getattr(self, '_last_report_path', None)
        if not path:
            logger = RunLogger()
            path = logger.open_latest()
        if path and path.exists():
            webbrowser.open(path.as_uri())
        else:
            messagebox.showinfo("No Report", "Run a Boot Simulation first to generate a report.")

    def _rpt_print(self):
        path = getattr(self, '_last_report_path', None)
        if not path:
            logger = RunLogger()
            path = logger.open_latest()
        if path and path.exists():
            try:
                os.startfile(str(path), "print")
                Toast(self, "Opening print dialog...", sev="info")
            except Exception as e:
                # Fallback: open in browser and let user print from there
                webbrowser.open(path.as_uri())
                messagebox.showinfo("Print",
                    "Report opened in browser. Press Ctrl+P to print.")
        else:
            messagebox.showinfo("No Report", "Run a Boot Simulation first.")

    def _rpt_export(self):
        path = getattr(self, '_last_report_path', None)
        if not path:
            logger = RunLogger()
            path = logger.open_latest()
        if not path or not path.exists():
            messagebox.showinfo("No Report", "Run a Boot Simulation first.")
            return
        dest = filedialog.asksaveasfilename(
            title="Export Audit Report",
            initialfile=path.name,
            defaultextension=".html",
            filetypes=[("HTML Report", "*.html"), ("Text Report", "*.txt"), ("All", "*.*")],
        )
        if dest:
            dest_path = Path(dest)
            if dest_path.suffix == ".txt":
                # Copy text version
                txt_path = path.with_suffix(".txt")
                if txt_path.exists():
                    shutil.copy2(txt_path, dest_path)
            else:
                shutil.copy2(path, dest_path)
            Toast(self, f"✓ Report exported to {dest_path.name}", sev="ok")
            self._status(f"* Report exported: {dest_path}")

    # ═══════════════════════════════════════════════════════════════════════════
    # ── INVENTORY TAB ──────────────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_inventory_tab(self, parent):
        """System inventory: game version, DLC grid, mod counts."""
        self._inv_game_root = DEFAULT_GAME_ROOT

        # -- Top action row --
        action_row = ctk.CTkFrame(parent, fg_color="transparent")
        action_row.pack(fill="x", pady=(0, 8))
        NeonButton(action_row, ">> SCAN SYSTEM",
                   command=self._run_inventory_scan,
                   color=NEON_CYAN, height=40, width=180).pack(side="left", padx=4)
        NeonButton(action_row, "BROWSE GAME ROOT",
                   command=self._browse_game_root,
                   color=NEON_AMBER, height=40, width=180).pack(side="left", padx=4)
        self._inv_root_var = tk.StringVar(value=str(DEFAULT_GAME_ROOT))
        ctk.CTkEntry(action_row, textvariable=self._inv_root_var,
                     font=FONT_MONO_S, fg_color=BG_CARD,
                     border_color=NEON_CYAN, border_width=1,
                     text_color=NEON_GREEN).pack(side="left", fill="x", expand=True, padx=4)

        # -- Stat cards --
        sc_row = ctk.CTkFrame(parent, fg_color="transparent")
        sc_row.pack(fill="x", pady=(0, 8))
        for i in range(5): sc_row.columnconfigure(i, weight=1)
        self._inv_ver    = StatCard(sc_row, "GAME VERSION", color=NEON_CYAN)
        self._inv_dlc    = StatCard(sc_row, "DLC INSTALLED", color=NEON_GREEN)
        self._inv_mods   = StatCard(sc_row, "MOD PACKAGES", color=NEON_AMBER)
        self._inv_scr    = StatCard(sc_row, "SCRIPTS",      color=NEON_PURPLE)
        self._inv_depth  = StatCard(sc_row, "DEPTH ERR",    color=NEON_RED)
        for i, c in enumerate([self._inv_ver, self._inv_dlc, self._inv_mods,
                                self._inv_scr, self._inv_depth]):
            c.grid(row=0, column=i, padx=4, sticky="nsew")

        # -- Scrollable content --
        scroll = ctk.CTkScrollableFrame(parent, fg_color=BG_DEEP,
                                        scrollbar_button_color="#002d3d")
        scroll.pack(fill="both", expand=True)
        self._inv_scroll = scroll

        ctk.CTkLabel(scroll, text="Click >> SCAN SYSTEM to inventory your installation.",
                     font=FONT_LABEL, text_color=TEXT_DIM).pack(pady=40)

    def _browse_game_root(self):
        path = filedialog.askdirectory(
            title="Select Sims 4 game installation root",
            initialdir=str(self._inv_game_root),
        )
        if path:
            self._inv_game_root = Path(path)
            self._inv_root_var.set(path)

    def _run_inventory_scan(self):
        if not self.s4_folder:
            messagebox.showwarning("No Folder", "Select a Sims 4 folder first.")
            return
        self._status("* Scanning system inventory...")
        game_root = Path(self._inv_root_var.get())

        def worker():
            # Game version
            ver = read_game_version(self.s4_folder)
            # DLC
            try:
                dlc = dlc_summary(game_root)
                dlc_installed = dlc["installed"]
                dlc_total     = dlc["total"]
                installed_map = dlc["installed_map"]
            except Exception:
                dlc_installed, dlc_total, installed_map = 0, 0, {}
            # Mods
            mods_folder = self.s4_folder / "Mods"
            scripts  = packages = depth_err = 0
            base_depth = len(mods_folder.parts)
            if mods_folder.exists():
                for f in mods_folder.rglob("*"):
                    if not f.is_file() or "MODS_DISABLED" in str(f):
                        continue
                    depth = len(f.parts) - base_depth
                    if f.suffix == ".ts4script":
                        scripts += 1
                        if depth > 5: depth_err += 1
                    elif f.suffix == ".package":
                        packages += 1
                        if depth > 5: depth_err += 1
            self.after(0, lambda: self._finish_inventory(
                ver, dlc_installed, dlc_total, installed_map,
                packages, scripts, depth_err, game_root))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_inventory(self, ver, dlc_installed, dlc_total, installed_map,
                           packages, scripts, depth_err, game_root):
        # Update stat cards
        short_ver = ".".join(ver.split(".")[:2]) if "." in ver else ver
        self._inv_ver.set(short_ver)
        self._inv_dlc.set(f"{dlc_installed}/{dlc_total}")
        self._inv_mods.set(f"{packages:,}")
        self._inv_scr.set(str(scripts))
        self._inv_depth.set(str(depth_err))

        # Clear scroll area
        for w in self._inv_scroll.winfo_children():
            w.destroy()

        # Game version card
        ver_card = neon_frame(self._inv_scroll, color=NEON_CYAN)
        ver_card.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(ver_card, text=f"GAME VERSION: {ver}",
                     font=("Courier New", 12, "bold"), text_color=NEON_CYAN).pack(
                         anchor="w", padx=12, pady=4)
        ctk.CTkLabel(ver_card, text=f"Game root: {game_root}",
                     font=FONT_SMALL, text_color=TEXT_DIM).pack(anchor="w", padx=12, pady=(0, 6))

        # DLC grid
        ctk.CTkLabel(self._inv_scroll, text="DLC PACKS",
                     font=FONT_HEAD, text_color=NEON_GREEN).pack(anchor="w", padx=8, pady=(8, 4))
        dlc_grid_frame = ctk.CTkFrame(self._inv_scroll, fg_color="transparent")
        dlc_grid_frame.pack(fill="x", padx=4)
        cols = 5
        for i in range(cols): dlc_grid_frame.columnconfigure(i, weight=1)

        ordered_codes = (
            [f"EP{n:02d}" for n in range(1, 22)] +
            [f"GP{n:02d}" for n in range(1, 13)] +
            [f"SP{n:02d}" for n in range(1, 12)] +
            ["FP01"]
        )
        for idx, code in enumerate(ordered_codes):
            info = DLC_CATALOG.get(code, {})
            is_installed = installed_map.get(code, False)
            pack_type = info.get("type", "")
            type_color = TYPE_COLOR.get(pack_type, NEON_CYAN)
            badge_color = type_color if is_installed else "#2a0a0a"
            text_color  = TEXT_BRIGHT if is_installed else TEXT_DIM
            border_color = type_color if is_installed else NEON_RED

            badge = ctk.CTkFrame(dlc_grid_frame, fg_color=badge_color,
                                 border_color=border_color, border_width=1,
                                 corner_radius=4)
            r, c = divmod(idx, cols)
            badge.grid(row=r, column=c, padx=3, pady=3, sticky="ew")
            ctk.CTkLabel(badge, text=code, font=("Courier New", 9, "bold"),
                         text_color=text_color).pack(pady=(4, 0))
            name = info.get("name", "")[:22]
            ctk.CTkLabel(badge, text=name, font=("Courier New", 7),
                         text_color=text_color).pack(pady=(0, 4))

        # Mods summary
        ctk.CTkLabel(self._inv_scroll, text="MOD BREAKDOWN",
                     font=FONT_HEAD, text_color=NEON_AMBER).pack(anchor="w", padx=8, pady=(16, 4))
        summary_frame = neon_frame(self._inv_scroll, color=NEON_AMBER)
        summary_frame.pack(fill="x", padx=4, pady=4)
        for label, value, color in [
            ("Total .package files",  f"{packages:,}",  NEON_GREEN),
            ("Total .ts4script files", str(scripts),    NEON_PURPLE),
            ("Depth violations (>5)",  str(depth_err),  NEON_RED if depth_err else NEON_GREEN),
        ]:
            row = ctk.CTkFrame(summary_frame, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(row, text=label, font=FONT_LABEL, text_color=TEXT_DIM).pack(side="left")
            ctk.CTkLabel(row, text=value, font=("Courier New", 12, "bold"),
                         text_color=color).pack(side="right")

        self._status(f"* Inventory complete — {dlc_installed}/{dlc_total} DLC, {packages:,} mods")

    # ═══════════════════════════════════════════════════════════════════════════
    # ── BOOT SIMULATOR TAB ─────────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_bootsim_tab(self, parent):
        """7-phase boot simulation with animated phase status rows."""
        self._boot_running   = False
        self._boot_report    = None
        self._boot_phase_widgets = {}   # phase_name -> (status_lbl, bar, detail_lbl)
        self._game_index_cached: GameIndex | None = None

        # -- Action row --
        action_row = ctk.CTkFrame(parent, fg_color="transparent")
        action_row.pack(fill="x", pady=(0, 8))
        self._boot_run_btn = NeonButton(action_row, ">> RUN FULL BOOT SIMULATION",
                                        command=self._run_boot_sim,
                                        color=NEON_GREEN, height=48, width=280)
        self._boot_run_btn.pack(side="left", padx=4)
        NeonButton(action_row, "REBUILD INDEX",
                   command=self._rebuild_game_index,
                   color=NEON_CYAN, height=48, width=150).pack(side="left", padx=4)
        NeonButton(action_row, "OPEN LAST REPORT",
                   command=self._open_last_report,
                   color=NEON_PURPLE, height=48, width=180).pack(side="left", padx=4)
        self._boot_prog_lbl = ctk.CTkLabel(action_row, text="",
                                            font=FONT_SMALL, text_color=TEXT_DIM)
        self._boot_prog_lbl.pack(side="left", padx=8)

        # -- Overall progress bar --
        self._boot_overall_bar = ctk.CTkProgressBar(
            parent, progress_color=NEON_GREEN, fg_color=BG_CARD,
            height=6, corner_radius=2)
        self._boot_overall_bar.pack(fill="x", pady=(0, 8))
        self._boot_overall_bar.set(0)

        # -- Split: phase panel (left) + live console (right) --
        split = ctk.CTkFrame(parent, fg_color="transparent")
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=2)
        split.columnconfigure(1, weight=3)

        # Phase panel
        phase_panel = neon_frame(split, color="#003d26")
        phase_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        ctk.CTkLabel(phase_panel, text="BOOT PHASES",
                     font=("Courier New", 10, "bold"),
                     text_color=NEON_GREEN).pack(pady=(8, 4))

        for phase_name in PHASES:
            row = ctk.CTkFrame(phase_panel, fg_color=BG_CARD, corner_radius=4)
            row.pack(fill="x", padx=8, pady=3)
            row.columnconfigure(1, weight=1)

            status_lbl = ctk.CTkLabel(row, text="PENDING",
                                       font=("Courier New", 9, "bold"),
                                       text_color=TEXT_DIM, width=70)
            status_lbl.grid(row=0, column=0, padx=6, pady=(6, 0))

            name_lbl = ctk.CTkLabel(row, text=phase_name,
                                     font=("Courier New", 10, "bold"),
                                     text_color=NEON_CYAN, anchor="w")
            name_lbl.grid(row=0, column=1, padx=4, sticky="ew")

            bar = ctk.CTkProgressBar(row, progress_color=NEON_GREEN,
                                      fg_color=BG_DEEP, height=3)
            bar.grid(row=1, column=0, columnspan=2, padx=6, pady=(2, 4), sticky="ew")
            bar.set(0)

            detail_lbl = ctk.CTkLabel(row, text="",
                                       font=("Courier New", 8),
                                       text_color=TEXT_DIM, anchor="w")
            detail_lbl.grid(row=2, column=0, columnspan=2, padx=6, pady=(0, 4), sticky="ew")

            self._boot_phase_widgets[phase_name] = (status_lbl, bar, detail_lbl)

        # Verdict panel (initially hidden)
        self._boot_verdict_frame = ctk.CTkFrame(phase_panel,
                                                 fg_color=BG_CARD, corner_radius=6)

        # Live console
        console_panel = neon_frame(split, color="#002d1e")
        console_panel.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(console_panel, text="SIMULATION LOG",
                     font=("Courier New", 10, "bold"),
                     text_color=NEON_GREEN).pack(pady=(8, 4), anchor="w", padx=8)
        self._boot_console = ConsoleText(console_panel)
        sb = ctk.CTkScrollbar(console_panel, command=self._boot_console.yview,
                               button_color="#002d1e")
        sb.pack(side="right", fill="y")
        self._boot_console.configure(yscrollcommand=sb.set)
        self._boot_console.pack(fill="both", expand=True, padx=4, pady=4)
        self._boot_console.append("Ready. Click RUN FULL BOOT SIMULATION to begin.", "dim")
        self._boot_console.append("This will scan all scripts, CC, and check imports against", "dim")
        self._boot_console.append("the real game module registry without booting the game.", "dim")

    def _rebuild_game_index(self):
        """Force-rebuild the game index from game files."""
        if not self.s4_folder:
            messagebox.showwarning("No Folder", "Select a Sims 4 folder first.")
            return
        game_root = Path(self._inv_root_var.get()) if hasattr(self, '_inv_root_var') else DEFAULT_GAME_ROOT
        self._boot_console.clear()
        self._boot_console.append("Rebuilding game index from real game files...", "info")
        self._boot_console.append(f"  Game root: {game_root}", "dim")

        def worker():
            idx = GameIndex(game_root)
            idx.build(progress_cb=lambda m: self._q.put(
                {"action": "boot_phase", "event": "log", "msg": m, "sev": "INFO"}))
            self._game_index_cached = idx
            self._q.put({"action": "boot_phase", "event": "log",
                         "msg": f"Index built: {idx.module_count:,} modules, {idx.resource_count:,} resources",
                         "sev": "OK"})
        threading.Thread(target=worker, daemon=True).start()

    def _run_boot_sim(self):
        if not self.s4_folder:
            messagebox.showwarning("No Folder", "Select a Sims 4 folder first.")
            return
        if self._boot_running:
            return
        self._boot_running = True
        self._boot_run_btn.configure(state="disabled")
        self._boot_console.clear()
        self._boot_overall_bar.set(0)

        # Reset all phase widgets
        for ph, (sl, bar, dl) in self._boot_phase_widgets.items():
            sl.configure(text="PENDING", text_color=TEXT_DIM)
            bar.set(0)
            bar.configure(progress_color=NEON_GREEN)
            dl.configure(text="")
        for w in self._boot_verdict_frame.winfo_children():
            w.destroy()
        self._boot_verdict_frame.pack_forget()

        game_root = Path(self._inv_root_var.get()) if hasattr(self, '_inv_root_var') else DEFAULT_GAME_ROOT

        def worker():
            idx = self._game_index_cached or GameIndex(game_root)
            engine = BootEngine(self.s4_folder, game_root, game_index=idx)

            def cb(phase, pct, msg, sev="INFO"):
                self._q.put({"action": "boot_phase",
                              "event": "progress",
                              "phase": phase, "pct": pct,
                              "msg": msg, "sev": sev})
            report = engine.run(progress_cb=cb)
            self._game_index_cached = idx
            self._q.put({"action": "boot_done", "report": report})

        threading.Thread(target=worker, daemon=True).start()

    def _on_boot_phase(self, msg):
        event = msg.get("event", "")
        sev = msg.get("sev", "INFO")
        log_tag = {"CRITICAL": "critical", "WARNING": "warning",
                   "OK": "ok", "INFO": "info"}.get(sev, "info")

        if event == "log":
            self._boot_console.append(msg.get("msg", ""), log_tag)
            return

        # event == "progress"
        phase = msg.get("phase", "")
        pct   = msg.get("pct",   0.0)
        text  = msg.get("msg",   "")

        self._boot_console.append(f"[{phase}] {text}", log_tag)
        self._boot_prog_lbl.configure(text=f"{phase}: {int(pct*100)}%")

        # Update global progress (7 phases total)
        phase_idx = PHASES.index(phase) if phase in PHASES else 0
        global_pct = (phase_idx + pct) / len(PHASES)
        self._boot_overall_bar.set(global_pct)

        # Update per-phase widget
        if phase in self._boot_phase_widgets:
            sl, bar, dl = self._boot_phase_widgets[phase]
            bar.set(pct)
            sl.configure(text="RUNNING", text_color=NEON_AMBER)
            dl.configure(text=text[:60])

    def _on_boot_done(self, report):
        self._boot_running = False
        self._boot_run_btn.configure(state="normal")
        self._boot_overall_bar.set(1.0)
        self._boot_report = report
        # Feed result back to wizard if it triggered this run
        if getattr(self, '_wiz_boot_done_pending', False):
            self._wiz_boot_done_pending = False
            self._wiz_on_boot_done(report)

        SEV_COLORS = {"PASS": NEON_GREEN, "WARN": NEON_AMBER,
                      "FAIL": NEON_RED, "SKIP": TEXT_DIM}

        # Update phase widgets with final status
        for ph_result in report.phases:
            ph = ph_result.name
            if ph in self._boot_phase_widgets:
                sl, bar, dl = self._boot_phase_widgets[ph]
                color = SEV_COLORS.get(ph_result.status, TEXT_DIM)
                sl.configure(text=ph_result.status, text_color=color)
                bar.set(1.0)
                bar.configure(progress_color=color)
                issues = len(ph_result.issues)
                dl.configure(text=f"{issues} issue{'s' if issues != 1 else ''} found" if issues else "Clean")

        # Show verdict
        v = self._boot_verdict_frame
        for w in v.winfo_children(): w.destroy()
        v.pack(fill="x", padx=8, pady=8)

        prob_color  = report.verdict_color
        grade_color = report.health_grade_color

        # Grade + verdict row
        gv_row = ctk.CTkFrame(v, fg_color="transparent")
        gv_row.pack(fill="x", padx=8, pady=(8, 0))
        ctk.CTkLabel(gv_row,
                     text=report.health_grade,
                     font=("Courier New", 42, "bold"),
                     text_color=grade_color).pack(side="left", padx=(0, 12))
        vbox = ctk.CTkFrame(gv_row, fg_color="transparent")
        vbox.pack(side="left", anchor="w")
        ctk.CTkLabel(vbox, text=f"VERDICT: {report.verdict_label}",
                     font=("Courier New", 14, "bold"),
                     text_color=prob_color).pack(anchor="w")
        ctk.CTkLabel(vbox, text=f"Crash probability: {report.crash_probability}%",
                     font=("Courier New", 11), text_color=prob_color).pack(anchor="w")
        ctk.CTkLabel(vbox,
                     text=f"Critical: {report.critical_count}  |  Warnings: {report.warning_count}  "
                          f"|  Near-dupes: {sum(1 for d in report.dup_file_pairs if d.is_near_duplicate)}",
                     font=FONT_LABEL, text_color=TEXT_DIM).pack(anchor="w", pady=(2, 0))

        if report.critical_count > 0:
            NeonButton(v, "XX QUARANTINE ALL CRITICAL",
                       command=self._boot_quarantine_critical,
                       color=NEON_RED, height=36).pack(fill="x", padx=8, pady=(4, 8))

        # ── Duplicate CC files panel ─────────────────────────────────────────
        if report.dup_file_pairs:
            self._show_dup_panel(report)

        # Log final summary
        self._boot_console.append("-" * 55, "dim")
        self._boot_console.append(f"SIMULATION COMPLETE: {report.verdict_label}", "bold")
        self._boot_console.append(
            f"  Crash probability: {report.crash_probability}%  |  "
            f"{report.critical_count} critical  |  {report.warning_count} warnings",
            "critical" if report.crash_probability >= 60 else
            "warning"  if report.crash_probability >= 30 else "ok")

        top_issues = sorted(report.all_issues,
                            key=lambda i: 0 if i.severity == "CRITICAL" else 1)[:10]
        for issue in top_issues:
            tag = "critical" if issue.severity == "CRITICAL" else "warning"
            self._boot_console.append(
                f"  [{issue.severity}] {issue.file[:40]}: {issue.message}", tag)

        self._status(f"* Boot simulation done — {report.verdict_label} "
                     f"({report.crash_probability}% crash risk)")
        Toast(self, f"✓ Boot simulation complete: {report.verdict_label} "
              f"({report.crash_probability}% crash risk)  Grade: {report.health_grade}",
              sev="ok" if report.crash_probability < 30 else
                  "warning" if report.crash_probability < 60 else "critical")

        # Refresh report viewer if open
        self.after(500, self._rpt_refresh)

        # Auto-save HTML + text log
        try:
            logger = RunLogger()
            from datetime import datetime
            elapsed = ""
            html_path, txt_path = logger.save(
                report, quarantined=[], label=f"GUI run — {datetime.now().strftime('%H:%M:%S')}")
            self._boot_console.append("-" * 50, "dim")
            self._boot_console.append(f"LOG SAVED: {html_path.name}", "ok")
            self._boot_console.append(f"  Open Last Report to view full breakdown.", "dim")
            self._last_report_path = html_path
        except Exception as e:
            self._boot_console.append(f"(Log save failed: {e})", "warning")
            return
        Toast(self, f"Report saved: {html_path.name}", sev="info")

    def _show_dup_panel(self, report):
        """Render the duplicate CC file list below the verdict in the boot sim tab."""
        # Container (reuse or create inside phase panel)
        phase_panel = None
        for child in self._boot_verdict_frame.master.winfo_children():
            if hasattr(child, '_is_dup_panel'):
                child.destroy()
                break

        near_dups = [d for d in report.dup_file_pairs if d.is_near_duplicate]
        all_dups  = report.dup_file_pairs

        dup_frame = ctk.CTkFrame(self._boot_verdict_frame.master,
                                  fg_color=BG_CARD,
                                  border_color=NEON_PINK, border_width=1,
                                  corner_radius=6)
        dup_frame._is_dup_panel = True
        dup_frame.pack(fill="x", padx=8, pady=(4, 8))

        # Header row
        hdr = ctk.CTkFrame(dup_frame, fg_color=BG_HEADER)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr,
                     text=f"  DUPLICATE CC FILES  —  {len(near_dups)} near-exact  |  "
                          f"{len(all_dups) - len(near_dups)} minor overlaps",
                     font=("Courier New", 10, "bold"),
                     text_color=NEON_PINK).pack(side="left", padx=8, pady=6)
        NeonButton(hdr, "QUARANTINE NEAR-EXACT",
                   command=lambda r=report: self._quarantine_near_dups(r),
                   color=NEON_PINK, height=30, width=210).pack(
                       side="right", padx=8, pady=4)

        ctk.CTkLabel(dup_frame,
                     text="  Two files share the same resource IDs = same CC installed twice."
                          "  The REMOVE column = older/smaller file to quarantine.",
                     font=FONT_SMALL, text_color=TEXT_DIM).pack(
                         anchor="w", padx=8, pady=(4, 0))

        # Column headers
        col_hdr = ctk.CTkFrame(dup_frame, fg_color="#0d0d22")
        col_hdr.pack(fill="x", padx=4, pady=(4, 0))
        for col_text, col_w in [
            ("#",         4), ("Shared", 8), ("Type",    16),
            ("KEEP",     30), ("REMOVE", 30),
        ]:
            ctk.CTkLabel(col_hdr, text=col_text,
                         font=("Courier New", 8, "bold"),
                         text_color=TEXT_DIM,
                         width=col_w * 7, anchor="w").pack(side="left", padx=4, pady=2)

        # Scrollable list (show top 40)
        scroll = ctk.CTkScrollableFrame(dup_frame, fg_color=BG_DEEP,
                                        height=220,
                                        scrollbar_button_color="#2a001a")
        scroll.pack(fill="x", padx=4, pady=(0, 8))

        display = (near_dups[:40] if near_dups
                   else [d for d in all_dups if not d.is_near_duplicate][:40])

        for rank, dup in enumerate(display, 1):
            row = ctk.CTkFrame(scroll, fg_color=BG_CARD if rank % 2 == 0 else "transparent",
                               corner_radius=2)
            row.pack(fill="x", padx=2, pady=1)

            name_color = NEON_RED if dup.is_near_duplicate else NEON_AMBER
            keep_name   = dup.name_a if dup.remove_path == dup.file_b else dup.name_b
            remove_name = Path(dup.remove_path).name

            ctk.CTkLabel(row, text=str(rank),
                         font=FONT_SMALL, text_color=TEXT_DIM,
                         width=28).pack(side="left", padx=4, pady=3)
            ctk.CTkLabel(row, text=f"{dup.shared_ids:,}",
                         font=("Courier New", 9, "bold"),
                         text_color=name_color,
                         width=56).pack(side="left")
            ctk.CTkLabel(row, text=dup.dominant_type[:16],
                         font=FONT_SMALL, text_color=TEXT_DIM,
                         width=112).pack(side="left")
            ctk.CTkLabel(row, text=keep_name[:36],
                         font=FONT_SMALL, text_color=NEON_GREEN,
                         anchor="w").pack(side="left", padx=4, fill="x", expand=True)
            ctk.CTkLabel(row, text=f"⛔ {remove_name[:36]}",
                         font=FONT_SMALL, text_color=NEON_RED,
                         anchor="w").pack(side="left", padx=4)

        if len(all_dups) > 40:
            ctk.CTkLabel(dup_frame,
                         text=f"  ... and {len(all_dups)-40} more pairs. Open HTML report for full list.",
                         font=FONT_SMALL, text_color=TEXT_DIM).pack(
                             anchor="w", padx=8, pady=(0, 4))

    def _quarantine_near_dups(self, report):
        """Quarantine the 'remove_path' file from every near-exact duplicate pair."""
        if not self.qm:
            messagebox.showwarning("No Folder", "Select a Sims 4 folder first.")
            return
        near_dups = [d for d in report.dup_file_pairs if d.is_near_duplicate]
        if not near_dups:
            messagebox.showinfo("None", "No near-exact duplicates to quarantine.")
            return

        # Deduplicate remove_paths
        to_remove = list({d.remove_path for d in near_dups})
        if not messagebox.askyesno(
                "Quarantine Near-Exact Duplicates",
                f"Safely quarantine {len(to_remove)} duplicate file(s)?\n\n"
                f"These contain the same CC as another file already in your Mods folder.\n"
                f"Files are NEVER deleted — restore any time from Fix & Repair."):
            return

        self._boot_console.append("-" * 50, "dim")
        self._boot_console.append(f"Quarantining {len(to_remove)} near-duplicate files...", "warning")
        moved = 0
        for path_str in to_remove:
            p = Path(path_str)
            if p.exists():
                if self.qm.quarantine(p, "Near-exact duplicate CC — same content as another package",
                                       auto=True):
                    moved += 1
                    self._boot_console.append(f"  ⛔ {p.name}", "warning")
            else:
                self._boot_console.append(f"  (not found) {p.name}", "dim")

        self._clear_cache_silent()
        self._boot_console.append(
            f"Done. {moved} files quarantined. Caches cleared.", "ok")
        self._status(f"* {moved} duplicate CC files quarantined")
        messagebox.showinfo("Done",
            f"{moved} of {len(to_remove)} duplicate files quarantined.\n"
            "Caches cleared. You can launch the game now.")

    def _open_last_report(self):
        """Open the most recent HTML audit report in the default browser."""
        import os
        path = getattr(self, '_last_report_path', None)
        if not path:
            logger = RunLogger()
            path = logger.open_latest()
        if path and path.exists():
            try:
                os.startfile(str(path))
                self._status(f"* Opened report: {path.name}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open report:\n{e}")
        else:
            # No log yet — show the logs folder location
            logger = RunLogger()
            logs = logger.list_logs()
            if logs:
                import subprocess
                subprocess.Popen(["explorer", str(logger.log_dir)])
            else:
                messagebox.showinfo("No Reports Yet",
                    "No audit reports saved yet.\n"
                    "Run a Boot Simulation to generate the first report.")

    def _boot_quarantine_critical(self):
        if not self._boot_report or not self.qm:
            return
        critical_files = list({i.file.split("::")[0]
                                for i in self._boot_report.all_issues
                                if i.severity == "CRITICAL" and
                                   (i.file.endswith(".ts4script") or
                                    i.file.endswith(".package"))})
        if not critical_files:
            messagebox.showinfo("None", "No quarantinable files found in critical issues.")
            return
        moved = 0
        for fname in critical_files:
            p = Path(fname) if Path(fname).exists() else None
            if not p:
                for f in (self.mods_folder or Path()).rglob(fname):
                    p = f; break
            if p and p.exists():
                if self.qm.quarantine(p, "Flagged by boot simulator", auto=True):
                    moved += 1
        messagebox.showinfo("Done", f"{moved} files quarantined from boot simulation.")

    # ═══════════════════════════════════════════════════════════════════════════
    # ── SAVE DOCTOR TAB ────────────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_savedoctor_tab(self, parent):
        """Save file analyzer and repair tool."""
        self._save_report  = None
        self._save_analyzer: SaveAnalyzer | None = None
        self._save_selected: Path | None = None

        # -- Save picker row --
        pick_row = ctk.CTkFrame(parent, fg_color="transparent")
        pick_row.pack(fill="x", pady=(0, 8))
        pick_row.columnconfigure(1, weight=1)

        ctk.CTkLabel(pick_row, text="SAVE FILE:",
                     font=FONT_LABEL, text_color=NEON_CYAN).grid(
            row=0, column=0, padx=(0, 8), sticky="w")
        self._save_path_var = tk.StringVar(value="No save selected")
        ctk.CTkEntry(pick_row, textvariable=self._save_path_var,
                     font=FONT_MONO_S, fg_color=BG_CARD,
                     border_color=NEON_CYAN, border_width=1,
                     text_color=NEON_GREEN).grid(row=0, column=1, sticky="ew", padx=(0, 8))
        NeonButton(pick_row, "BROWSE", command=self._browse_save,
                   color=NEON_CYAN, width=90).grid(row=0, column=2, padx=(0, 4))
        NeonButton(pick_row, "AUTO LIST", command=self._list_saves,
                   color=NEON_AMBER, width=100).grid(row=0, column=3)

        # -- Save list dropdown frame --
        self._save_list_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._save_list_frame.pack(fill="x", pady=(0, 4))

        # -- Action buttons --
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 8))
        NeonButton(btn_row, "[SAV] ANALYZE SAVE",
                   command=self._run_save_analyze,
                   color=NEON_PURPLE, height=44, width=200).pack(side="left", padx=4)
        self._clean_save_btn = NeonButton(btn_row, ">> GENERATE CLEAN SAVE",
                                           command=self._run_save_clean,
                                           color=NEON_GREEN, height=44, width=220)
        self._clean_save_btn.pack(side="left", padx=4)
        self._clean_save_btn.configure(state="disabled")

        # -- Save stats --
        sv_stats = ctk.CTkFrame(parent, fg_color="transparent")
        sv_stats.pack(fill="x", pady=(0, 8))
        for i in range(5): sv_stats.columnconfigure(i, weight=1)
        self._sv_total    = StatCard(sv_stats, "TOTAL RES",    color=NEON_CYAN)
        self._sv_known    = StatCard(sv_stats, "KNOWN RES",    color=NEON_GREEN)
        self._sv_orphan   = StatCard(sv_stats, "ORPHANED",     color=NEON_RED)
        self._sv_critical = StatCard(sv_stats, "CRITICAL ORF", color=NEON_RED)
        self._sv_warning  = StatCard(sv_stats, "WARNING ORF",  color=NEON_AMBER)
        for i, c in enumerate([self._sv_total, self._sv_known, self._sv_orphan,
                                self._sv_critical, self._sv_warning]):
            c.grid(row=0, column=i, padx=4, sticky="nsew")

        # -- Results split: console + orphan table --
        split = ctk.CTkFrame(parent, fg_color="transparent")
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=2)
        split.columnconfigure(1, weight=3)

        # Console
        console_frame = neon_frame(split, color="#1a0033")
        console_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        ctk.CTkLabel(console_frame, text="SAVE ANALYSIS LOG",
                     font=("Courier New", 10, "bold"),
                     text_color=NEON_PURPLE).pack(pady=(8, 4), anchor="w", padx=8)
        self._save_console = ConsoleText(console_frame)
        sb = ctk.CTkScrollbar(console_frame, command=self._save_console.yview,
                               button_color="#1a0033")
        sb.pack(side="right", fill="y")
        self._save_console.configure(yscrollcommand=sb.set)
        self._save_console.pack(fill="both", expand=True, padx=4, pady=4)
        self._save_console.append("Select a save file and click ANALYZE SAVE.", "dim")
        self._save_console.append("", "dim")
        self._save_console.append("WARNING: Save cleaning is lossy. Sims may lose custom", "warning")
        self._save_console.append("traits, careers, or appearances from removed mods.", "warning")
        self._save_console.append("Original is always backed up before cleaning.", "dim")

        # Orphan table
        orphan_frame = neon_frame(split, color="#2a001a")
        orphan_frame.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(orphan_frame, text="ORPHANED REFERENCES",
                     font=("Courier New", 10, "bold"),
                     text_color=NEON_RED).pack(pady=(8, 4), anchor="w", padx=8)
        orphan_scroll = ctk.CTkScrollableFrame(orphan_frame, fg_color=BG_DEEP,
                                               scrollbar_button_color="#2a001a")
        orphan_scroll.pack(fill="both", expand=True, padx=4, pady=4)
        self._orphan_scroll = orphan_scroll
        ctk.CTkLabel(orphan_scroll,
                     text="No analysis run yet.",
                     font=FONT_LABEL, text_color=TEXT_DIM).pack(pady=40)

    def _list_saves(self):
        if not self.s4_folder:
            messagebox.showwarning("No Folder", "Select a Sims 4 folder first.")
            return
        sa = SaveAnalyzer(self.s4_folder)
        saves = sa.list_saves()
        if not saves:
            messagebox.showinfo("No Saves", "No .save files found.")
            return

        for w in self._save_list_frame.winfo_children():
            w.destroy()

        ctk.CTkLabel(self._save_list_frame, text="Select a save:",
                     font=FONT_SMALL, text_color=TEXT_DIM).pack(side="left", padx=4)
        for s in saves[:8]:
            size_mb = s.stat().st_size / (1024 * 1024)
            label = f"{s.name}  ({size_mb:.0f} MB)"
            NeonButton(self._save_list_frame, label,
                       command=lambda p=s: self._select_save(p),
                       color=NEON_PURPLE, height=28).pack(side="left", padx=2)

    def _browse_save(self):
        if not self.s4_folder:
            messagebox.showwarning("No Folder", "Select a Sims 4 folder first.")
            return
        path = filedialog.askopenfilename(
            title="Select a Sims 4 save file",
            filetypes=[("Sims 4 Save", "*.save"), ("All", "*.*")],
            initialdir=str(self.s4_folder / "saves"),
        )
        if path:
            self._select_save(Path(path))

    def _select_save(self, path: Path):
        self._save_selected = path
        self._save_path_var.set(str(path))
        self._save_console.clear()
        self._save_console.append(f"Selected: {path.name}", "info")
        self._save_console.append(f"Size: {path.stat().st_size / 1024 / 1024:.1f} MB", "dim")
        self._clean_save_btn.configure(state="disabled")
        self._save_report = None

    def _run_save_analyze(self):
        if not self._save_selected:
            messagebox.showwarning("No Save", "Select a save file first.")
            return
        if not self.s4_folder:
            messagebox.showwarning("No Folder", "Select a Sims 4 folder first.")
            return

        game_root = Path(self._inv_root_var.get()) if hasattr(self, '_inv_root_var') else DEFAULT_GAME_ROOT
        self._save_console.clear()
        self._save_console.append(f"Analyzing {self._save_selected.name} ...", "header")
        self._clean_save_btn.configure(state="disabled")
        for w in self._orphan_scroll.winfo_children(): w.destroy()

        idx = self._game_index_cached or GameIndex(game_root)
        sa  = SaveAnalyzer(self.s4_folder, game_root, game_index=idx)
        self._save_analyzer = sa
        save_path = self._save_selected

        def worker():
            def log(m):
                self._q.put({"action": "save_log", "text": m, "tag": "info"})
            report = sa.analyze(save_path, progress_cb=log)
            self._game_index_cached = idx
            self._q.put({"action": "save_done", "report": report})

        threading.Thread(target=worker, daemon=True).start()

    def _on_save_analyzed(self, report):
        self._save_report = report

        self._sv_total.set(f"{report.total_resources:,}")
        self._sv_known.set(f"{report.known_resources:,}")
        self._sv_orphan.set(str(report.orphaned_resources))
        self._sv_critical.set(str(report.critical_orphans))
        self._sv_warning.set(str(report.warning_orphans))

        # Populate orphan table
        for w in self._orphan_scroll.winfo_children():
            w.destroy()

        if report.is_clean:
            ctk.CTkLabel(self._orphan_scroll,
                         text="SAVE IS CLEAN — no orphaned references found!",
                         font=FONT_HEAD, text_color=NEON_GREEN).pack(pady=30)
            self._save_console.append("CLEAN: No orphaned references found.", "ok")
        else:
            # Group by type
            for type_label, count in sorted(report.orphan_by_type.items(),
                                             key=lambda x: -x[1]):
                grp_color = NEON_RED if any(
                    o.severity == "CRITICAL" for o in report.orphans
                    if o.resource.type_label == type_label) else NEON_AMBER

                grp = ctk.CTkFrame(self._orphan_scroll, fg_color=BG_CARD, corner_radius=4)
                grp.pack(fill="x", padx=4, pady=2)
                ctk.CTkLabel(grp,
                             text=f"{type_label}  ×{count}",
                             font=("Courier New", 9, "bold"),
                             text_color=grp_color).pack(anchor="w", padx=8, pady=(4, 0))
                # Show first matching orphan's impact
                for o in report.orphans:
                    if o.resource.type_label == type_label:
                        ctk.CTkLabel(grp,
                                     text=o.impact[:80],
                                     font=("Courier New", 8),
                                     text_color=TEXT_DIM).pack(anchor="w", padx=8, pady=(0, 4))
                        break

            self._save_console.append(
                f"Found {report.orphaned_resources} orphaned references:", "warning")
            for label, count in report.orphan_by_type.items():
                self._save_console.append(f"  {label}: {count}", "warning")
            self._save_console.append("", "dim")
            self._save_console.append("Click GENERATE CLEAN SAVE to repair.", "ok")
            self._clean_save_btn.configure(state="normal")

        self._status(f"* Save analysis done — {report.orphaned_resources} orphaned refs")

    def _run_save_clean(self):
        if not self._save_report or not self._save_analyzer:
            return
        if not messagebox.askyesno(
                "Generate Clean Save",
                f"Remove {self._save_report.orphaned_resources} orphaned references?\n"
                f"Original will be backed up to .save.bak"):
            return

        self._save_console.append("-" * 50, "dim")
        self._save_console.append("Generating clean save...", "header")
        report = self._save_report
        sa     = self._save_analyzer

        def worker():
            def log(m):
                self._q.put({"action": "save_log", "text": m, "tag": "info"})
            try:
                out_path = sa.generate_clean_save(report, progress_cb=log)
                self._q.put({"action": "save_cleaned",
                              "ok": True,
                              "path": str(out_path),
                              "removed": report.resources_removed})
            except Exception as e:
                self._q.put({"action": "save_cleaned", "ok": False, "error": str(e)})

        threading.Thread(target=worker, daemon=True).start()

    def _on_save_cleaned(self, msg):
        if msg.get("ok"):
            out = msg.get("path", "")
            removed = msg.get("removed", 0)
            self._save_console.append(
                f"CLEAN SAVE WRITTEN: {Path(out).name}", "ok")
            self._save_console.append(
                f"  {removed} orphaned entries removed.", "ok")
            self._save_console.append(
                f"  Original backed up to: {self._save_selected.name}.bak", "dim")
            messagebox.showinfo("Success",
                f"Clean save written!\n{Path(out).name}\n"
                f"{removed} entries removed.")
        else:
            err = msg.get("error", "Unknown error")
            self._save_console.append(f"CLEAN FAILED: {err}", "critical")
            messagebox.showerror("Error", f"Failed to generate clean save:\n{err}")


def main():
    app = Sims4ModGuardApp()
    app.mainloop()


if __name__ == "__main__":
    main()
