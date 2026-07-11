"""
Dry-run: scan all packages and report which ones have broken 1.121 tuning.
Does NOT modify any files.
"""
import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sims4modguard.dbpf_patcher import scan_and_patch_folder

MODS = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\Mods')

print("DRY-RUN SCAN: Finding packages with broken 1.121 tuning attributes...")
print("(No files will be modified)")
print()

start = time.time()
calls = [0]

def progress(current, total):
    calls[0] += 1
    if calls[0] % 5 == 0 or current == total:
        pct = int(current / total * 100)
        print(f"  [{pct:3d}%] {current:,}/{total:,}", end='\r')

result = scan_and_patch_folder(MODS, dry_run=True, progress_callback=progress)
elapsed = time.time() - start

print(f"\nDone in {elapsed:.1f}s")
print()
print("=" * 60)
print("RESULTS")
print("=" * 60)
print(f"  Scanned:          {result['scanned']:,} packages")
print(f"  With broken attrs: {result['found_files']} packages")
print(f"  Resources to fix:  {result['patched_resources']}")
print()

if result['found_files'] == 0:
    print("  No broken packages found.")
    print("  The issue may be from a different source.")
else:
    print(f"  PACKAGES TO PATCH ({result['found_files']}):")
    for name in result['patched_names']:
        print(f"    {name}")

if result['failed']:
    print()
    print(f"  ERRORS ({len(result['failed'])}):")
    for f in result['failed'][:10]:
        print(f"    {f}")
