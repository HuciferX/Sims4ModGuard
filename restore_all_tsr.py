import shutil
from pathlib import Path

S4   = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4')
MODS = S4 / 'Mods'
TSR  = MODS / 'TSRLibrary'

restored = 0
for stage_name in ['TSR_STAGE', 'TSR_STAGE2']:
    stage = S4 / stage_name
    if stage.exists():
        files = list(stage.rglob('*.package'))
        print(f'{stage_name}: {len(files)} files')
        for f in files:
            if 'tsrarchive' in f.name.lower():
                dest = TSR / f.name
            else:
                dest = MODS / f.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(dest))
            print(f'  Restored: {f.name}')
            restored += 1
        for sf in S4.glob('*stage*state*.json'):
            sf.unlink(missing_ok=True)
        try:
            stage.rmdir()
        except:
            pass

tsrs = list(MODS.rglob('tsrarchive*.package'))
mb   = sum(t.stat().st_size for t in tsrs) // 1024 // 1024
print(f'\nRestored {restored} files. TSR archives in Mods: {len(tsrs)} ({mb} MB)')
print('All CC restored. Game has old Resource.cfg (BOM) - will load without subfolder CC.')
print()
print('The game is loading NOW (old Resource.cfg). When ready, load your save.')
print('The TSRLibrary CC wont show until we fix the subfolder crash issue.')
