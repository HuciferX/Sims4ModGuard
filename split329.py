import shutil, json, sys
from pathlib import Path

MODS  = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\Mods')
ST    = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\CHUNK5B_STAGE')
ST2   = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\SPLIT329_STAGE')
ST2FILE = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\split329_state.json')

def active():
    return sorted([str(p) for p in MODS.rglob('*.package')
                   if all(x not in str(p) for x in ['MODS_DISABLED','CHUNK_STAGE','CHUNK5B','SPLIT329'])],
                  key=lambda x: Path(x).name.lower())

if sys.argv[1:] == ['init']:
    pkgs = active()
    half = len(pkgs)//2
    A, B = pkgs[:half], pkgs[half:]
    print(f'{len(pkgs)} active | A: {Path(A[0]).name}...{Path(A[-1]).name}')
    print(f'                 B: {Path(B[0]).name}...{Path(B[-1]).name}')
    ST2.mkdir(exist_ok=True)
    for p in B: shutil.move(p, str(ST2 / Path(p).name))
    ST2FILE.write_text(json.dumps({'A': A, 'B': B, 'active': 'A'}))
    print(f'A active ({len(A)} pkgs). Launch → loads=culprit in B, crash=culprit in A')

elif sys.argv[1:] == ['swap']:
    state = json.loads(ST2FILE.read_text())
    cur = state['active']
    nxt = 'B' if cur == 'A' else 'A'
    for p in state[cur]:
        s = MODS / Path(p).name
        if s.exists(): shutil.move(str(s), str(ST2 / Path(p).name))
    for p in state[nxt]:
        s = ST2 / Path(p).name
        if s.exists(): shutil.move(str(s), str(MODS / Path(p).name))
    state['active'] = nxt
    ST2FILE.write_text(json.dumps(state))
    pkgs = state[nxt]
    print(f'{nxt} active ({len(pkgs)} pkgs): {Path(pkgs[0]).name}...{Path(pkgs[-1]).name}')
    print('Launch. Crash=culprit here. Loads=culprit in other half.')

elif sys.argv[1:] == ['restore']:
    for f in ST2.rglob('*.package'):
        shutil.move(str(f), str(MODS / f.name))
    try: ST2.rmdir()
    except: pass
    ST2FILE.unlink(missing_ok=True)
    print('Restored', len(active()), 'active')
