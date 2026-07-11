"""
Find the exact CC packages causing tuning_loaded_callback errors.
Scans for packages containing the known tuning conflict signatures.
"""
import struct, time
from pathlib import Path
from datetime import datetime, timezone

MODS = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\Mods')
PATCH_DATE = datetime(2026, 2, 3, tzinfo=timezone.utc)

# Byte signatures from tuning that causes _tuning_loaded_callback errors in 1.121
CONFLICT_SIGS = [
    b'object_reservation_tests',
    b'provided_posture_type',
    b'_super_affordances',       # some versions of this still break
    b'reservation_tests',
]

packages = [
    p for p in MODS.rglob('*.package')
    if 'MODS_DISABLED' not in p.parts
]

print(f"Scanning {len(packages):,} packages for tuning conflicts...")
print(f"This may take a few minutes on {len(packages):,} files.\n")

DBPF = b'DBPF'
start = time.time()
culprits = []
old_culprits = []  # pre-patch, have conflict sigs
clean = 0
errors = 0

for i, pkg in enumerate(packages):
    if i % 1000 == 0 and i > 0:
        elapsed = time.time() - start
        print(f"  {i:,}/{len(packages):,} scanned... ({elapsed:.0f}s)")

    try:
        data = pkg.read_bytes()
    except Exception:
        errors += 1
        continue

    if len(data) < 96 or data[:4] != DBPF:
        continue  # skip corrupt

    found_sigs = []
    for sig in CONFLICT_SIGS:
        if sig in data:
            found_sigs.append(sig.decode('ascii', errors='replace'))

    if found_sigs:
        mod_time = datetime.fromtimestamp(pkg.stat().st_mtime, tz=timezone.utc)
        is_old = mod_time < PATCH_DATE
        culprits.append({
            'name': pkg.name,
            'path': pkg,
            'sigs': found_sigs,
            'size_kb': len(data) // 1024,
            'mod_date': mod_time.date(),
            'pre_patch': is_old,
        })
        if is_old:
            old_culprits.append(culprits[-1])
    else:
        clean += 1

elapsed = time.time() - start
print(f"\nDone in {elapsed:.1f}s")
print(f"Total: {len(packages):,} | Conflicts: {len(culprits)} | Pre-patch: {len(old_culprits)} | Clean: {clean:,}")

print()
print("=" * 70)
print(f"TUNING CONFLICT PACKAGES ({len(culprits)} total)")
print("  [PRE] = modified before patch 1.121 (Feb 3 2026) = highest risk")
print("=" * 70)

# Sort: pre-patch first, then by name
culprits.sort(key=lambda x: (not x['pre_patch'], x['name'].lower()))

for c in culprits:
    flag = "[PRE]" if c['pre_patch'] else "[NEW]"
    print(f"  {flag} {c['name'][:60]}")
    print(f"        {c['size_kb']}KB  |  {c['mod_date']}  |  sigs: {', '.join(c['sigs'][:2])}")

print()
print("=" * 70)
print("RECOMMENDATION")
print("=" * 70)
if old_culprits:
    print(f"  {len(old_culprits)} packages predate patch 1.121 AND have conflict signatures.")
    print("  These are the most likely cause of your kitchen/object issues.")
    print("  Quarantine them and clear caches, then test the game.")
    print()
    print("  PRE-PATCH CULPRITS:")
    for c in old_culprits[:20]:
        print(f"    {c['name']}")
else:
    print("  No pre-patch culprit packages found.")
    print("  All conflict packages are newer than patch 1.121.")
    print("  The errors may be from posture system changes only — try clearing caches.")
