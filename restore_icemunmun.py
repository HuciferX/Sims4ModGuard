import shutil, sys
from pathlib import Path

DIS  = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\MODS_DISABLED')
MODS = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\Mods')

src = DIS / 'icemunmun_CandleMaking_Script.ts4script'
if src.exists():
    dst = MODS / src.name
    shutil.copy2(str(src), str(dst))
    kb = src.stat().st_size // 1024
    print(f'Restored: {src.name} ({kb}KB)')
    print('Basemental should now find HOMESTASH_AFFORDANCES and NEW_AFFORDANCES')
else:
    print('icemunmun_CandleMaking_Script not found in MODS_DISABLED')

sys.path.insert(0, r'C:\Users\merli\Sims4ModGuard')
from sims4modguard.cache_manager import clear_caches
S4 = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4')
result = clear_caches(S4, verbose=False)
freed = result['bytes_freed'] // 1024 // 1024
count = len(result['files'])
print(f'Cleared {count} cache files ({freed} MB)')
