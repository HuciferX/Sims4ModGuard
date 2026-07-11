import shutil, json
from pathlib import Path

MODS   = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\Mods')
STAGE2 = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\CHUNK5B_STAGE')
STATE2 = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\chunk5b_state.json')

import sys
state = json.loads(STATE2.read_text())

if sys.argv[1:] and sys.argv[1] == 'restore':
    for f in STAGE2.rglob('*.package'):
        shutil.move(str(f), str(MODS / f.name))
    try: STAGE2.rmdir()
    except: pass
    STATE2.unlink(missing_ok=True)
    print('Restored')
else:
    active_half = state['active']
    if active_half == 'first':
        for p in state['first']:
            src = MODS / Path(p).name
            if src.exists(): shutil.move(str(src), str(STAGE2 / Path(p).name))
        for p in state['second']:
            src = STAGE2 / Path(p).name
            if src.exists(): shutil.move(str(src), str(MODS / Path(p).name))
        state['active'] = 'second'
        print(f'SECOND HALF now active ({len(state["second"])} packages)')
        print(f'Range: {Path(state["second"][0]).name} ... {Path(state["second"][-1]).name}')
    else:
        for p in state['second']:
            src = MODS / Path(p).name
            if src.exists(): shutil.move(str(src), str(STAGE2 / Path(p).name))
        for p in state['first']:
            src = STAGE2 / Path(p).name
            if src.exists(): shutil.move(str(src), str(MODS / Path(p).name))
        state['active'] = 'first'
        print(f'FIRST HALF now active ({len(state["first"])} packages)')
    STATE2.write_text(json.dumps(state))
    print('Launch the game. Crashes = culprit in this half.')
