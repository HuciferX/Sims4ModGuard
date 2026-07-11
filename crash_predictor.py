"""
Crash predictor: scans each package in the confirmed culprit range for
patterns that cause hard C++ crashes in the game's DBPF reader.

Checks:
  - Resources with impossible decompressed sizes (>64MB each)
  - Resource offsets outside file bounds
  - Index count overflow / implausible values
  - Specific broken TypeIDs known to crash 1.121
  - Very old modfile signatures (NRaas, pre-2016 mods)
  - All resources can be safely read from file
"""
import struct, zlib, json
from pathlib import Path
from datetime import datetime, timezone

MODS   = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\Mods')
STAGE  = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\CULPRIT_STAGE')
STATE  = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\culprit_state.json')

MAX_RESOURCE_SIZE = 64 * 1024 * 1024   # 64 MB per resource = crash threshold
PATCH_DATE        = datetime(2016, 1, 1, tzinfo=timezone.utc)  # very old mods

# TypeIDs that are known to crash 1.121 when encountered
CRASH_TYPEIDS = {
    0xCCA8E925,  # old Sims 3 resource type (NRaas)
    0x0353782B,  # old career resource
    # 0xB61DE6B4 removed - false positive (valid food/recipe TypeID used by icemunmun)
}

# Known old/broken filename patterns
OLD_MOD_PATTERNS = ['nraas', 'errortrap', 'mccmd', 'dresser_nraas']

# Scan ALL active packages in Mods, not just the current test range
MODS_PATH = MODS
packages = [str(p) for p in MODS_PATH.rglob('*.package')
            if 'MODS_DISABLED' not in p.parts
            and 'CULPRIT_STAGE' not in str(p)
            and 'CHUNK_STAGE' not in str(p)]
print(f'Scanning {len(packages):,} packages for crash triggers...\n')
print(f'{"RISK":<8} {"PACKAGE":<55} REASON')
print('-' * 90)

results = []
for pkg_path in packages:
    actual = Path(pkg_path)
    name = actual.name
    if not actual.exists():
        continue

    risk = 0
    reasons = []

    try:
        raw = actual.read_bytes()
        sz  = len(raw)

        # 1. DBPF magic check
        if raw[:4] != b'DBPF':
            risk += 100; reasons.append('NOT DBPF')

        if len(raw) >= 96:
            major      = struct.unpack_from('<I', raw, 4)[0]
            idx_count  = struct.unpack_from('<I', raw, 36)[0]
            idx_block  = struct.unpack_from('<I', raw, 44)[0]

            # 2. Unknown version
            if major not in (1, 2):
                risk += 50; reasons.append(f'unknown DBPF version {major}')

            # 3. Implausible index
            if idx_count > 100_000:
                risk += 80; reasons.append(f'huge index count {idx_count}')

            # 4. Index block bigger than file
            if idx_block > sz:
                risk += 90; reasons.append(f'index block {idx_block} > file {sz}')

            elif idx_block > 0 and idx_count > 0:
                block_start = sz - idx_block
                if block_start >= 96:
                    flags = struct.unpack_from('<I', raw, block_start)[0]
                    TYPE_CONST  = bool(flags & 0x01)
                    GROUP_CONST = bool(flags & 0x02)
                    INSHI_CONST = bool(flags & 0x04)
                    hp = block_start + 4
                    const_tid = None
                    if TYPE_CONST:
                        const_tid = struct.unpack_from('<I', raw, hp)[0]; hp += 4
                    if GROUP_CONST: hp += 4
                    if INSHI_CONST: hp += 4
                    ESIZ = 32 - (4 if TYPE_CONST else 0) - (4 if GROUP_CONST else 0) - (4 if INSHI_CONST else 0)

                    for i in range(min(idx_count, 2000)):
                        base = hp + i * ESIZ
                        if base + ESIZ > sz: break
                        tid  = const_tid if TYPE_CONST else struct.unpack_from('<I', raw, base)[0]
                        off_base = base + (0 if TYPE_CONST else 16 - (4 if GROUP_CONST else 0) - (4 if INSHI_CONST else 0))

                        # Try to get offset and sizes safely
                        try:
                            # offsets in entry depend on constant fields
                            entry_fields_offset = 0
                            if not TYPE_CONST:  entry_fields_offset += 4   # type
                            if not GROUP_CONST: entry_fields_offset += 4   # group
                            if not INSHI_CONST: entry_fields_offset += 4   # inst_hi
                            entry_fields_offset += 4  # inst_lo
                            res_off  = struct.unpack_from('<I', raw, base + entry_fields_offset)[0]
                            res_size = struct.unpack_from('<I', raw, base + entry_fields_offset + 4)[0] & 0x7FFFFFFF
                            mem_size = struct.unpack_from('<I', raw, base + entry_fields_offset + 8)[0]

                            # 5. Resource offset out of bounds
                            if res_off + res_size > sz and res_size > 0:
                                risk += 30; reasons.append(f'resource #{i} out of bounds')
                                break

                            # 6. Huge decompressed size = memory crash
                            if mem_size > MAX_RESOURCE_SIZE:
                                risk += 60; reasons.append(f'resource #{i} mem_size={mem_size//1024//1024}MB')

                            # 7. Known crashing TypeIDs
                            if tid in CRASH_TYPEIDS:
                                risk += 70; reasons.append(f'crash TypeID {hex(tid)}')

                        except struct.error:
                            break

        # 8. Old mod signature
        for pat in OLD_MOD_PATTERNS:
            if pat in name.lower():
                risk += 40; reasons.append(f'old mod pattern ({pat})')
                break

        # 9. Very old file
        mtime = datetime.fromtimestamp(actual.stat().st_mtime, tz=timezone.utc)
        if mtime < PATCH_DATE:
            risk += 20; reasons.append(f'pre-2016 ({mtime.year})')

    except Exception as e:
        risk += 50; reasons.append(f'read error: {e}')

    results.append((risk, name, ', '.join(reasons) if reasons else 'clean'))

results.sort(reverse=True)

# Show only flagged items (risk > 0)
flagged = [(r, n, reason) for r, n, reason in results if r > 0]
clean   = len(results) - len(flagged)

print(f'Flagged ({len(flagged)}) | Clean ({clean:,})')
print()
for risk, name, reason in flagged:
    flag = '[!!]' if risk >= 50 else '[??]'
    print(f'{flag} {risk:<4} {name}')
    print(f'         {reason}')

# Save full report
report = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\crash_scan_report.txt')
with open(report, 'w', encoding='utf-8') as f:
    f.write(f'Crash Scan Report - {len(results):,} packages scanned\n')
    f.write(f'Flagged: {len(flagged)} | Clean: {clean:,}\n\n')
    for risk, name, reason in results:
        if risk > 0:
            f.write(f'RISK {risk:3d}  {name}\n')
            f.write(f'         {reason}\n')
print(f'\nFull report: {report}')

if flagged and flagged[0][0] >= 50:
    print(f'\nTOP CRASH SUSPECT: {flagged[0][1]}')
    print(f'  Reason: {flagged[0][2]}')
