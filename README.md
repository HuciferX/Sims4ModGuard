# 🦉 Sims4ModGuard
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
