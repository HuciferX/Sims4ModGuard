# 🦉 Sims4ModGuard

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
