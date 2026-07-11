"""Inject the LAUNCHER tab into gui_app.py in binary-safe mode."""
from pathlib import Path

gui = Path(r'C:\Users\merli\Sims4ModGuard\gui_app.py')
raw = gui.read_bytes()

# ── 1. Add launcher to tabs list (insert before [??] ABOUT) ─────────────────
old_tabs = b'            (\"[??] ABOUT\",         \"about\",   self._build_about_tab),'
new_tabs = (
    b'            (\"[>G] LAUNCHER\",    \"launcher\", self._build_launcher_tab),\r\n'
    b'            (\"[??] ABOUT\",         \"about\",   self._build_about_tab),'
)
if old_tabs in raw:
    raw = raw.replace(old_tabs, new_tabs)
    print("Added LAUNCHER to tabs list")
else:
    print("WARNING: tabs list pattern not found")

# ── 2. Add imports at top (after existing imports) ───────────────────────────
old_imports = b'from sims4modguard.quarantine     import QuarantineManager'
new_imports = (
    b'from sims4modguard.quarantine     import QuarantineManager\r\n'
    b'import subprocess\r\n'
    b'import re\r\n'
    b'import os'
)
if old_imports in raw and b'import subprocess' not in raw:
    raw = raw.replace(old_imports, new_imports)
    print("Added subprocess/re/os imports")

# ── 3. Inject _build_launcher_tab and monitoring methods before _build_about_tab
LAUNCHER_CODE = b"""
    def _build_launcher_tab(self, parent):
        \"\"\"Game launcher with real-time process and error monitoring.\"\"\"
        self._game_exe = None
        self._game_pid = None
        self._launcher_running = False
        self._log_error_count  = 0
        self._launch_time      = None

        # --- Top: find game exe ---
        exe_row = ctk.CTkFrame(parent, fg_color=\"transparent\")
        exe_row.pack(fill=\"x\", pady=(0, 8))
        exe_row.columnconfigure(1, weight=1)
        ctk.CTkLabel(exe_row, text=\"GAME EXE:\", font=FONT_LABEL,
                     text_color=NEON_CYAN).grid(row=0, column=0, padx=(0, 8), sticky=\"w\")
        self._exe_var = tk.StringVar(value=\"Click FIND to locate TS4_x64.exe\")
        ctk.CTkEntry(exe_row, textvariable=self._exe_var, font=FONT_MONO_S,
                     fg_color=BG_CARD, border_color=NEON_CYAN, border_width=1,
                     text_color=NEON_GREEN).grid(row=0, column=1, sticky=\"ew\", padx=(0, 8))
        NeonButton(exe_row, \"FIND\", self._find_game_exe,
                   color=NEON_CYAN, width=70).grid(row=0, column=2, padx=(0, 8))

        # --- Launch / Kill buttons ---
        btn_row = ctk.CTkFrame(parent, fg_color=\"transparent\")
        btn_row.pack(fill=\"x\", pady=(0, 8))
        self._launch_btn = NeonButton(btn_row, \">> LAUNCH SIMS 4\",
                                      command=self._launch_game,
                                      color=NEON_GREEN, height=52, width=200)
        self._launch_btn.pack(side=\"left\", padx=4)
        self._kill_btn = NeonButton(btn_row, \"XX KILL GAME\",
                                    command=self._kill_game,
                                    color=NEON_RED, height=52, width=150)
        self._kill_btn.pack(side=\"left\", padx=4)

        # --- Status cards ---
        stat_row = ctk.CTkFrame(parent, fg_color=\"transparent\")
        stat_row.pack(fill=\"x\", pady=(0, 8))
        for i in range(4):
            stat_row.columnconfigure(i, weight=1)
        self._game_status_card  = StatCard(stat_row, \"GAME STATUS\",  value=\"OFFLINE\", color=TEXT_DIM)
        self._game_uptime_card  = StatCard(stat_row, \"UPTIME\",       value=\"--\",       color=NEON_CYAN)
        self._game_errors_card  = StatCard(stat_row, \"LOG ERRORS\",   value=\"--\",       color=NEON_AMBER)
        self._game_crash_card   = StatCard(stat_row, \"CRASH DETECT\", value=\"--\",       color=NEON_RED)
        for i, c in enumerate([self._game_status_card, self._game_uptime_card,
                                self._game_errors_card, self._game_crash_card]):
            c.grid(row=0, column=i, padx=4, sticky=\"nsew\")

        # --- Live log output ---
        frame = neon_frame(parent, color=\"#003d26\")
        frame.pack(fill=\"both\", expand=True)
        toolbar = ctk.CTkFrame(frame, fg_color=BG_HEADER)
        toolbar.pack(fill=\"x\")
        ctk.CTkLabel(toolbar, text=\">> LIVE GAME LOG\", font=(\"Courier New\", 10, \"bold\"),
                     text_color=NEON_GREEN).pack(side=\"left\", padx=8, pady=4)
        ctk.CTkLabel(toolbar, text=\"Monitors lastException.txt in real-time\",
                     font=FONT_SMALL, text_color=TEXT_DIM).pack(side=\"left\", padx=4, pady=4)
        self._launcher_log = ConsoleText(frame)
        sb = ctk.CTkScrollbar(frame, command=self._launcher_log.yview, button_color=\"#002d1e\")
        sb.pack(side=\"right\", fill=\"y\")
        self._launcher_log.configure(yscrollcommand=sb.set)
        self._launcher_log.pack(fill=\"both\", expand=True, padx=4, pady=4)
        self._launcher_log.append(\"Launcher ready. Find and launch The Sims 4.\", \"dim\")
        self._launcher_log.append(\"Errors from lastException.txt will appear here in real-time.\", \"dim\")

        # Auto-find game on open
        self.after(200, self._find_game_exe_auto)

    def _find_game_exe_auto(self):
        \"\"\"Auto-detect Sims 4 exe from common locations.\"\"\"
        candidates = [
            Path(r'C:/Program Files/EA Games/The Sims 4/Game/Bin/TS4_x64.exe'),
            Path(r'C:/Program Files (x86)/EA Games/The Sims 4/Game/Bin/TS4_x64.exe'),
            Path(r'D:/EA Games/The Sims 4/Game/Bin/TS4_x64.exe'),
            Path(r'E:/EA Games/The Sims 4/Game/Bin/TS4_x64.exe'),
        ]
        # Also check registry
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\\Maxis\\The Sims 4')
            d = winreg.QueryValueEx(key, 'Install Dir')[0]
            candidates.insert(0, Path(d) / 'Game' / 'Bin' / 'TS4_x64.exe')
        except Exception:
            pass
        for p in candidates:
            if p.exists():
                self._game_exe = p
                self._exe_var.set(str(p))
                self._launcher_log.append(f\"Game found: {p}\", \"ok\")
                return
        self._launcher_log.append(\"Game exe not auto-found. Click FIND to browse.\", \"warning\")

    def _find_game_exe(self):
        path = filedialog.askopenfilename(
            title=\"Select TS4_x64.exe\",
            filetypes=[(\"Sims 4 Executable\", \"TS4_x64.exe\"), (\"All\", \"*.*\")],
            initialdir=\"C:/Program Files\",
        )
        if path:
            self._game_exe = Path(path)
            self._exe_var.set(path)
            self._launcher_log.append(f\"Game set: {path}\", \"ok\")

    def _launch_game(self):
        if not self._game_exe or not self._game_exe.exists():
            self._find_game_exe()
            if not self._game_exe:
                return
        self._launcher_log.clear()
        self._launcher_log.append(\">> Launching The Sims 4...\", \"header\")
        self._launcher_log.append(f\"   {self._game_exe}\", \"dim\")
        try:
            proc = subprocess.Popen([str(self._game_exe)],
                                    cwd=str(self._game_exe.parent))
            self._game_pid    = proc.pid
            self._launch_time = time.time()
            self._launcher_running = True
            self._log_error_count  = 0
            self._last_log_mtime   = 0
            self._last_error_count = 0
            self._game_status_card.set(\"RUNNING\")
            self._game_crash_card.set(\"NONE\")
            self._launcher_log.append(f\"   PID: {proc.pid}\", \"dim\")
            self._launcher_log.append(\"   Monitoring started - errors will appear below\", \"info\")
            # Start monitor thread
            threading.Thread(target=self._monitor_game, args=(proc,), daemon=True).start()
            self._tick_launcher()
        except Exception as e:
            self._launcher_log.append(f\"Launch failed: {e}\", \"critical\")

    def _kill_game(self):
        if self._game_pid:
            try:
                subprocess.run(['taskkill', '/PID', str(self._game_pid), '/F'],
                               capture_output=True)
                self._launcher_log.append(f\"XX Game killed (PID {self._game_pid})\", \"warning\")
                self._game_pid = None
                self._launcher_running = False
                self._game_status_card.set(\"KILLED\")
            except Exception as e:
                self._launcher_log.append(f\"Kill failed: {e}\", \"critical\")

    def _monitor_game(self, proc):
        \"\"\"Background thread: watch process and log file.\"\"\"
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
        \"\"\"Update uptime display every second while game is running.\"\"\"
        if self._launcher_running and self._launch_time:
            elapsed = int(time.time() - self._launch_time)
            m, s = divmod(elapsed, 60)
            self._game_uptime_card.set(f\"{m:02d}:{s:02d}\")
            self.after(1000, self._tick_launcher)
        elif not self._launcher_running:
            self._game_uptime_card.set(\"--\")

"""

OLD_ABOUT = b'    def _build_about_tab(self, parent):'
NEW_ABOUT = LAUNCHER_CODE + b'    def _build_about_tab(self, parent):'

if OLD_ABOUT in raw:
    raw = raw.replace(OLD_ABOUT, NEW_ABOUT)
    print("Injected _build_launcher_tab and monitoring methods")
else:
    print("WARNING: _build_about_tab not found")

# ── 4. Add launcher event handling to _poll_queue ─────────────────────────────
old_poll = b"                elif action == \"done_cc\":"
new_poll = (
    b"                elif action == \"launcher_event\":\r\n"
    b"                    ev = msg.get(\"event\", \"\")\r\n"
    b"                    if ev == \"crashed\":\r\n"
    b"                        self._game_status_card.set(\"CRASHED\")\r\n"
    b"                        self._game_crash_card.set(\"YES\")\r\n"
    b"                        self._launcher_running = False\r\n"
    b"                        if hasattr(self, '_launcher_log'):\r\n"
    b"                            self._launcher_log.append(\"[!!] GAME CRASHED - check log\", \"critical\")\r\n"
    b"                    elif ev == \"errors\":\r\n"
    b"                        c = msg.get(\"count\", 0)\r\n"
    b"                        n = msg.get(\"new\", 0)\r\n"
    b"                        self._game_errors_card.set(str(c))\r\n"
    b"                        if hasattr(self, '_launcher_log') and n > 0:\r\n"
    b"                            self._launcher_log.append(f\"  +{n} new errors (total {c})\", \"warning\")\r\n"
    b"                    elif ev == \"hang\":\r\n"
    b"                        sec = msg.get(\"elapsed\", 0)\r\n"
    b"                        self._game_crash_card.set(\"HANG?\")\r\n"
    b"                        if hasattr(self, '_launcher_log'):\r\n"
    b"                            self._launcher_log.append(f\"[!!] POSSIBLE HANG: {sec}s on loading screen\", \"critical\")\r\n"
    b"                elif action == \"done_cc\":"
)
if old_poll in raw:
    raw = raw.replace(old_poll, new_poll)
    print("Added launcher event handling to _poll_queue")
else:
    print("WARNING: poll_queue pattern not found")

# Write
gui.write_bytes(raw)
print(f"\nDone. File: {len(raw)} bytes")
