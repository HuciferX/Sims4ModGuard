"""Stage ALL active TSR archives + Lifeline to find the crash culprit."""
import shutil, json
from pathlib import Path

MODS  = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\Mods')
STAGE = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\TSR_STAGE2')
STATE = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\tsr_stage2_state.json')

STAGE.mkdir(exist_ok=True)

# Stage ALL remaining TSR archives and Lifeline
to_stage = [p for p in MODS.rglob('*.package')
            if 'MODS_DISABLED' not in p.parts
            and 'TSR_STAGE' not in str(p)
            and ('tsrarchive' in p.name.lower() or
                 'Lifeline' in p.name or
                 'Kiki_animation' in p.name or
                 'TLayer_Animation' in p.name or
                 'wild_guy_Animation' in p.name or
                 'Zorak_Animation' in p.name or
                 'Yummy-o-Tummy' in p.name)]

staged = []
total_mb = 0
for f in to_stage:
    mb = f.stat().st_size // 1024 // 1024
    dest = STAGE / f.name
    shutil.move(str(f), str(dest))
    staged.append(str(f))
    total_mb += mb
    print(f'  Staged {mb}MB: {f.name}')

STATE.write_text(json.dumps({'staged': staged}))

# Count what's left
remain = [p for p in MODS.rglob('*.package')
          if 'MODS_DISABLED' not in p.parts and 'TSR_STAGE' not in str(p)]
remain_mb = sum(p.stat().st_size for p in remain) // 1024 // 1024
print(f'\nStaged: {len(staged)} files ({total_mb} MB)')
print(f'Remaining: {len(remain):,} packages ({remain_mb:,} MB)')
print()
print('Launch the game. If it loads:')
print('  -> restore one TSR at a time to find the corrupt one')
print('  -> python stage_all_tsr.py restore')

import sys
if len(sys.argv) > 1 and sys.argv[1] == 'restore':
    if STATE.exists():
        state = json.loads(STATE.read_text())
        for orig in state['staged']:
            name = Path(orig).name
            src  = STAGE / name
            if src.exists():
                shutil.move(str(src), orig)
                print(f'  Restored: {name}')
        STATE.unlink(missing_ok=True)
        print('Done')
