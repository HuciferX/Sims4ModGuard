"""Fix emoji rendering and dead space issues in gui_app.py"""
import re

with open(r'C:\Users\merli\Sims4ModGuard\gui_app.py', 'r', encoding='utf-8-sig') as f:
    content = f.read()

original_len = len(content)

# --- Fix tab labels (the sidebar nav buttons) ---
content = content.replace(
    '("🔍  SCAN SCRIPTS",  "scan",    self._build_scan_tab)',
    '("[>>] SCAN SCRIPTS", "scan",    self._build_scan_tab)'
)
content = content.replace(
    '("📦  CC CLEANER",    "cc",      self._build_cc_tab)',
    '("[##] CC CLEANER",   "cc",      self._build_cc_tab)'
)
content = content.replace(
    '("📋  LOG ANALYZER",  "logs",    self._build_logs_tab)',
    '("[!!] LOG ANALYZER", "logs",    self._build_logs_tab)'
)
content = content.replace(
    '("🔧  FIX & REPAIR",  "fix",     self._build_fix_tab)',
    '("[WR] FIX & REPAIR", "fix",     self._build_fix_tab)'
)
content = content.replace(
    '("💻  CONSOLE",       "console", self._build_console_tab)',
    '("[>_] CONSOLE",      "console", self._build_console_tab)'
)
content = content.replace(
    '("ℹ️   ABOUT",         "about",   self._build_about_tab)',
    '("[??] ABOUT",         "about",   self._build_about_tab)'
)

# --- Fix header plumbob emoji ---
content = content.replace(
    'text="🔷",\n                     font=("Courier New", 28),',
    'text="◆",\n                     font=("Courier New", 28),'
)

# --- Fix header branding (remove owl emoji) ---
content = content.replace(
    '"by  Hucifer  &  🦉Hypatia"',
    '"by  Hucifer  &  Hypatia"'
)

# --- Fix folder label emoji ---
content = content.replace(
    'text="📂 SIMS4 FOLDER:"',
    'text=">> SIMS4 FOLDER:"'
)

# --- Fix scan tab action buttons ---
content = content.replace('"⚡ SCAN SCRIPTS"', '">> SCAN SCRIPTS"')
content = content.replace('"🗑  QUARANTINE ALL CRITICAL"', '"XX QUARANTINE ALL CRITICAL"')
content = content.replace('"♻ CLEAR CACHE"', '"~~ CLEAR CACHE"')

# --- Fix CC tab ---
content = content.replace('"📦 SCAN CC PACKAGES"', '"## SCAN CC PACKAGES"')

# --- Fix Log tab ---
content = content.replace('"📋 PARSE LAST EXCEPTION LOG"', '"!! PARSE LAST EXCEPTION LOG"')

# --- Fix & Repair tab header ---
content = content.replace(
    'text="⚡ REPAIR CONSOLE ⚡"',
    'text=">> REPAIR CONSOLE <<"'
)

# --- Fix & Repair tab action buttons ---
content = content.replace('"🔴 QUARANTINE ALL CRITICAL SCRIPTS"', '"[!!] QUARANTINE ALL CRITICAL"')
content = content.replace('"♻  CLEAR ALL CACHES"',               '"[~~] CLEAR ALL CACHES"')
content = content.replace('"🟢 RESTORE ALL QUARANTINED"',         '"[OK] RESTORE ALL QUARANTINED"')
content = content.replace('"📂 OPEN MODS FOLDER"',                '"[->] OPEN MODS FOLDER"')
content = content.replace('"🗑  REMOVE DUPLICATE PACKAGES"',      '"[XX] REMOVE DUPLICATE PACKAGES"')
content = content.replace('"📋 SHOW QUARANTINE MANIFEST"',        '"[??] SHOW QUARANTINE MANIFEST"')

# --- Fix Console tab header ---
content = content.replace('"▶ LIVE OUTPUT CONSOLE"', '">> LIVE OUTPUT CONSOLE"')

# --- Fix About tab ---
content = content.replace(
    '"🔷  SIMS4 MOD GUARDIAN  🔷"',
    '"◆  SIMS4 MOD GUARDIAN  ◆"'
)
content = content.replace(
    '"◈  Crafted by  ◈\\n\\nHucifer  &  🦉Hypatia"',
    '"◈  Crafted by  ◈\\n\\nHucifer  &  Hypatia"'
)

# --- Fix About tab bullet points ---
content = content.replace('  🔴  Scans .ts4script', '  [!!] Scans .ts4script')
content = content.replace('  🔴  Detects APIs',     '  [!!] Detects APIs')
content = content.replace('  🟡  Finds WickedWhims', '  [~~] Finds WickedWhims')
content = content.replace('  🟡  Validates every',   '  [~~] Validates every')
content = content.replace('  🟡  Finds duplicate',   '  [~~] Finds duplicate')
content = content.replace('  🔵  Parses lastException', '  [>>] Parses lastException')
content = content.replace('  🟢  Safe quarantine',   '  [OK] Safe quarantine')
content = content.replace('  🟢  One-click cache',   '  [OK] One-click cache')
content = content.replace('  ✗  Fix compiled',       '  [XX] Fix compiled')
content = content.replace('  ✗  Restore saves',      '  [XX] Restore saves')
content = content.replace('  ✗  Auto-update every',  '  [XX] Auto-update every')
content = content.replace('  ✗  Replace mods',       '  [XX] Replace mods')

# --- Fix boot sequence ---
content = content.replace(
    '"by Hucifer & 🦉Hypatia — Community Edition"',
    '"by Hucifer & Hypatia -- Community Edition"'
)

# --- Fix em dash (broken — character) in StatCard default ---
content = content.replace('value: str = "\u2014"', 'value: str = "--"')
# Also catch any literal em dash
content = content.replace('value: str = "—"', 'value: str = "--"')

# --- Fix dead space: remove rowconfigure(1, weight=1) from _build_ui ---
# This was causing stats row to expand, creating huge gaps
content = content.replace(
    '        content.columnconfigure(0, weight=1)\n        content.rowconfigure(1, weight=1)',
    '        content.columnconfigure(0, weight=1)'
)

# --- Fix the arrow in log parser display ---
content = content.replace('"    → {err.explanation}"', '"    -> {err.explanation}"')

print(f"Original: {original_len} chars")
print(f"Fixed:    {len(content)} chars")

with open(r'C:\Users\merli\Sims4ModGuard\gui_app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("All fixes applied successfully!")
