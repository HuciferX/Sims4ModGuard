# 🦉 Sims4ModGuard
> **31 / 31 tests passing** &nbsp;|&nbsp; Python 3.10+ &nbsp;|&nbsp; Windows &nbsp;|&nbsp; Patch 1.121+

> **The ultimate Sims 4 mod compatibility scanner, CC cleaner, and repair tool.**  
> Built by **Hucifer** & **🦉 Hypatia** — cyberpunk-style, hacker-grade, community-free.

![Platform](https://img.shields.io/badge/Platform-Windows-blue?style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10%2B-brightgreen?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-purple?style=flat-square)
![Game](https://img.shields.io/badge/Sims%204-Patch%201.121%2B-ff69b4?style=flat-square)

---

## 🚨 What Is This?

Every Sims 4 patch breaks mods. The community spends hours hunting broken scripts, corrupt CC packages, and injection-pattern crashes. **Sims4ModGuard** automates all of that.

It's a full **cyberpunk hacker dashboard** that:
- Scans every `.ts4script` ZIP for broken injection patterns
- Detects outdated mods that crash on Patch 1.121+
- Validates CC packages (`.package`) for DBPF corruption
- Finds duplicates, tiny-file junk, and tuning conflicts
- Parses your `lastException.txt` into plain English
- Quarantines broken files safely (with one-click restore)
- Clears game caches automatically

---

## ✨ Features

| Feature | Description |
|--------|-------------|
| 🔍 **Script Scanner** | Detects `inject_load_data_into_class_instances`, `HasTunableReference`, `add_super_affordances`, `lmsinjector`, and 10+ other broken patterns |
| 🧹 **CC Cleaner** | Validates DBPF headers, finds duplicates by name and MD5 hash, flags corrupt or empty packages |
| 📋 **Log Analyzer** | Parses `lastException.txt` XML into grouped, human-readable errors with mod name attribution |
| 🔧 **Fix & Repair** | One-click quarantine of bad files with a JSON restore manifest |
| 🗑️ **Cache Cleaner** | Auto-detects your Sims 4 folder and clears localthumbcache and script/slot caches |
| 🛡️ **Smart Whitelist** | Known-good mods (MCCC, Basemental, BetterExceptions, XmlInjector) are never flagged |
| 🚀 **Auto-Update URLs** | Embedded links to official update pages for top community mods |

---

## 📖 How It Works — Step by Step

### Step 1 — Open the App
Double-click `Sims4ModGuard.exe`. The app opens in a cyberpunk dashboard interface and **auto-detects your Sims 4 folder** (usually `Documents/Electronic Arts/The Sims 4`). You'll see your stats load instantly at the top:
- **GAME VERSION** — what patch you're on
- **SCRIPTS** — how many .ts4script mods you have
- **PACKAGES** — how many .package CC files
- **QUARANTINED** — files you've previously disabled
- **ISSUES FOUND** — updates live after each scan

If the folder isn't detected, click **BROWSE** to point it at your Sims 4 data folder.

---

### Step 2 — Scan Your Script Mods (`[>>] SCAN SCRIPTS` tab)

Click **>> SCAN SCRIPTS**. The scanner reads every `.ts4script` file in your Mods folder and looks inside the ZIP for broken Python patterns.

It catches:
| Pattern | What it means |
|---------|---------------|
| `inject_load_data_into_class_instances` | EA removed this API. Mod crashes on launch. |
| `HasTunableReference` | Tunable reference system changed. Mod is dead. |
| `add_super_affordances` | Affordance injection removed. Mod broken. |
| `lmsinjector` | Scumbumbo's injector, no longer compatible. |
| `add_wicked_attributes` | Mod depends on WickedWhims (not installed). |
| `leroi_death_injector` | LeRoi death system removed by EA. |

Results appear color-coded:
- 🔴 **CRITICAL** — this mod WILL crash your game, quarantine it
- 🟡 **WARNING** — likely broken, needs attention
- 🟢 **OK** — clean, no issues found

Known-good mods (MCCC, Basemental, BetterExceptions, XmlInjector) are **whitelisted** and never flagged.

---

### Step 3 — Quarantine Broken Scripts

After scanning, click **XX QUARANTINE ALL CRITICAL**. This **safely moves** every critical script from your Mods folder to a `MODS_DISABLED` folder. A JSON manifest records every move so you can restore files later.

> Your files are NEVER deleted — only moved. You can restore them any time from the `[WR] FIX & REPAIR` tab.

---

### Step 4 — Scan CC Packages (`[##] CC CLEANER` tab)

Click **## SCAN CC PACKAGES**. This inspects every `.package` file. CC is Sims 4's binary format (DBPF). The cleaner:
1. **Checks the file header** — if it doesn't start with `DBPF`, the file is corrupt and won't load
2. **Finds duplicates by filename** — same mod installed in two folders will cause conflicts
3. **Finds exact duplicates by file hash** — identical files wasting space
4. **Flags tuning conflicts** — multiple packages trying to override the same game file
5. **Finds WickedWhims-dependent packages** — if you don't have WW installed

Warning: scanning 10,000+ packages takes 2–5 minutes. The progress bar shows you where it's at.

---

### Step 5 — Analyze Your Crash Log (`[!!] LOG ANALYZER` tab)

Click **!! PARSE LAST EXCEPTION LOG**. The app reads your `lastException.txt` (the file the game writes when it crashes) and translates it from raw error XML into plain English:

- **Was there a crash?** — checks if tuning finished loading
- **How many errors?** — total count from the log
- **Top root causes** — the most-repeated errors, sorted by frequency
- **Which mod?** — traces errors back to specific script files where possible
- **Plain English explanations** — "This mod uses an API that EA removed in patch 1.105"

---

### Step 6 — Fix and Repair (`[WR] FIX & REPAIR` tab)

One-click actions:
- **[!!] QUARANTINE ALL CRITICAL** — same as the Scan tab button
- **[~~] CLEAR ALL CACHES** — deletes `localthumbcache.package` and slot/blueprint caches. Always do this after changing mods.
- **[OK] RESTORE ALL QUARANTINED** — moves all quarantined files back to Mods
- **[->] OPEN MODS FOLDER** — opens your Mods folder in Explorer
- **[XX] REMOVE DUPLICATE PACKAGES** — quarantines older duplicates, keeping the newest
- **[??] SHOW QUARANTINE MANIFEST** — lists every quarantined file with the reason it was moved

---

### Step 7 — Clear Cache and Launch

After making any changes, **always clear caches** before launching the game. Click **~~ CLEAR CACHE** on the Scan tab or **[~~] CLEAR ALL CACHES** on the Fix tab. The CACHE (MB) stat card will drop to 0.

Then launch your game. If it still crashes, come back and check the LOG ANALYZER tab.

---

## 🧪 Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

**31 tests** covering scanner detection, CC validation, log parsing, and quarantine/restore.

---

## 🖥️ Screenshots

> **Main Dashboard** — live stats, animated scanline header, neon cyberpunk theme  
> **Scan Tab** — real-time script scanning with color-coded severity  
> **CC Cleaner Tab** — duplicate detection with file sizes  
> **Log Analyzer Tab** — parsed lastException output with per-mod breakdowns  
> **Fix & Repair Tab** — quarantine manager with restore support  

---

## 📦 Download & Run (No Python Required)

1. Go to the [**Releases**](../../releases) page
2. Download `Sims4ModGuard.exe`
3. Double-click and run — no install needed

> ⚠️ Windows Defender may show a warning for unsigned `.exe` files from unknown publishers.  
> Click **"More info" → "Run anyway"** — the app is open source and safe.

---

## 🛠️ Run From Source

**Requirements**: Python 3.10+

```bash
git clone https://github.com/HuciferX/Sims4ModGuard.git
cd Sims4ModGuard
pip install -r requirements.txt
python gui_app.py
```

Or use the CLI:
```bash
python run.py --help
python run.py --scan-only
python run.py --full-scan
python run.py --fix
```

---

## 🔨 Build the .exe Yourself

```bash
pip install pyinstaller
python -m PyInstaller --onefile --windowed --name "Sims4ModGuard" gui_app.py
```

The output will be at `dist/Sims4ModGuard.exe`.

---

## 🧩 What Mods Are Detected?

Sims4ModGuard flags mods using patterns that broke in **Patch 1.105+** and are confirmed broken through **1.121**:

| Pattern | Why It's Broken |
|--------|----------------|
| `inject_load_data_into_class_instances` | Genealogy caching API removed |
| `HasTunableReference` | Tunable reference system changed |
| `add_super_affordances` | Affordance injection API removed |
| `lmsinjector` | Scumbumbo's injector no longer compatible |
| `add_wicked_attributes` | WickedWhims dependency (WW not installed) |
| `leroi_death_injector` | LeRoi death system removed |

**Whitelisted** (known good, never flagged):
- MCCC 2026.1.1+
- Basemental 8.18+
- BetterExceptions
- XmlInjector
- Kuttoe ForbiddenSpells

---

## 📁 Project Structure

```
Sims4ModGuard/
├── gui_app.py              # Cyberpunk GUI dashboard (tkinter + customtkinter)
├── run.py                  # CLI entry point
├── requirements.txt
├── README.md
└── sims4modguard/
    ├── known_patterns.py   # All detection rules, whitelist, update URLs
    ├── scanner.py          # .ts4script ZIP scanner
    ├── cc_cleaner.py       # .package DBPF validator + duplicate finder
    ├── log_parser.py       # lastException.txt parser
    ├── quarantine.py       # Safe file mover with JSON manifest
    ├── cache_manager.py    # Cache clearing + folder detection
    └── main.py             # CLI orchestrator
```

---

## 🤝 Contributing

Pull requests welcome! If you find a new broken pattern or know of a mod that should be whitelisted, open an issue or PR.

**To add a broken pattern**: edit `sims4modguard/known_patterns.py` — `BROKEN_PATTERNS` dict.  
**To whitelist a mod**: add the script filename to `WHITELIST_SCRIPTS`.

---

## 📜 License

MIT — free for personal and community use. Credit appreciated but not required.

---

## 🙏 Credits

- **Hucifer** — concept, vision, testing
- **🦉 Hypatia** — engineering, pattern research, build
- Community mod authors who open-source their work and make fixing possible
- The Sims 4 modding community at large — you're the reason this exists

---

*"We make the mods work again."* 🦉
