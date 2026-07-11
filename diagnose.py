"""Diagnose what was quarantined and check for CC load errors."""
import json, sys, re
from pathlib import Path

S4 = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4')

# ── Quarantine manifest ───────────────────────────────────────────────────────
manifest_path = S4 / 'MODS_DISABLED' / '_quarantine_manifest.json'
print("=" * 60)
print("QUARANTINE MANIFEST")
print("=" * 60)
if manifest_path.exists():
    entries = json.loads(manifest_path.read_text(encoding='utf-8'))
    active = [e for e in entries if not e.get('restored')]
    print(f"Total quarantined: {len(active)}")
    print()
    for e in active:
        print(f"  FILE:   {e['name']}")
        print(f"  REASON: {e['reason']}")
        print(f"  TIME:   {e['timestamp'][:19]}")
        print()
else:
    print("No manifest found")

# ── Current Mods folder scan ─────────────────────────────────────────────────
print("=" * 60)
print("CURRENT MODS FOLDER CONTENTS")
print("=" * 60)
mods = S4 / 'Mods'
scripts  = list(mods.rglob('*.ts4script'))
packages = list(mods.rglob('*.package'))
print(f"  Scripts:  {len(scripts)}")
print(f"  Packages: {len(packages):,}")
print()

# ── MODS_DISABLED folder scan ────────────────────────────────────────────────
disabled = S4 / 'MODS_DISABLED'
if disabled.exists():
    dis_files = [f for f in disabled.rglob('*') if f.is_file() and f.suffix in ('.package', '.ts4script')]
    print(f"  MODS_DISABLED: {len(dis_files)} mod files")

# ── lastException.txt analysis ────────────────────────────────────────────────
print()
print("=" * 60)
print("LAST EXCEPTION LOG ANALYSIS")
print("=" * 60)

log_path = S4 / 'lastException.txt'
if not log_path.exists():
    print("  No lastException.txt found - game may have loaded cleanly!")
else:
    content = log_path.read_text(encoding='utf-8', errors='replace')
    # Count reports
    report_count = content.count('<report>')
    print(f"  Error reports: {report_count}")

    # Check tuning
    if 'TuningLoadFinished' in content:
        finished = 'true' in content.lower().split('tuningloadfinished')[1][:20].lower()
        print(f"  Tuning finished: {finished}")

    # Find CC-related errors (package files, object tuning)
    cc_patterns = [
        'object_reservation_tests',
        'provided_posture_type',
        'CAS_',
        'hair',
        'kitchen',
        'CUSTOM',
        'cannot find',
        'KeyError',
    ]

    print()
    print("  CC-related errors found in log:")
    lines = content.splitlines()
    shown = 0
    for line in lines:
        ll = line.lower()
        for pat in cc_patterns:
            if pat.lower() in ll and shown < 20:
                print(f"    {line.strip()[:120]}")
                shown += 1
                break

    if shown == 0:
        print("    None found")

    # Show unique error types
    errors = re.findall(r'<type>(.*?)</type>', content)
    desync = re.findall(r'<categoryid>(.*?)</categoryid>', content)
    print()
    unique_cats = list(set(desync[:100]))[:15]
    if unique_cats:
        print(f"  Error categories (first 15 unique):")
        for c in sorted(unique_cats):
            print(f"    {c}")

print()
print("=" * 60)
print("DIAGNOSIS")
print("=" * 60)

# Check for common culprits
if packages:
    # Sample a few package names to spot kitchen/hair CC
    pkg_names = [p.name.lower() for p in packages]
    hair_pkgs = [p.name for p in packages if 'hair' in p.name.lower()]
    kitchen_pkgs = [p.name for p in packages if 'kitchen' in p.name.lower() or 'counter' in p.name.lower() or 'cabinet' in p.name.lower()]
    
    print(f"  Hair-related packages in Mods: {len(hair_pkgs)}")
    for n in hair_pkgs[:10]:
        print(f"    {n}")
    print()
    print(f"  Kitchen-related packages in Mods: {len(kitchen_pkgs)}")
    for n in kitchen_pkgs[:10]:
        print(f"    {n}")
