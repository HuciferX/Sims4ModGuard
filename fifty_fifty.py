"""
50/50 Package Isolation Test
Moves half your CC packages aside, so you can launch and test.
Narrows down which half contains the culprit causing tuning errors.

Usage:
  python fifty_fifty.py init    -- split packages and move HALF out
  python fifty_fifty.py restore -- put all packages back
  python fifty_fifty.py swap    -- swap which half is active
  python fifty_fifty.py status  -- show current state
"""
import json, sys, shutil
from pathlib import Path

S4     = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4')
MODS   = S4 / 'Mods'
STAGE  = S4 / 'MODS_5050_STAGE'   # packages moved for testing
STATE  = S4 / 'fifty_fifty_state.json'

def save_state(data):
    STATE.write_text(json.dumps(data, indent=2), encoding='utf-8')

def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding='utf-8'))
    return None

def get_all_packages():
    """Get all active packages, excluding MODS_DISABLED and the stage folder."""
    return sorted([
        p for p in MODS.rglob('*.package')
        if 'MODS_DISABLED' not in p.parts
        and 'MODS_5050_STAGE' not in str(p)
    ], key=lambda p: p.name.lower())

def cmd_status():
    state = load_state()
    if not state:
        print("No 50/50 test in progress.")
        active = get_all_packages()
        print(f"Active packages: {len(active):,}")
        return

    active  = get_all_packages()
    staged  = list(STAGE.rglob('*.package')) if STAGE.exists() else []
    print(f"50/50 test in progress — Round {state.get('round', 1)}")
    print(f"  Active (in Mods):  {len(active):,} packages")
    print(f"  Staged (set aside): {len(staged):,} packages")
    print()
    print("Current active half:")
    for n in state.get('active_names', [])[:5]:
        print(f"  {n}")
    if len(state.get('active_names', [])) > 5:
        print(f"  ... and {len(state['active_names'])-5} more")

def cmd_init():
    state = load_state()
    if state:
        print("50/50 test already in progress. Use 'restore' first or 'swap' to continue.")
        return

    packages = get_all_packages()
    total = len(packages)
    print(f"Found {total:,} active packages.")

    STAGE.mkdir(exist_ok=True)

    # Move the SECOND half into the stage area
    half = total // 2
    to_stage = packages[half:]   # second half goes to stage
    active   = packages[:half]   # first half stays active

    print(f"Keeping first half active: {len(active):,} packages")
    print(f"Staging second half:       {len(to_stage):,} packages")
    print()
    print("Moving packages to stage folder...")

    moved = 0
    for pkg in to_stage:
        # Preserve subfolder structure under STAGE
        rel = pkg.relative_to(MODS)
        dest = STAGE / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pkg), str(dest))
        moved += 1
        if moved % 500 == 0:
            print(f"  Moved {moved:,}/{len(to_stage):,}...")

    save_state({
        'round': 1,
        'active_names': [p.name for p in active],
        'staged_names': [p.name for p in to_stage],
        'active_half': 'first',
    })

    print(f"\nDone! Moved {moved:,} packages to STAGE.")
    print()
    print("=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("1. Clear caches and launch The Sims 4")
    print("2. Check if hair/kitchen CC loads")
    print()
    print("   IF hair/kitchen LOADS with first half:")
    print("     -> Culprit is in the STAGED (second) half")
    print("     -> Run: python fifty_fifty.py swap")
    print("     -> This puts second half back and stages first half")
    print("     -> Run the game again to confirm, then narrow down further")
    print()
    print("   IF hair/kitchen STILL doesn't load:")
    print("     -> Culprit is in the ACTIVE (first) half")
    print("     -> Run: python fifty_fifty.py swap")
    print("     -> Then split the first half in two and repeat")
    print()
    print("   To put everything back: python fifty_fifty.py restore")

def cmd_restore():
    state = load_state()
    if not state:
        print("No 50/50 test in progress.")
        return

    if not STAGE.exists():
        print("Stage folder doesn't exist.")
        STATE.unlink(missing_ok=True)
        return

    staged = list(STAGE.rglob('*.package'))
    print(f"Restoring {len(staged):,} staged packages to Mods...")

    restored = 0
    for pkg in staged:
        rel = pkg.relative_to(STAGE)
        dest = MODS / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pkg), str(dest))
        restored += 1

    # Clean up empty stage folders
    for folder in sorted(STAGE.rglob('*'), reverse=True):
        if folder.is_dir():
            try: folder.rmdir()
            except: pass
    try: STAGE.rmdir()
    except: pass

    STATE.unlink(missing_ok=True)
    print(f"Restored {restored:,} packages. Test complete.")

def cmd_swap():
    """Swap which half is active (put staged back, move active to stage)."""
    state = load_state()
    if not state:
        print("No 50/50 test in progress. Run 'init' first.")
        return

    currently_active = get_all_packages()
    staged = list(STAGE.rglob('*.package')) if STAGE.exists() else []

    if not staged:
        print("No staged packages found.")
        return

    print(f"Swapping halves:")
    print(f"  Moving {len(currently_active):,} active packages to stage")
    print(f"  Restoring {len(staged):,} staged packages to Mods")

    # Move current active to a temp area
    TEMP = S4 / 'MODS_5050_TEMP'
    TEMP.mkdir(exist_ok=True)
    for pkg in currently_active:
        rel = pkg.relative_to(MODS)
        dest = TEMP / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pkg), str(dest))

    # Move staged back to Mods
    for pkg in staged:
        rel = pkg.relative_to(STAGE)
        dest = MODS / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pkg), str(dest))

    # Move temp to stage
    for pkg in TEMP.rglob('*.package'):
        rel = pkg.relative_to(TEMP)
        dest = STAGE / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pkg), str(dest))

    # Clean temp
    for folder in sorted(TEMP.rglob('*'), reverse=True):
        if folder.is_dir():
            try: folder.rmdir()
            except: pass
    try: TEMP.rmdir()
    except: pass

    new_active = get_all_packages()
    new_staged = list(STAGE.rglob('*.package'))
    new_round = state.get('round', 1) + 1

    save_state({
        'round': new_round,
        'active_names': [p.name for p in new_active],
        'staged_names': [p.name for p in new_staged],
        'active_half': 'second' if state.get('active_half') == 'first' else 'first',
    })

    print(f"\nSwapped! Round {new_round}")
    print(f"  Active: {len(new_active):,}  Staged: {len(new_staged):,}")
    print()
    print("Launch the game and check if hair/kitchen loads.")
    print("  Culprit is in whichever half causes the problem.")
    print("  Run 'swap' again to narrow down further.")


# ── Entry point ────────────────────────────────────────────────────────────────

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(0)

cmd = sys.argv[1].lower()
if   cmd == 'init':    cmd_init()
elif cmd == 'restore': cmd_restore()
elif cmd == 'swap':    cmd_swap()
elif cmd == 'status':  cmd_status()
else:
    print(f"Unknown command: {cmd}")
    print("Use: init | restore | swap | status")
