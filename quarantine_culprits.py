"""
Quarantine all pre-patch packages with tuning conflict signatures.
Adds them to the manifest so they can be restored via the app.
"""
import sys, time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from sims4modguard.quarantine import QuarantineManager
from sims4modguard.cache_manager import clear_caches

S4    = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4')
MODS  = S4 / 'Mods'
PATCH = datetime(2026, 2, 3, tzinfo=timezone.utc)

CONFLICT_SIGS = [
    b'object_reservation_tests',
    b'provided_posture_type',
    b'reservation_tests',
]

DBPF = b'DBPF'

qm = QuarantineManager(S4)

packages = [
    p for p in MODS.rglob('*.package')
    if 'MODS_DISABLED' not in p.parts
]

print(f"Scanning {len(packages):,} packages for pre-patch tuning conflicts...")
start = time.time()
to_quarantine = []

for pkg in packages:
    try:
        data = pkg.read_bytes()
    except Exception:
        continue

    if len(data) < 96 or data[:4] != DBPF:
        continue

    mod_time = datetime.fromtimestamp(pkg.stat().st_mtime, tz=timezone.utc)
    if mod_time >= PATCH:
        continue  # Not pre-patch, skip

    for sig in CONFLICT_SIGS:
        if sig in data:
            to_quarantine.append((pkg, sig.decode('ascii')))
            break

print(f"Found {len(to_quarantine)} pre-patch conflict packages in {time.time()-start:.1f}s")
print()

if not to_quarantine:
    print("Nothing to quarantine.")
else:
    print("Quarantining:")
    moved = 0
    for pkg, sig in to_quarantine:
        reason = f"Pre-1.121 tuning conflict: contains '{sig}' (causes _tuning_loaded_callback crash)"
        dest = qm.quarantine(pkg, reason, auto=True)
        if dest:
            print(f"  [OK] {pkg.name}")
            moved += 1
        else:
            print(f"  [!!] FAILED: {pkg.name}")

    print()
    print(f"Quarantined: {moved} / {len(to_quarantine)} packages")

    # Clear caches
    print()
    print("Clearing Sims 4 caches...")
    result = clear_caches(S4, verbose=True)
    mb = result['bytes_freed'] // (1024 * 1024)
    print(f"  Cleared {len(result['files'])} cache files ({mb} MB freed)")

    print()
    print("=" * 60)
    print("DONE. Next steps:")
    print("=" * 60)
    print(f"  1. Launch The Sims 4")
    print(f"  2. Kitchen CC and hair should now load correctly")
    print(f"  3. If issues remain, check the LOG ANALYZER tab in the app")
    print(f"  4. All {moved} quarantined files can be restored in the")
    print(f"     [WR] FIX & REPAIR tab -> [OK] RESTORE ALL QUARANTINED")
    print()
    print("  Quarantined packages (candles/sofas with broken seating tuning):")
    for pkg, sig in to_quarantine:
        print(f"    {pkg.name}")
