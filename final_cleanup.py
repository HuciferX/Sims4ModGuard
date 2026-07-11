import sys
sys.path.insert(0, r'C:\Users\merli\Sims4ModGuard')
from sims4modguard.quarantine import QuarantineManager
from sims4modguard.cache_manager import clear_caches
from pathlib import Path

S4 = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4')
MODS = S4 / 'Mods'
qm = QuarantineManager(S4)

# Quarantine last remaining plzsaysike file
found = list(MODS.rglob('plzsaysike_betterkitchenappliances.package'))
if found:
    pkg = found[0]
    dest = qm.quarantine(pkg, 'plzsaysike kitchen appliances: outdated kitchen object posture tuning', auto=True)
    print(f'Quarantined: {pkg.name}')
else:
    print('plzsaysike_betterkitchenappliances not found (already quarantined)')

# Delete stale lastException.txt so we get a fresh clean log on next launch
log = S4 / 'lastException.txt'
if log.exists():
    log.unlink()
    print('Deleted stale lastException.txt — next launch creates a clean log')

result = clear_caches(S4, verbose=False)
mb = result['bytes_freed'] // (1024 * 1024)
print(f'Cleared {mb} MB cache')
print()
print('ALL DONE. Summary of what was quarantined this session:')
entries = qm.get_quarantined()
for e in entries:
    print(f'  {e["name"]}')
