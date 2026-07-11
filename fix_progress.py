"""
1. Wire real progress_callback into CC scanner worker thread
2. Fix remaining mojibake: box-drawing ─ (U+2500) and diamond ◈ (U+25C8)
All edits in binary mode to preserve CRLF.
"""

with open(r'C:\Users\merli\Sims4ModGuard\gui_app.py', 'rb') as f:
    raw = f.read()

print(f"Original: {len(raw)} bytes")

# ── 1. Replace the fake CC worker with a real progress-reporting one ──────────
# Old worker:
#   def worker():
#       self._status("◈ SCANNING CC PACKAGES...")   <- ◈ is mojibake C3A2 E28094 CB86
#       data = scan_all_packages(self.mods_folder)
#       self._q.put({"action": "done_cc", "data": data})
#
# Note: ◈ mojibake bytes = b'\xc3\xa2\xe2\x80\x94\xcb\x86'

OLD_WORKER = (
    b'        def worker():\r\n'
    b'            self._status(\"\xc3\xa2\xe2\x80\x94\xcb\x86 SCANNING CC PACKAGES...\")\r\n'
    b'            data = scan_all_packages(self.mods_folder)\r\n'
    b'            self._q.put({\"action\": \"done_cc\", \"data\": data})'
)

NEW_WORKER = (
    b'        def worker():\r\n'
    b'            self._status(\">> SCANNING CC PACKAGES...\")\r\n'
    b'            def _progress_cb(current, total):\r\n'
    b'                val = current / total if total > 0 else 0\r\n'
    b'                self._q.put({\"action\": \"progress\", \"bar\": \"cc\", \"val\": val})\r\n'
    b'                self._q.put({\"action\": \"status\",\r\n'
    b'                             \"text\": f\">> CC SCAN: {current:,} / {total:,} packages\"})\r\n'
    b'            data = scan_all_packages(self.mods_folder, progress_callback=_progress_cb)\r\n'
    b'            self._q.put({\"action\": \"done_cc\", \"data\": data})'
)

if OLD_WORKER in raw:
    raw = raw.replace(OLD_WORKER, NEW_WORKER)
    print("  Replaced CC worker with real progress callback")
else:
    print("  WARNING: CC worker pattern not found - may already be updated")
    # Try LF-only variant
    OLD_LF = OLD_WORKER.replace(b'\r\n', b'\n')
    NEW_LF = NEW_WORKER.replace(b'\r\n', b'\n')
    if OLD_LF in raw:
        raw = raw.replace(OLD_LF, NEW_LF)
        print("  Replaced CC worker (LF variant)")

# ── 2. Remove the _fake_progress("cc") call after threading.Thread start ──────
FAKE = b'        self._fake_progress(\"cc\")\r\n'
if FAKE in raw:
    raw = raw.replace(FAKE, b'')
    print("  Removed _fake_progress(cc) call")
else:
    FAKE_LF = b'        self._fake_progress(\"cc\")\n'
    if FAKE_LF in raw:
        raw = raw.replace(FAKE_LF, b'')
        print("  Removed _fake_progress(cc) call (LF)")

# ── 3. Fix remaining mojibake ─────────────────────────────────────────────────

# ─ (U+2500 BOX DRAWINGS LIGHT HORIZONTAL) mojibake
# UTF-8 E2 94 80 → CP1252 → â " € → UTF-8 C3A2 E2809D E282AC
BOX_HORIZ = b'\xc3\xa2\xe2\x80\x9d\xe2\x82\xac'
n = raw.count(BOX_HORIZ)
if n:
    raw = raw.replace(BOX_HORIZ, b'-')
    print(f"  Replaced {n}x box-drawing \u2500 -> -")

# ◈ (U+25C8 WHITE DIAMOND CONTAINING BLACK SMALL DIAMOND) mojibake
# UTF-8 E2 97 88 → CP1252 → â — ˆ → UTF-8 C3A2 E28094 CB86
DIAMOND = b'\xc3\xa2\xe2\x80\x94\xcb\x86'
n = raw.count(DIAMOND)
if n:
    raw = raw.replace(DIAMOND, b'*')
    print(f"  Replaced {n}x diamond \u25c8 -> *")

# ◆ (U+25C6 BLACK DIAMOND) mojibake  
# UTF-8 E2 97 86 → CP1252 → â — † → UTF-8 C3A2 E28094 E280A0
BLACK_DIAMOND = b'\xc3\xa2\xe2\x80\x94\xe2\x80\xa0'
n = raw.count(BLACK_DIAMOND)
if n:
    raw = raw.replace(BLACK_DIAMOND, b'<>')
    print(f"  Replaced {n}x black diamond \u25c6 -> <>")

# ⚠ (U+26A0 WARNING SIGN) - any remaining
WARN = b'\xc3\xa2\xe2\x9a\xa0'
n = raw.count(WARN)
if n:
    raw = raw.replace(WARN, b'[!]')
    print(f"  Replaced {n}x warning sign -> [!]")

# → arrow remaining (U+2192)
ARROW = b'\xc3\xa2\xe2\x86\x92'
n = raw.count(ARROW)
if n:
    raw = raw.replace(ARROW, b'->')
    print(f"  Replaced {n}x arrow -> ->")

with open(r'C:\Users\merli\Sims4ModGuard\gui_app.py', 'wb') as f:
    f.write(raw)

print(f"\nFinal: {len(raw)} bytes, {raw.count(b'chr(10)')} lines")
print("Done!")
