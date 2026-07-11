"""
Binary search targeting the confirmed culprit range:
NitroPanic_Chi Sets Tops.package → NynaeveDesign_454 - Vegetables - Eggplant.package

Commands:
  python find_culprit.py init    -- isolate culprit range, split in half
  python find_culprit.py swap    -- swap halves
  python find_culprit.py status  -- show current half
  python find_culprit.py restore -- put everything back
"""
import json, shutil, sys
from pathlib import Path

MODS  = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\Mods')
STAGE = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\CULPRIT_STAGE')
STATE = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\culprit_state.json')

def save(d): STATE.write_text(json.dumps(d, indent=2))
def load(): return json.loads(STATE.read_text()) if STATE.exists() else None

def all_pkgs():
    return sorted([str(p) for p in MODS.rglob('*.package')
                   if 'MODS_DISABLED' not in p.parts and 'CULPRIT_STAGE' not in str(p)],
                  key=lambda x: Path(x).name.lower())

def cmd_init():
    # Get just the culprit range
    all_p = all_pkgs()
    culprit = [p for p in all_p
               if Path(p).name.lower() >= 'nitropanic_chi sets tops'
               and Path(p).name.lower() <= 'nynaevedesign_454']
    print(f'Culprit range: {len(culprit)} packages')
    print(f'  {Path(culprit[0]).name}')
    print(f'  ...{Path(culprit[-1]).name}')

    half = len(culprit) // 2
    A, B = culprit[:half], culprit[half:]

    print(f'\nA ({len(A)}): {Path(A[0]).name} ... {Path(A[-1]).name}')
    print(f'B ({len(B)}): {Path(B[0]).name} ... {Path(B[-1]).name}')

    # Stage B, keep A active, stage everything OUTSIDE culprit range too
    outside = [p for p in all_p if p not in culprit]
    STAGE.mkdir(exist_ok=True)
    staged_outside = []
    for p in outside:
        dest = STAGE / ('out_' + Path(p).name)
        shutil.move(p, str(dest))
        staged_outside.append(p)
    for p in B:
        shutil.move(p, str(STAGE / ('B_' + Path(p).name)))

    save({'A': A, 'B': B, 'outside': outside, 'active': 'A'})
    print(f'\nA active ({len(A)} packages). ALL other packages staged.')
    print('Launch the game:')
    print('  Loads   -> culprit in B -> python find_culprit.py swap')
    print('  Crashes -> culprit in A -> python find_culprit.py swap')

def cmd_swap():
    state = load()
    if not state: print('Run init first'); return
    cur = state['active']
    nxt = 'B' if cur == 'A' else 'A'
    for p in state[cur]:
        s = MODS / Path(p).name
        if s.exists(): shutil.move(str(s), str(STAGE / (cur + '_' + Path(p).name)))
    for p in state[nxt]:
        s = STAGE / (nxt + '_' + Path(p).name)
        if s.exists(): shutil.move(str(s), str(MODS / Path(p).name))
    state['active'] = nxt
    save(state)
    pkgs = state[nxt]
    print(f'{nxt} active ({len(pkgs)} pkgs):')
    print(f'  {Path(pkgs[0]).name}')
    print(f'  ...{Path(pkgs[-1]).name}')
    print('Launch. Crash=culprit here, Loads=culprit in other half.')

def cmd_status():
    state = load()
    if not state: print('No search running'); return
    cur = state['active']
    pkgs = state[cur]
    active = all_pkgs()
    print(f'{cur} active | {len(active)} in Mods | range: {Path(pkgs[0]).name}...{Path(pkgs[-1]).name}')

def cmd_restore():
    if STAGE.exists():
        for f in STAGE.rglob('*.package'):
            # Strip prefix (out_, A_, B_) to get original name
            name = f.name
            for prefix in ['out_', 'A_', 'B_']:
                if name.startswith(prefix):
                    name = name[len(prefix):]
                    break
            shutil.move(str(f), str(MODS / name))
        for d in sorted(STAGE.rglob('*'), reverse=True):
            try: d.rmdir()
            except: pass
        try: STAGE.rmdir()
        except: pass
    STATE.unlink(missing_ok=True)
    print(f'Restored. {len(all_pkgs()):,} packages active.')

cmds = {'init': cmd_init, 'swap': cmd_swap, 'status': cmd_status, 'restore': cmd_restore}
cmds.get(sys.argv[1] if len(sys.argv) > 1 else 'status', cmd_status)()
