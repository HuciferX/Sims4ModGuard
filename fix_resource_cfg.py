"""
The crash happened because the good Resource.cfg scanned depth-1 subfolders,
and Basemental Drugs.package (87 MB) in Mods/Basemental_Drugs/ was crashing
the DBPF reader.

Fix:
1. Move all packages from Mods/Basemental_Drugs/ to Mods/ (depth-0)
2. Restore the good Resource.cfg (no BOM, 5-level subfolder scanning)
3. Now TSRLibrary CC will also load (depth-1, tsrarchive*.package)
"""
import shutil
from pathlib import Path

S4   = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4')
MODS = S4 / 'Mods'
BM   = MODS / 'Basemental_Drugs'

print('Step 1: Move Basemental packages to root Mods/')
moved = 0
if BM.exists():
    for f in list(BM.rglob('*.package')):
        dest = MODS / f.name
        if dest.exists():
            print(f'  SKIP (already at root): {f.name}')
            continue
        shutil.move(str(f), str(dest))
        print(f'  Moved: {f.name}')
        moved += 1
    print(f'  Moved {moved} packages to root Mods/')
    # Keep the folder (scripts and logs live there)
else:
    print('  Basemental_Drugs folder not found')

print()
print('Step 2: Restore good Resource.cfg (no BOM, 5 levels)')
good = MODS / 'Resource_GOOD.cfg'
cfg  = MODS / 'Resource.cfg'

if good.exists():
    shutil.copy2(str(good), str(cfg))
    print('  Restored Resource_GOOD.cfg -> Resource.cfg')
    print('  Contents:')
    print(cfg.read_text(encoding='ascii', errors='replace'))
else:
    # Write it fresh
    content = (
        'Priority 500\r\n'
        'PackedFile *.package\r\n'
        'PackedFile */*.package\r\n'
        'PackedFile */*/*.package\r\n'
        'PackedFile */*/*/*.package\r\n'
        'PackedFile */*/*/*/*.package\r\n'
        'PackedFile */*/*/*/*/*.package\r\n'
    )
    cfg.write_bytes(content.encode('ascii'))
    print('  Written fresh Resource.cfg (no BOM, 5 levels)')

print()
# Verify depth distribution
from collections import Counter
depth_count = Counter()
for p in MODS.rglob('*.package'):
    if 'MODS_DISABLED' in p.parts: continue
    rel = p.relative_to(MODS)
    depth = len(rel.parts) - 1
    depth_count[depth] += 1

print('Packages by depth (should mostly be depth 0 and depth 1 TSRLibrary):')
for d in sorted(depth_count):
    print(f'  depth {d}: {depth_count[d]:,} packages')

print()
print('DONE. On next game launch:')
print('  - Depth-0 packages load (all root CC including Basemental)')
print('  - Depth-1 TSRLibrary loads (all 20 TSR archives)')
print('  - Game should NOT crash')
