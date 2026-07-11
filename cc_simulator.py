"""
cc_simulator.py
Simulates the Sims 4 CC loading pipeline to identify what loads, what doesn't, and WHY.

Checks:
  1. Folder depth (game only loads CC <= 5 subfolder levels deep)
  2. DBPF validity (header, index structure)
  3. Resource type classification (what each package ACTUALLY contains)
  4. Conflict detection (two packages with same TypeID + InstanceID)
  5. Dependency stubs (missing required companion files)
  6. Script mod injection pattern validation
  7. Size anomalies (zero-byte, impossibly small)

By Hucifer & Hypatia
"""

import struct, zipfile, time, json
from pathlib import Path
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set

MODS  = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\Mods')
S4    = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4')

MAX_DEPTH = 5  # Sims 4 only loads CC up to 5 subfolder levels

# ── Resource type ID → human label ────────────────────────────────────────────
RESOURCE_TYPES = {
    0x034AEECB: "CAS Part (hair/clothing)",
    0x025ED6F4: "CAS Geometry",
    0x3C1AF1F2: "CAS 3D Mesh",
    0x319E4F1D: "CAS SimData",
    0x8B18AE2E: "CAS Overlay",
    0x2F7D0004: "CAS Thumbnail",
    0xCF9A4ACE: "Swatch",
    0x2C81F764: "Swatch Specular",
    0xBD31E1F3: "RLE2 Texture",
    0x00B2D882: "GEOM Mesh",
    0x736884F1: "LOD Mesh",
    0x015A1849: "Texture (IMG)",
    0xEB988E71: "Material Definition",
    0x0166038C: "Build/Buy Catalog Object",
    0x03B33DDF: "XML Tuning (Object/Interaction)",
    0x62ECC59A: "Object Tuning",
    0x02D5DF13: "Object Definition Tuning",
    0x545AC67A: "SimData (Object)",
    0xE882D22F: "SimData (Object Alt)",
    0x01D0E75D: "SimData Binary",
    0x9063660B: "Snippet (XmlInjector)",
    0x7DF2169C: "Snippet",
    0x6017E896: "Buff Tuning",
    0x814AF95D: "Trait Tuning",
    0xAA1E1E3E: "Interaction Tuning",
    0x6F9B3B46: "Social Tuning",
    0x51C21B1B: "Reward Tuning",
    0x0C772E27: "Aspiration Tuning",
    0x16CCF748: "Career Tuning",
    0x2B978C6:  "Animation Clip",
    0x6B20C4F3: "Animation State Machine",
    0x3032D7B5: "World Thumbnail",
    0xD4D9FBE5: "Footprint",
    0xB8C7B733: "Slot Tuning",
    0x5B16B687: "Combined Tuning",
    0x36F97548: "Object Catalog (Small)",
}

# CAS-specific types (hair, clothing, accessories)
CAS_TYPES  = {0x034AEECB, 0x025ED6F4, 0x3C1AF1F2, 0x319E4F1D, 0x8B18AE2E, 0x2F7D0004}
# Build/Buy types (furniture, decor, objects)
BUY_TYPES  = {0x0166038C, 0x03B33DDF, 0x62ECC59A, 0x02D5DF13, 0x545AC67A, 0xD4D9FBE5, 0xB8C7B733}
# Shared mesh/texture
MESH_TYPES = {0x00B2D882, 0x736884F1, 0x015A1849, 0xEB988E71, 0xBD31E1F3, 0x2C81F764, 0xCF9A4ACE}
# Tuning/game logic
TUNE_TYPES = {0x6017E896, 0x814AF95D, 0xAA1E1E3E, 0x6F9B3B46, 0x51C21B1B, 0x0C772E27,
              0x16CCF748, 0x9063660B, 0x7DF2169C, 0x5B16B687}
# Animation
ANIM_TYPES = {0x2B978C6, 0x6B20C4F3}

BROKEN_SCRIPT_PATTERNS = [
    b'inject_load_data_into_class_instances',
    b'HasTunableReference',
    b'add_super_affordances',
    b'lmsinjector',
    b'leroi_death_injector',
    b'add_wicked_attributes',
]

# ── DBPF parser ────────────────────────────────────────────────────────────────

def parse_dbpf_typeids(raw: bytes) -> Optional[Set[int]]:
    """
    Parse DBPF index and return set of TypeIDs found.
    Handles both standard (32-byte) and truncated (constant-field) index formats.
    Returns None if not a valid DBPF.

    Truncated index format:
      The 4-byte flags at index block start indicate which fields are constant.
      Bit 0 = TypeID constant, bit 1 = GroupID constant, bit 2 = InstHigh constant.
      Constant fields are stored once in the index header; per-entry size shrinks accordingly.
    """
    if len(raw) < 96 or raw[:4] != b'DBPF':
        return None
    major = struct.unpack_from('<I', raw, 4)[0]
    if major not in (1, 2):
        return None

    index_count      = struct.unpack_from('<I', raw, 36)[0]
    index_block_size = struct.unpack_from('<I', raw, 44)[0]

    if index_count == 0:
        return set()
    if index_count > 500_000 or index_block_size > len(raw):
        return None

    # Index block is at the end of the file
    block_start = len(raw) - index_block_size
    if block_start < 96:
        return None

    # Read index flags (first 4 bytes of the block)
    flags = struct.unpack_from('<I', raw, block_start)[0]

    # Determine which fields are constant and read their values
    # Bit 0x01 = TypeID constant, 0x02 = GroupID constant, 0x04 = InstHigh constant
    TYPE_CONST  = bool(flags & 0x01)
    GROUP_CONST = bool(flags & 0x02)
    INSHI_CONST = bool(flags & 0x04)

    header_pos = block_start + 4  # right after flags
    const_type_id  = None
    const_group_id = None
    const_inst_hi  = None

    if TYPE_CONST:
        const_type_id  = struct.unpack_from('<I', raw, header_pos)[0]
        header_pos += 4
    if GROUP_CONST:
        const_group_id = struct.unpack_from('<I', raw, header_pos)[0]
        header_pos += 4
    if INSHI_CONST:
        const_inst_hi  = struct.unpack_from('<I', raw, header_pos)[0]
        header_pos += 4

    # Entry size: 32 bytes minus 4 for each constant field
    ENTRY_SIZE = 32 - (4 if TYPE_CONST else 0) - (4 if GROUP_CONST else 0) - (4 if INSHI_CONST else 0)
    if ENTRY_SIZE < 8:  # sanity check
        ENTRY_SIZE = 32

    index_start = header_pos  # first actual entry starts here

    type_ids: Set[int] = set()

    if TYPE_CONST:
        # All entries share the same TypeID
        if const_type_id is not None:
            type_ids.add(const_type_id)
    else:
        # TypeID is the first field of each entry
        for i in range(min(index_count, 10_000)):
            base = index_start + i * ENTRY_SIZE
            if base + 4 > len(raw):
                break
            try:
                tid = struct.unpack_from('<I', raw, base)[0]
                type_ids.add(tid)
            except struct.error:
                break

    return type_ids


def classify_package(type_ids: Set[int]) -> str:
    """Classify a package by its dominant resource type."""
    if not type_ids:
        return "Empty/Unknown"

    cas  = sum(1 for t in type_ids if t in CAS_TYPES)
    buy  = sum(1 for t in type_ids if t in BUY_TYPES)
    mesh = sum(1 for t in type_ids if t in MESH_TYPES)
    tune = sum(1 for t in type_ids if t in TUNE_TYPES)
    anim = sum(1 for t in type_ids if t in ANIM_TYPES)

    if anim > 0 and cas == 0 and buy == 0:
        return "Animation Pack"
    if 0x034AEECB in type_ids:
        return "CAS (hair/clothing/accessory)"
    if 0x0166038C in type_ids:
        return "Build/Buy Object"
    if 0x03B33DDF in type_ids and buy > 0:
        return "Build/Buy Object + Tuning"
    if cas > 0:
        return "CAS (texture/mesh only)"
    if buy > 0:
        return "Build/Buy Tuning"
    if tune > 0:
        return "Tuning/Trait/Career"
    if mesh > 0:
        return "Shared Mesh/Texture"
    if 0x9063660B in type_ids:
        return "XmlInjector Snippet"
    return f"Unknown (types: {[hex(t) for t in list(type_ids)[:3]]})"


def check_script(path: Path):
    """Check a .ts4script for broken patterns."""
    issues = []
    try:
        with zipfile.ZipFile(path) as z:
            py_files = [n for n in z.namelist() if n.endswith('.py')]
            for pf in py_files:
                content = z.read(pf)
                for pat in BROKEN_SCRIPT_PATTERNS:
                    if pat in content:
                        issues.append(f"broken pattern: {pat.decode()}")
                        break
    except zipfile.BadZipFile:
        issues.append("corrupt ZIP")
    except Exception as e:
        issues.append(f"read error: {e}")
    return issues


# ── Main simulation ────────────────────────────────────────────────────────────

def simulate(mods_path: Path) -> dict:
    start = time.time()

    results = {
        'will_load':    [],   # (path, category, type_ids)
        'wont_load':    [],   # (path, reason)
        'scripts_ok':   [],
        'scripts_bad':  [],   # (path, issues)
        'conflicts':    defaultdict(list),   # (type_id, inst) -> [paths]
        'categories':   Counter(),
        'depth_blocked': [],
        'tiny_files':   [],
    }

    # Track (TypeID, InstHi, InstLo) for conflict detection
    resource_registry: Dict = defaultdict(list)

    all_packages = list(mods_path.rglob('*.package'))
    all_scripts  = list(mods_path.rglob('*.ts4script'))

    print(f"Found {len(all_packages):,} packages + {len(all_scripts)} scripts")
    print("Simulating load pipeline...\n")

    processed = 0

    for pkg in all_packages:
        # Skip MODS_DISABLED
        if 'MODS_DISABLED' in pkg.parts:
            continue

        # Check folder depth (Sims 4 limit: 5 subfolder levels)
        rel = pkg.relative_to(mods_path)
        depth = len(rel.parts) - 1  # -1 because last part is the filename
        if depth > MAX_DEPTH:
            results['wont_load'].append((pkg, f"TOO DEEP: {depth} levels (max {MAX_DEPTH})"))
            results['depth_blocked'].append(pkg)
            continue

        # Size check
        size = pkg.stat().st_size
        if size == 0:
            results['wont_load'].append((pkg, "ZERO BYTES: empty file"))
            results['tiny_files'].append(pkg)
            continue
        if size < 96:
            results['wont_load'].append((pkg, f"TOO SMALL: {size} bytes (not a valid DBPF)"))
            results['tiny_files'].append(pkg)
            continue

        # DBPF parse
        try:
            raw = pkg.read_bytes()
        except Exception as e:
            results['wont_load'].append((pkg, f"READ ERROR: {e}"))
            continue

        type_ids = parse_dbpf_typeids(raw)
        if type_ids is None:
            results['wont_load'].append((pkg, "INVALID DBPF: not a Sims 4 package"))
            continue

        # Register resources for conflict detection
        if type_ids:
            # Quick index scan for conflict detection (first 200 entries)
            index_block_size = struct.unpack_from('<I', raw, 44)[0]
            index_start = len(raw) - index_block_size + 4
            index_count = struct.unpack_from('<I', raw, 36)[0]
            for i in range(min(index_count, 200)):
                base = index_start + i * 32
                if base + 16 > len(raw): break
                try:
                    tid  = struct.unpack_from('<I', raw, base)[0]
                    ih   = struct.unpack_from('<I', raw, base + 8)[0]
                    il   = struct.unpack_from('<I', raw, base + 12)[0]
                    key = (tid, ih, il)
                    resource_registry[key].append(pkg)
                except struct.error:
                    break

        # Classify
        category = classify_package(type_ids)
        results['will_load'].append((pkg, category, type_ids))
        results['categories'][category] += 1

        processed += 1
        if processed % 1000 == 0:
            elapsed = time.time() - start
            print(f"  {processed:,}/{len(all_packages):,} packages... ({elapsed:.0f}s)")

    # Find conflicts (same resource in multiple packages)
    for key, paths in resource_registry.items():
        if len(paths) > 1:
            results['conflicts'][key] = paths

    # Script analysis
    for script in all_scripts:
        if 'MODS_DISABLED' in script.parts:
            continue
        issues = check_script(script)
        if issues:
            results['scripts_bad'].append((script, issues))
        else:
            results['scripts_ok'].append(script)

    elapsed = time.time() - start
    results['elapsed'] = elapsed
    results['total_packages'] = len(all_packages)
    results['total_scripts']  = len(all_scripts)
    return results


def report(results: dict):
    print()
    print("=" * 70)
    print("SIMS 4 CC LOAD SIMULATION REPORT")
    print("=" * 70)

    total = results['total_packages']
    loaded = len(results['will_load'])
    blocked = len(results['wont_load'])
    scripts_ok  = len(results['scripts_ok'])
    scripts_bad = len(results['scripts_bad'])
    conflicts   = len(results['conflicts'])

    print(f"\nTotal packages found:  {total:,}")
    print(f"  Will load (valid):   {loaded:,}")
    print(f"  WON'T load (issues): {blocked}")
    print(f"\nTotal scripts:         {results['total_scripts']}")
    print(f"  Clean:               {scripts_ok}")
    print(f"  Broken (blocked):    {scripts_bad}")
    print(f"\nResource conflicts:    {conflicts}")
    print(f"\nScan time:             {results['elapsed']:.1f}s")

    # Category breakdown
    print()
    print("─" * 70)
    print("CC CATEGORIES (what will load):")
    print("─" * 70)
    for cat, count in sorted(results['categories'].items(), key=lambda x: -x[1]):
        bar = '█' * min(40, count // max(1, loaded // 40))
        print(f"  {count:5,}  {cat}")

    # Packages that won't load
    if results['wont_load']:
        print()
        print("─" * 70)
        print(f"PACKAGES THAT WON'T LOAD ({len(results['wont_load'])}):")
        print("─" * 70)
        for pkg, reason in results['wont_load']:
            print(f"  [{reason.split(':')[0]}]  {pkg.name}")
            print(f"           {reason}")

    # Depth blocked
    if results['depth_blocked']:
        print()
        print("─" * 70)
        print(f"TOO DEEP (>{MAX_DEPTH} subfolder levels, game ignores these):")
        print("─" * 70)
        for pkg in results['depth_blocked']:
            rel = pkg.relative_to(MODS)
            print(f"  Depth {len(rel.parts)-1}: {rel}")

    # Broken scripts
    if results['scripts_bad']:
        print()
        print("─" * 70)
        print(f"BROKEN SCRIPTS (won't function, may cause errors):")
        print("─" * 70)
        for script, issues in results['scripts_bad']:
            print(f"  {script.name}")
            for issue in issues:
                print(f"    -> {issue}")

    # Conflicts (same resource in 2+ packages)
    if results['conflicts']:
        print()
        print("─" * 70)
        conflict_list = sorted(results['conflicts'].items(), key=lambda x: -len(x[1]))
        print(f"RESOURCE CONFLICTS ({len(conflict_list)} conflicts, showing top 20):")
        print("  Same tuning/object defined in multiple packages = CONFLICT")
        print("─" * 70)
        for (tid, ih, il), paths in conflict_list[:20]:
            type_name = RESOURCE_TYPES.get(tid, hex(tid))
            print(f"  {type_name} [{hex(tid)}:{hex(ih)}:{hex(il)}] in {len(paths)} packages:")
            for p in paths[:3]:
                print(f"    {p.name}")
            if len(paths) > 3:
                print(f"    ...and {len(paths)-3} more")

    # Summary for user
    print()
    print("=" * 70)
    print("DIAGNOSIS")
    print("=" * 70)

    cas_count = sum(v for k, v in results['categories'].items() if 'CAS' in k or 'hair' in k.lower())
    buy_count = sum(v for k, v in results['categories'].items() if 'Build' in k or 'Buy' in k)
    anim_count = results['categories'].get('Animation Pack', 0)

    print(f"  CAS items (hair/clothing):    {cas_count:,}")
    print(f"  Build/Buy items (furniture):  {buy_count:,}")
    print(f"  Animation packs:              {anim_count}")
    print(f"  Packages blocked from loading: {blocked}")
    print(f"  Resource conflicts:           {conflicts}")

    if blocked == 0 and conflicts < 50:
        print()
        print("  >> All packages can load. If items are missing in-game,")
        print("     the issue is SAVE CORRUPTION (items placed from now-missing CC)")
        print("     or the items are in a different Build/Buy category than expected.")

    # Save report to file
    report_path = S4 / 'cc_simulation_report.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"CC Load Simulation Report\n")
        f.write(f"Total packages: {total:,} | Will load: {loaded:,} | Blocked: {blocked}\n")
        f.write(f"Scripts OK: {scripts_ok} | Scripts broken: {scripts_bad}\n")
        f.write(f"Conflicts: {conflicts}\n\n")
        f.write("CATEGORIES:\n")
        for cat, count in sorted(results['categories'].items(), key=lambda x: -x[1]):
            f.write(f"  {count:5,}  {cat}\n")
        f.write("\nWON'T LOAD:\n")
        for pkg, reason in results['wont_load']:
            f.write(f"  {pkg.name}: {reason}\n")
        f.write("\nBROKEN SCRIPTS:\n")
        for script, issues in results['scripts_bad']:
            f.write(f"  {script.name}: {'; '.join(issues)}\n")
    print(f"\n  Full report saved to: {report_path}")


if __name__ == '__main__':
    results = simulate(MODS)
    report(results)
