"""Quarantine plzsaysike library packages + WW animation packs that break 1.121."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sims4modguard.quarantine import QuarantineManager
from sims4modguard.cache_manager import clear_caches

S4   = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4')
MODS = S4 / 'Mods'
qm   = QuarantineManager(S4)

# plzsaysike library packages inject outdated posture/reservation tuning into
# base game objects (fish bowl, stove, easel, crib, etc.) causing 1.121 _tuning_loaded_callback failures
QUARANTINE_PATTERNS = [
    # plzsaysike pose libraries — override base game object posture tuning
    'plzsaysikeLibraryMainMod.package',
    'plzsaysikeLibraryBaseGame.package',
    'plzsaysikeLibraryBaseGame_Toddler.package',
    'plzsaysikelibraryDiscoverUniversity_large.package',
    'plzsaysikelibraryDiscoverUniversity_Small.package',
    'plzsaysikelibraryGetTogether.package',
    'plzsaysikelibraryGetToWork.package',
    'plzsaysikelibraryRealmOfMagic_large.package',
    'plzsaysikelibraryRealmOfMagic_small.package',
    'plzsaysikelibraryStrangervile.package',
    # WickedWhims animation packs (WW not installed — these are dead weight)
    'WW_CIPHER UVS_Animations.package',
    'WW_E404P_Animations.package',
    'WW_Fruitydelicious_Animations.package',
    'WW_GreyNaya_Animations.package',
    'WW_MOTHERLODESIMS_Animations.package',
    'WW_SexyLunella_Animations.package',
    'WW_Whoonky_Animations.package',
    # WW AnimationS from OLL (AP = Adult Poses/Animations, WW dependent)
    'OLL Animations (AP).package',
]

REASONS = {
    'plzsaysike': 'plzsaysike pose library: injects outdated provided_posture_type / object_reservation_tests into base game objects — causes _tuning_loaded_callback failures in 1.121 on fish bowl, stove, easel, crib, pear, etc.',
    'WW_':        'WickedWhims animation pack: requires WW core (not installed) — dead weight, may cause injection failures',
    'OLL ':       'OLL animation pack (AP = Adult/WW): requires WickedWhims — not functional without WW core',
}

moved = 0
skipped = 0
for name in QUARANTINE_PATTERNS:
    pkg = MODS / name
    if not pkg.exists():
        # Try recursive search (might be in subfolder)
        found = list(MODS.rglob(name))
        if found:
            pkg = found[0]
        else:
            print(f'  [--] Not found: {name}')
            skipped += 1
            continue

    reason = 'plzsaysike pose library' if 'plzsaysike' in name else ('WW animation pack' if 'WW_' in name or 'OLL' in name else 'outdated library')
    for prefix, r in REASONS.items():
        if prefix in name:
            reason = r
            break

    dest = qm.quarantine(pkg, reason, auto=True)
    if dest:
        print(f'  [OK] Quarantined: {name}')
        moved += 1
    else:
        print(f'  [!!] Failed: {name}')

print()
print(f'Quarantined: {moved}  Skipped (not found): {skipped}')

print()
print('Clearing caches...')
result = clear_caches(S4, verbose=False)
mb = result['bytes_freed'] // (1024*1024)
print(f'Cleared {mb} MB')

print()
print('DONE. Launch the game and check if errors are gone.')
print('Expected: fish bowl, stove, pear, crib errors should disappear.')
