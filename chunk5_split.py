"""50/50 inside the active chunk 5 to find the crash culprit."""
import json, shutil, sys
from pathlib import Path

MODS   = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\Mods')
STAGE2 = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\CHUNK5_STAGE')
STATE2 = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\chunk5_state.json')

def save(d): STATE2.write_text(json.dumps(d, indent=2))
def load(): return json.loads(STATE2.read_text()) if STATE2.exists() else None

def active():
    return sorted(
        [str(p) for p in MODS.rglob('*.package')
         if 'MODS_DISABLED' not in p.parts
         and 'CHUNK_STAGE' not in str(p)
         and 'CHUNK5_STAGE' not in str(p)],
        key=lambda x: Path(x).name.lower()
    )

def cmd_init():
    pkgs = active()
    half = len(pkgs) // 2
    first_half  = pkgs[:half]
    second_half = pkgs[half:]
    print(f'{len(pkgs)} packages in active chunk')
    print(f'First half:  {len(first_half)} packages ({Path(first_half[0]).name} ... {Path(first_half[-1]).name})')
    print(f'Second half: {len(second_half)} packages ({Path(second_half[0]).name} ... {Path(second_half[-1]).name})')

    # Stage second half, keep first half active
    STAGE2.mkdir(exist_ok=True)
    for p in second_half:
        dest = STAGE2 / Path(p).name
        shutil.move(p, str(dest))

    save({'first': first_half, 'second': second_half, 'active': 'first'})
    print(f'\nFirst half ACTIVE ({len(first_half)} packages)')
    print('Launch the game:')
    print('  Loads   -> Culprit in SECOND half -> python chunk5_split.py swap')
    print('  Crashes -> Culprit in FIRST half  -> python chunk5_split.py swap')

def cmd_swap():
    state = load()
    if not state:
        print('Run init first'); return
    active_half = state['active']
    if active_half == 'first':
        # Stage first half, restore second half
        for p in state['first']:
            src = MODS / Path(p).name
            if src.exists(): shutil.move(str(src), str(STAGE2 / Path(p).name))
        for p in state['second']:
            src = STAGE2 / Path(p).name
            if src.exists(): shutil.move(str(src), str(MODS / Path(p).name))
        state['active'] = 'second'
        print(f'SECOND HALF now active ({len(state["second"])} packages)')
    else:
        # Stage second half, restore first half
        for p in state['second']:
            src = MODS / Path(p).name
            if src.exists(): shutil.move(str(src), str(STAGE2 / Path(p).name))
        for p in state['first']:
            src = STAGE2 / Path(p).name
            if src.exists(): shutil.move(str(src), str(MODS / Path(p).name))
        state['active'] = 'first'
        print(f'FIRST HALF now active ({len(state["first"])} packages)')
    save(state)
    print()
    print('Launch the game. Crashes = culprit in this half.')

def cmd_restore():
    if STAGE2.exists():
        for f in STAGE2.rglob('*.package'):
            shutil.move(str(f), str(MODS / f.name))
        for d in sorted(STAGE2.rglob('*'), reverse=True):
            try: d.rmdir()
            except: pass
        try: STAGE2.rmdir()
        except: pass
    STATE2.unlink(missing_ok=True)
    print(f'Restored. Active: {len(active())} packages')

def cmd_status():
    state = load()
    if not state:
        print('No split test running'); return
    a = active()
    print(f'{state["active"]} half active | {len(a)} packages in Mods')

cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
{'init': cmd_init, 'swap': cmd_swap, 'restore': cmd_restore, 'status': cmd_status}.get(cmd, cmd_status)()
