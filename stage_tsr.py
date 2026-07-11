"""
Stage the 10 largest TSR archives so the game can complete its first
mod-list cache build without hitting memory limits.
After the game loads successfully, run: python stage_tsr.py restore
"""
import sys, shutil, json
from pathlib import Path

MODS  = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\Mods')
STAGE = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\TSR_STAGE')
STATE = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\tsr_stage_state.json')

def cmd_stage():
    tsrfiles = sorted(
        [p for p in MODS.rglob('tsrarchive*.package')],
        key=lambda x: x.stat().st_size, reverse=True
    )
    # Stage the largest 10 (keep smallest 10 active)
    to_stage = tsrfiles[:10]
    keep     = tsrfiles[10:]

    total_stage = sum(f.stat().st_size for f in to_stage) // 1024 // 1024
    total_keep  = sum(f.stat().st_size for f in keep)     // 1024 // 1024

    STAGE.mkdir(exist_ok=True)
    staged = []
    for f in to_stage:
        dest = STAGE / f.name
        sz = f.stat().st_size // 1024 // 1024
        shutil.move(str(f), str(dest))
        staged.append(str(f))
        print(f'  Staged: {f.name} ({sz} MB)')

    # Save state
    STATE.write_text(json.dumps({'staged': staged}), encoding='utf-8')
    print(f'\nStaged {len(to_stage)} archives ({total_stage} MB)')
    print(f'Active {len(keep)} archives ({total_keep} MB)')
    print()
    print('Now launch the game. Once it loads:')
    print('  python stage_tsr.py restore')

def cmd_restore():
    if not STATE.exists():
        print('No stage state found')
        return
    state = json.loads(STATE.read_text(encoding='utf-8'))
    for orig_path in state['staged']:
        name = Path(orig_path).name
        src  = STAGE / name
        if src.exists():
            shutil.move(str(src), orig_path)
            print(f'  Restored: {name}')
    STAGE.rmdir() if STAGE.exists() and not any(STAGE.iterdir()) else None
    STATE.unlink(missing_ok=True)
    print('All TSR archives restored. Next launch will be fast (mod cache built).')

cmd = sys.argv[1] if len(sys.argv) > 1 else 'stage'
if cmd == 'restore': cmd_restore()
else: cmd_stage()
