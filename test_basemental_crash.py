import shutil
from pathlib import Path

MODS = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\Mods')
TEMP = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\TEMP_TEST')
TEMP.mkdir(exist_ok=True)

to_test = [
    'Basemental Drugs.package',
    'Basemental Gambling.package',
]

for name in to_test:
    src = MODS / name
    if src.exists():
        mb = src.stat().st_size // 1024 // 1024
        shutil.move(str(src), str(TEMP / name))
        print(f'Moved {mb}MB: {name}')
    else:
        print(f'Not found: {name}')

remaining = list(MODS.glob('Basemental*.package'))
print(f'Basemental packages still in Mods: {len(remaining)}')
for r in remaining:
    print(f'  {r.name}')
print()
print('Launch the game. If it loads -> Basemental packages were the crash.')
print('Restore: python test_basemental_crash.py restore')

import sys
if len(sys.argv) > 1 and sys.argv[1] == 'restore':
    for name in to_test:
        src = TEMP / name
        if src.exists():
            shutil.move(str(src), str(MODS / name))
            print(f'Restored: {name}')
    try:
        TEMP.rmdir()
    except:
        pass
    print('Done')
