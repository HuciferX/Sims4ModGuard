import json, shutil, sys
from pathlib import Path

MODS  = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\Mods')
STAGE = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\CULPRIT_STAGE')
STATE = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\culprit_state.json')

state = json.loads(STATE.read_text())
cur_key = state['active']   # e.g. 'A1'
cur = state[cur_key]

if sys.argv[1:] == ['split']:
    # Split current active half into two quarters
    half = len(cur) // 2
    Q1, Q2 = cur[:half], cur[half:]
    k1, k2 = cur_key + '_1', cur_key + '_2'
    print(f'Splitting {cur_key} ({len(cur)} pkgs) into:')
    print(f'  {k1} ({len(Q1)}): {Path(Q1[0]).name} ... {Path(Q1[-1]).name}')
    print(f'  {k2} ({len(Q2)}): {Path(Q2[0]).name} ... {Path(Q2[-1]).name}')
    # Stage Q2
    for p in Q2:
        s = MODS / Path(p).name
        if s.exists(): shutil.move(str(s), str(STAGE / (k2 + '_' + Path(p).name)))
    state[k1] = Q1
    state[k2] = Q2
    state['active'] = k1
    STATE.write_text(json.dumps(state))
    print(f'{k1} active ({len(Q1)} pkgs). Launch:')
    print('  Loads   -> culprit in ' + k2 + ' -> python split_next.py swap')
    print('  Crashes -> culprit in ' + k1 + ' -> python split_next.py split')

elif sys.argv[1:] == ['swap']:
    # Figure out sibling: A1<->A2, A1_1<->A1_2, etc.
    if cur_key.endswith('_1'):
        nxt_key = cur_key[:-2] + '_2'
    elif cur_key.endswith('_2'):
        nxt_key = cur_key[:-2] + '_1'
    elif cur_key == 'A1':
        nxt_key = 'A2'
    elif cur_key == 'A2':
        nxt_key = 'A1'
    else:
        nxt_key = 'B' if cur_key == 'A' else 'A'
    nxt = state.get(nxt_key)
    if not nxt:
        print(f'No sibling found for {cur_key}'); sys.exit(1)
    # Stage current
    for p in cur:
        s = MODS / Path(p).name
        if s.exists(): shutil.move(str(s), str(STAGE / (cur_key + '_' + Path(p).name)))
    # Restore next
    for p in nxt:
        s = STAGE / (nxt_key + '_' + Path(p).name)
        if s.exists(): shutil.move(str(s), str(MODS / Path(p).name))
    state['active'] = nxt_key
    STATE.write_text(json.dumps(state))
    print(f'{nxt_key} active ({len(nxt)} pkgs):')
    print(f'  {Path(nxt[0]).name} ... {Path(nxt[-1]).name}')
    print('Launch. Crash=culprit here.')
