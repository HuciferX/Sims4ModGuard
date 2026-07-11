from pathlib import Path

MODS = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\Mods')

# Check Resource.cfg
cfg = MODS / 'Resource.cfg'
print('=== Resource.cfg ===')
if cfg.exists():
    print(cfg.read_text())
else:
    print('MISSING - game only loads from root Mods folder!')

print()
# Check where TSR archives live
print('=== TSR Archive folder depths ===')
for p in sorted(MODS.rglob('tsrarchive*.package')):
    rel = p.relative_to(MODS)
    depth = len(rel.parts) - 1
    folder = str(rel.parts[0]) if depth > 0 else '[root]'
    print(f'  depth={depth}  folder={folder}')

print()
# Large packages depth check
print('=== Top 10 largest packages - their depth ===')
pkgs = [p for p in MODS.rglob('*.package') if 'MODS_DISABLED' not in p.parts]
for p in sorted(pkgs, key=lambda x: x.stat().st_size, reverse=True)[:10]:
    rel = p.relative_to(MODS)
    depth = len(rel.parts) - 1
    folder = str(rel.parts[0]) if depth > 0 else '[root]'
    mb = p.stat().st_size // 1024 // 1024
    print(f'  depth={depth}  {mb}MB  {folder}/{p.name}')
