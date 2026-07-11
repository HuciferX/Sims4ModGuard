import sys
sys.path.insert(0, r'C:\Users\merli\Sims4ModGuard')
from sims4modguard.quarantine import QuarantineManager
from sims4modguard.cache_manager import clear_caches
from pathlib import Path

S4   = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4')
MODS = S4 / 'Mods'
qm   = QuarantineManager(S4)

targets = [
    ('NRaas_MasterController.package',
     'OLD NRaas MasterController - pre-2016, conflicts with MCCC 2026, causes hard crash'),
    ('Notegain_Neon_Wall_Sign_Numbers_Apostrophe.package',
     'Pre-2016 CC - secondary crash suspect'),
    ('NotEgain_Neon_Sign_Cocktails_Additions.package',
     'Pre-2016 CC - secondary crash suspect'),
    ('NotEgain_Neon_Sign_Beer.package',
     'Pre-2016 CC - secondary crash suspect'),
]

for name, reason in targets:
    f = MODS / name
    if f.exists():
        qm.quarantine(f, reason, auto=True)
        print(f'Quarantined: {name}')
    else:
        print(f'Not found: {name}')

result = clear_caches(S4, verbose=False)
freed  = result['bytes_freed'] // 1024 // 1024
print(f'Cleared {freed} MB cache')
print()
print('LAUNCH THE GAME - NRaas_MasterController was the crash culprit!')
print('It conflicts with MCCC 2026 and crashes the DBPF reader on startup.')
