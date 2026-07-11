"""
Sims4ModGuard -- GUI
Cyberpunk Hacker Console for Sims 4 Mod Management

By Hucifer & Hypatia
"""

import sys
import threading
import queue
import time
import random
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
            hover_color=color + "22",
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
        tab_btn_col = ctk.CTkFrame(tab_bar, fg_color=BG_HEADER, width=190)
        tab_btn_col.pack(side="left", fill="y", padx=(0, 1))
        tab_btn_col.pack_propagate(False)

        self._tab_content = ctk.CTkFrame(tab_bar, fg_color=BG_PANEL)
        self._tab_content.pack(side="left", fill="both", expand=True)

        self._tab_frames = {}
        self._tab_btns   = {}

        tabs = [
            ("[>>]  SCAN SCRIPTS",  "scan",    self._build_scan_tab),
            ("[##]  CC CLEANER",    "cc",      self._build_cc_tab),
            ("[!!]  LOG ANALYZER",  "logs",    self._build_logs_tab),
            ("[WR]  FIX & REPAIR",  "fix",     self._build_fix_tab),
            ("[>_]  CONSOLE",       "console", self._build_console_tab),
            ("[??]   ABOUT",         "about",   self._build_about_tab),
        ]

        ctk.CTkLabel(tab_btn_col, text="* NAVIGATION *",
                     font=FONT_SMALL, text_color="#00805a").pack(pady=(12, 6))

        for label, key, builder in tabs:
            frame = ctk.CTkFrame(self._tab_content, fg_color=BG_PANEL)
            builder(frame)
            self._tab_frames[key] = frame

            btn = ctk.CTkButton(
                tab_btn_col, text=label, font=("Courier New", 10, "bold"),
                fg_color=BG_HEADER, border_width=0,
                text_color=TEXT_DIM, hover_color="#001a10",
                anchor="w", corner_radius=0,
                command=lambda k=key: self._switch_tab(k),
            )
            btn.pack(fill="x", padx=4, pady=2)
            self._tab_btns[key] = btn

        # Show scan tab first
        self._switch_tab("scan")

    def _switch_tab(self, key: str):
        for k, f in self._tab_frames.items():
            f.pack_forget()
        for k, b in self._tab_btns.items():
            b.configure(text_color=TEXT_DIM, fg_color=BG_HEADER)

        self._tab_frames[key].pack(fill="both", expand=True, padx=8, pady=8)
        self._tab_btns[key].configure(
            text_color=NEON_GREEN,
            fg_color=BG_CARD,
        )

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
                elif action == "done_cc":
                    self._finish_cc(msg["data"])
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


def main():
    app = Sims4ModGuardApp()
    app.mainloop()


if __name__ == "__main__":
    main()
