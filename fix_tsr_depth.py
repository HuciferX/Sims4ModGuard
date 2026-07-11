"""Move TSR archives from TSRLibrary subfolder to root Mods so they load at depth-0."""
import shutil
from pathlib import Path

S4   = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4')
MODS = S4 / 'Mods'
TSR_LIB = MODS / 'TSRLibrary'

print('Moving TSR archives to root Mods/ (depth-0)...')
moved = 0
if TSR_LIB.exists():
    for f in list(TSR_LIB.glob('*.package')):
        dest = MODS / f.name
        if dest.exists():
            print(f'  SKIP (exists): {f.name}')
            continue
        mb = f.stat().st_size // 1024 // 1024
        shutil.move(str(f), str(dest))
        print(f'  Moved {mb}MB: {f.name}')
        moved += 1
    # Remove empty folder
    try:
        TSR_LIB.rmdir()
        print('  Removed empty TSRLibrary/')
    except:
        remaining = list(TSR_LIB.iterdir())
        print(f'  TSRLibrary still has {len(remaining)} files (not all packages)')
else:
    print('  TSRLibrary folder not found')

print(f'\nMoved {moved} TSR archives to root Mods')

# Restore working (BOM) Resource.cfg so game loads
cfg = MODS / 'Resource.cfg'
bom_content = b'\xef\xbb\xbfPriority 500\r\nPackedFile *.package\r\nPackedFile */*.package\r\nPackedFile */*/*.package\r\n\r\n'
cfg.write_bytes(bom_content)
print('Restored working Resource.cfg (BOM, 3 levels)')

# Count final state
from collections import Counter
depth_count = Counter()
for p in MODS.rglob('*.package'):
    if 'MODS_DISABLED' in p.parts: continue
    depth = len(p.relative_to(MODS).parts) - 1
    depth_count[depth] += 1

print()
print('Final package depths:')
for d in sorted(depth_count):
    print(f'  depth {d}: {depth_count[d]:,} packages')

print()
print('TSR archives are now at depth-0 - they will load even with the BOM Resource.cfg')
print('Launch the game now.')
