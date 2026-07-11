import sys
sys.path.insert(0, r'C:\Users\merli\Sims4ModGuard')
from sims4modguard.quarantine import QuarantineManager
from sims4modguard.cache_manager import clear_caches
from pathlib import Path

S4 = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4')
qm = QuarantineManager(S4)
entries = qm.get_quarantined()

# Restore ONLY plzsaysike packages - they contained actual CC objects placed in the save
# Keep WW animations and broken Scumbumbo scripts quarantined
to_restore = [e for e in entries if 'plzsaysike' in e['name'].lower()]

print(f'Restoring {len(to_restore)} plzsaysike CC packages:')
restored = 0
for e in to_restore:
    ok = qm.restore(e['destination'])
    status = 'OK' if ok else 'FAIL'
    print(f'  [{status}]  {e["name"]}')
    if ok:
        restored += 1

print()
still = qm.get_quarantined()
print(f'Still quarantined ({len(still)}) - correctly kept out:')
for e in still:
    print(f'  {e["name"]}')

print()
result = clear_caches(S4, verbose=False)
mb = result['bytes_freed'] // (1024*1024)
print(f'Cleared {mb} MB cache')
print()
print(f'Restored {restored} plzsaysike files.')
print('The 2858 errors are EA vanilla bugs - cannot be fixed by mod removal.')
print('Your CC furniture should be back. Launch the game to check.')
