# 🦉 Sims4ModGuard — AI-Powered Mod Conflict Fixer

> **Hypatia's free gift to the Sims 4 community.**  
> Built by **Hucifer** & **🦉 Hypatia** — free forever, open source, no ads, no paywalls.

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-blue?style=flat-square)](../../releases/latest)
[![No Python](https://img.shields.io/badge/No%20Python-Required-brightgreen?style=flat-square)](../../releases/latest)
[![Tests](https://img.shields.io/badge/Tests-52%20Passing-success?style=flat-square)](#)
[![Version](https://img.shields.io/badge/Version-1.2-purple?style=flat-square)](../../releases/latest)
[![Free](https://img.shields.io/badge/Cost-Free%20Forever-ff69b4?style=flat-square)](#)
[![AI Powered](https://img.shields.io/badge/AI-Hypatia%20Backend-00e5ff?style=flat-square)](https://hySims.app)

---

## ⬇️ Download — One Click, No Setup

### ➡️ [DOWNLOAD Sims4ModGuard.exe — Free](../../releases/latest)

1. Go to **Releases** → download `Sims4ModGuard.exe`
2. Double-click it. That's all.
3. No Python. No install. No admin rights needed.

> **Windows Defender shows a warning?** Click **"More info" → "Run anyway"**  
> This is normal for unsigned apps. Every line of code is public — open source, always.

---

## 🔥 The Problem This Solves

You've spent 6 months building a 13,000-mod collection. EA releases a patch. You wait **90 minutes** for the game to load. It crashes. You have no idea which of your 13,000+ mods broke.

Without a tool like this, finding the culprit means the 50/50 method — moving half your mods, relaunching, repeat — for potentially **hundreds of hours.**

**Sims4ModGuard eliminates that.** It found the single crash-causing package in a 10,521-mod collection in **8 game launches** using automated binary search. It also discovered that a UTF-8 BOM in `Resource.cfg` was silently hiding 5 GB of TSR archives — making the game load 0% of that CC with no error message anywhere.

---

## ✨ What It Does

### 🔍 Script Scanner
Catches Python mods using injection patterns EA removed:
- `inject_load_data_into_class_instances` — removed in 1.105
- `HasTunableReference` — removed in 1.100  
- `lmsinjector` (Scumbumbo pattern) — broken since 1.105
- `add_super_affordances`, `leroi_death_injector`, WW dependency markers

### 📦 CC Package Deep Scanner
- Validates every `.package` file's DBPF header
- Finds the same mod installed twice (wasted load time + visual glitching)
- Detects corrupt files that silently fail to load
- Identifies 22,000+ MB TSR archives, CAS hair, Build/Buy objects, tuning overrides
- Finds packages too deep in subfolders (game silently ignores anything >5 levels deep)

### 🗃️ Known Conflicts Database
Pre-loaded with **16+ real conflicts** discovered through actual debugging:

| Mod | Issue | Severity |
|-----|-------|----------|
| `NRaas_MasterController.package` | Crashes C++ DBPF reader, conflicts with MCCC 2026 | 🔴 Critical |
| `AEP_StudiO_CC.package` (720MB, 2018) | Outdated format crashes game | 🔴 Critical |
| `plzsaysike Library*.package` | Injects outdated posture tuning | 🟡 Warning |
| `Tmex-CleanUI.package` | Black screen + UI exception | 🔴 Critical |
| `MoreTraitsInCAS-v1q-1.108.package` | Wrong patch version, loading hang | 🔴 Critical |
| `XmlInjector v4.1` or older | Silent injection failures | 🔴 Critical |
| `Resource.cfg` with UTF-8 BOM | **Hides ALL subfolder CC silently** | 🔴 Critical |

The database ships with the app and **updates automatically** — when the community finds new broken mods, everyone gets the fix on next launch.

### 🧠 Crash Predictor
Scans every package for crash-trigger patterns without launching the game:
- Pre-2016 TypeIDs that crash the C++ reader
- Oversized resources triggering memory errors
- NRaas pattern detection, empty stub files

### 🔬 1/8 Chunk Isolation Wizard
For hard crashes with no log output: splits your 10,000+ mods into 8 groups and tests each. Narrows any crash to the exact file in ~8 test launches.

**Real result:** Found `NRaas_MasterController.package` among 10,521 mods in 8 launches.

### 🛠️ Resource.cfg Validator  
Detects and fixes the UTF-8 BOM bug that silently makes the game ignore all organized subfolders — including TSRLibrary, Basemental_Drugs, and any creator-organized folder.

### 🚀 Real-Time Game Launcher
- Launch the game directly from within Sims4ModGuard
- Live uptime counter + error count updating every 5 seconds
- **Crash detector** — alerts the moment TS4_x64.exe dies unexpectedly
- **Hang detector** — alerts if loading screen exceeds 8 minutes with no log activity

### 📋 Log Analyzer
Translates `lastException.txt` from raw XML into plain English:
- Which mods caused errors, what type, and what to do
- Detects `TuningLoadFinished: False` (indicates a critical load crash)
- Powered by **Hypatia AI** when connected to the backend

### 💾 Save File Analyzer
- Scans `.save` files for orphaned mod references
- Generates a clean save copy with broken references removed

### 🔄 Auto-Updater
On every launch, silently checks GitHub. If a new version is available, shows a neon progress dialog, downloads the `.exe`, replaces itself, and relaunches. Zero manual steps.

### 🦉 Hypatia AI Backend *(at api.hySims.app)*
- Send your `lastException.txt` → get specific, version-aware fix steps back
- Community conflict submissions — you find a broken mod, you report it, everyone benefits
- Version conflict detection using LLM reasoning across patch history
- Falls back gracefully: the app works fully without it

---

## 📊 Real Results — 13,000-Mod Collection

| Problem | Root Cause | Outcome |
|---------|-----------|--------|
| Hard crash, no log | `NRaas_MasterController.package` (2016, conflicted with MCCC 2026) | Found in 8 launches |
| All TSR archives invisible | `Resource.cfg` UTF-8 BOM (hiding 5 GB) | Auto-fixed |
| UI black screen | `MoreTraitsInCAS` wrong patch version | Updated to v2d |
| Gallery hang on load | EA AS3 widget bug (online mode) | Fixed via Options.ini |
| Save load: infinite hang | Orphaned CC references | Clean save generated |
| 2,858 errors per session | EA 1.121 vanilla posture bug | Documented (not mod-caused) |

**Error count: 2,858 → 14 (99.5% reduction)**

---

## 🤝 Community Conflict Database

`sims4modguard/known_conflicts.json` is open-source and community-maintained.

Found a mod that crashes 1.121?
1. Open a **GitHub Issue** with the filename, patch, and error
2. Or use the **Submit Conflict** button in the app
3. Verified entries ship to all users on next auto-update

---

## ❓ FAQ

**Q: How long does a scan take?**  
Script scan: ~30 seconds. Full CC scan: 5–20 minutes for 10,000+ packages.

**Q: My game still crashes after using this.**  
Some errors (like EA's 1.121 posture callback bug — `object_reservation_tests`) are EA vanilla bugs, not fixable by removing mods. The log analyzer identifies these separately.

**Q: Why play offline?**  
The EA Gallery widget (main menu store panels) has an AS3 null-reference bug that keeps the loading screen up when online. The app can apply the offline fix to `Options.ini` automatically.

**Q: Is my data safe?**  
No telemetry. No accounts. No internet required. The AI backend is opt-in and only receives log content you explicitly send. All source is here, MIT licensed.

---

## 🛠️ Run From Source

```bash
git clone https://github.com/HuciferX/Sims4ModGuard.git
cd Sims4ModGuard
pip install -r requirements.txt
python gui_app.py
```

---

## 📁 Key Files

| File | What It Does |
|------|-------------|
| `gui_app.py` | Full app — all tabs, wizard, cyberpunk UI |
| `sims4modguard/known_conflicts.json` | Community conflict database (16+ entries) |
| `sims4modguard/conflict_checker.py` | Pattern-matches filenames against DB |
| `sims4modguard/updater.py` | GitHub release checker + auto-update |
| `sims4modguard/update_dialog.py` | Animated download progress dialog |
| `sims4modguard/api_client.py` | Hypatia AI backend client |
| `sims4modguard/scanner.py` | .ts4script injection pattern detector |
| `sims4modguard/cc_cleaner.py` | DBPF validator + duplicate finder |
| `sims4modguard/log_parser.py` | lastException.txt → plain English |
| `sims4modguard/quarantine.py` | Safe file mover with restore manifest |
| `cc_simulator.py` | Full CC load pipeline simulation |
| `crash_predictor.py` | Pre-scan for crash-trigger patterns |
| `chunk_test.py` | 1/8 chunk isolation wizard |
| `find_culprit.py` | Binary search for single crash file |
| `check_paths.py` | Resource.cfg BOM validator |
| `landing/` | hySims.app landing page source |
| `hypatia-sims4-service/` | FastAPI AI backend (Linux deploy) |
| `tests/` | 52 tests: scanner, CC cleaner, log parser, quarantine |

---

## 📜 License

MIT — free for personal and community use. Credit appreciated but not required.

---

## 🙏 Credits

- **Hucifer** — concept, vision, real-world testing with a 13,000-mod collection
- **🦉 Hypatia** — AI engineering, architecture, all the code
- Sims 4 modding community — you're why this exists

---

*"We make the mods work again."* 🦉

**[🌐 hySims.app](https://hySims.app)** • **[GitHub](https://github.com/HuciferX/Sims4ModGuard)** • **[Download](../../releases/latest)**

---
# OLD README BELOW (REPLACED)
### The Sims 4 Mod Fixer — fix crashes before you boot. No more hour-long loads that end in a crash.

![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-blue?style=flat-square)
![No Python Needed](https://img.shields.io/badge/Python-NOT%20required-brightgreen?style=flat-square)
![Game](https://img.shields.io/badge/Sims%204-Patch%201.121%2B-ff69b4?style=flat-square)
![Free](https://img.shields.io/badge/Cost-Free%20Forever-purple?style=flat-square)

> Built by **Hucifer** & **🦉 Hypatia** — free forever, open source, community edition.

---

## ⬇️ Download — No Installation, No Python, No Setup

### ➡️ [CLICK HERE TO DOWNLOAD Sims4ModGuard.exe](../../releases/latest)

1. Click the link above → go to the **Releases** page
2. Download **Sims4ModGuard.exe** under "Assets"
3. Double-click it to run — that's all

> **Windows Defender warning?** Click **"More info"** → **"Run anyway"**
> This is normal for unsigned apps. The code is fully open-source — you can read every line right here.

---

## 🎮 What Does This Do?

You have thousands of mods. Every time EA updates Sims 4, some mods break — but you don't find out until you've waited an hour for the game to load and then it crashes.

**Sims4ModGuard fixes that.** It simulates what the game does when it boots — *without* actually launching the game.  
It takes 10–30 minutes to scan, not an hour, and tells you **exactly which mods will crash the game before you waste your time.**

---

## 🪄 The 6-Step Wizard (Just Click Next)

When you open the app, you'll see the **WIZARD** tab. Follow the steps in order:

| # | Step | What It Does | Time |
|---|------|-------------|------|
| 1 | **Detect Folders** | Finds your Mods folder and game installation | Instant |
| 2 | **Index Game Files** | Reads the real game's 3,500+ Python modules to check your mods against | ~45 sec (cached after) |
| 3 | **Simulate Boot** | Runs all 7 phases of what the game does when it loads — without launching | 10–30 min |
| 4 | **Fix Issues** | Moves broken mods out (safely — you can restore them any time) | Instant |
| 5 | **Clear Caches** | Deletes the thumbnail cache (required after any mod change or the game crashes on loading) | Instant |
| 6 | **Check Save File** | Scans your save for broken mod references, can generate a clean copy | 2–5 min |

After step 5 you'll see a **CC Health Grade (A–F)** and a **Launch Game** button.

---

## 🔍 What Gets Checked

**Script mods (.ts4script)**
- Checks for Python functions EA removed in recent patches
- Checks that the mod can actually import (crashes before main menu if it can't)
- Detects old injection patterns that no longer work

**CC packages (.package)**
- Finds the same CC installed twice (wasted load time + glitching)
- Finds corrupt packages that silently fail to load
- Finds mods overriding game data that changed in a patch

**Save files (.save)**
- Finds orphaned references (mods you had when the save was made but have since removed)
- Generates a clean save copy with broken references stripped out

---

## 🔒 Will It Delete My Files?

**No. Never.** The app only *moves* files, never deletes them.

When a mod is "quarantined" it goes into a folder called `MODS_DISABLED` inside your Sims 4 folder.  
You can restore any file any time from the **Fix & Repair** tab in the app.

---

## 📊 Example — Real Results on a 13,000-Mod Collection

| Found | Example | Action Taken |
|-------|---------|--------------|
| Near-exact duplicate CC | Basemental Drugs installed twice (6,386 shared IDs) | Kept newer, quarantined older |
| Named duplicate | `NisaK_Wicked_Perversions_ROOTDUPE.package` | Quarantined |
| Old version | `EllaNoir_August.package` + `EllaNoir_September.package` | Kept September, removed August |
| Depth violation | CC buried 6+ subfolders deep | Flagged — game ignores it silently |

The **One-Click Fix** button handles all of these automatically.

---

## 🔗 Known Mod Update Links

The HTML report includes official update links for 40+ recognized mods. Examples:

| Mod | Where to Get the Latest |
|-----|--------------------------|
| WickedWhims | [turbodriver.itch.io/wickedwhims](https://turbodriver.itch.io/wickedwhims) *(Free)* |
| MCCC | [deaderpoolmc.tumblr.com](https://deaderpoolmc.tumblr.com/) *(Free)* |
| Basemental Drugs | [basementalcc.com](https://basementalcc.com/adult_mods/basemental-drugs/) *(Free, age check)* |
| LittleMsSam | [lms-mods.com](https://lms-mods.com/) *(Free)* |
| XML Injector | [scumbumbomods.com](https://scumbumbomods.com/) *(Free)* |
| Kuttoe mods | [kuttoe.itch.io](https://kuttoe.itch.io/) *(Free)* |
| EllaNoir mods | [patreon.com/ellanoir](https://www.patreon.com/ellanoir) *(Patreon)* |
| SCCOR | [srslysims.com](https://srslysims.com/) *(Free)* |

---

## ❓ FAQ

**Q: Do I need Python?**  
A: No. The `.exe` in Releases runs directly on Windows 10/11.

**Q: How long does the scan take?**  
A: Step 3 (Boot Simulation) takes 10–30 min for 10,000+ mods. It runs in the background while you do other things.

**Q: The game still crashes after using this?**  
A: Run Step 3 again — something new may have been flagged. Also check the **Log Analyzer** tab with your `lastException.txt`.

**Q: What's the CC Health Grade?**  
A: After the scan, the app grades your mod collection A–F:
- **A** = Clean! No broken mods, no real issues
- **B** = Minor issues, some duplicate CC
- **C** = Some broken mods or heavy duplicates
- **D/F** = Critical mods that will crash the game

**Q: Windows says "protected your PC" — is it safe?**  
A: Yes. Click **"More info" → "Run anyway"**. This warning appears because the `.exe` doesn't have an expensive code-signing certificate, not because it's dangerous. All source code is right here on GitHub.

---

## 🛠️ For Developers — Run From Source

```bash
git clone https://github.com/HuciferX/Sims4ModGuard.git
cd Sims4ModGuard
pip install -r requirements.txt
python gui_app.py
```

**Build your own .exe:**
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "Sims4ModGuard" gui_app.py
# Output: dist/Sims4ModGuard.exe
```

**Run the CLI audit (saves HTML + text report):**
```bash
python run_audit.py
```

---

## 📁 What's in the Repo

| File | What It Does |
|------|-------------|
| `gui_app.py` | The full app window — wizard, tabs, all UI |
| `run_audit.py` | CLI version: full scan + saves HTML report |
| `sims4modguard/boot_engine.py` | The 7-phase boot simulator |
| `sims4modguard/game_index.py` | Reads real game files (3,500+ modules) |
| `sims4modguard/step_indicator.py` | Animated wizard step circles (Pillow glow) |
| `sims4modguard/save_analyzer.py` | Save file analyzer + clean-save generator |
| `sims4modguard/run_logger.py` | HTML + text audit log with update links |
| `sims4modguard/mod_database.py` | 40+ known mods with official update URLs |
| `sims4modguard/dlc_database.py` | All 45 DLC packs |
| `sims4modguard/scanner.py` | .ts4script ZIP scanner |
| `sims4modguard/cc_cleaner.py` | .package DBPF validator |
| `sims4modguard/log_parser.py` | lastException.txt → plain English |
| `sims4modguard/quarantine.py` | Safe file mover with restore manifest |

---

## 📜 License

MIT — free for personal and community use. Credit appreciated but not required.

---

## 🙏 Credits

- **Hucifer** — concept, vision, testing
- **🦉 Hypatia** — engineering, AI, build
- The Sims 4 modding community — you're the reason this exists

---

*"We make the mods work again."* 🦉
