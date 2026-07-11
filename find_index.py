import struct, zlib
from pathlib import Path

mods = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\Mods')
pkg = next(p for p in mods.rglob('*.package') if p.stat().st_size > 10000)
raw = pkg.read_bytes()
file_size = len(raw)

idx_count  = struct.unpack_from('<I', raw, 36)[0]
val40 = struct.unpack_from('<I', raw, 40)[0]
val44 = struct.unpack_from('<I', raw, 44)[0]
val48 = struct.unpack_from('<I', raw, 48)[0]
val52 = struct.unpack_from('<I', raw, 52)[0]

print(f"File: {pkg.name} ({file_size:,} bytes)")
print(f"idx_count={idx_count}, 32*count={idx_count*32}")
print(f"Header: off40={val40} off44={val44} off48={val48} off52={val52}")
print()

# Try index at end: file_size - val44
for label, idx_off in [
    ("file_size - val44", file_size - val44),
    ("file_size - val48", file_size - val48),
    ("val40", val40),
    ("val44", val44),
    ("val48", val48),
]:
    if idx_off < 96 or idx_off + idx_count * 32 > file_size:
        print(f"[{label}={idx_off}] out of range")
        continue

    valid_entries = 0
    for i in range(idx_count):
        base = idx_off + i * 32
        if base + 32 > file_size: break
        res_off  = struct.unpack_from('<I', raw, base + 16)[0]
        size_raw = struct.unpack_from('<I', raw, base + 20)[0]
        size_act = size_raw & 0x7FFFFFFF
        if 96 <= res_off < file_size and 0 < size_act < file_size - res_off:
            valid_entries += 1

    pct = valid_entries / idx_count * 100 if idx_count else 0
    print(f"[{label}={idx_off}] valid entries: {valid_entries}/{idx_count} ({pct:.0f}%)")

    if pct > 80:
        print(f"  ** LIKELY CORRECT INDEX OFFSET **")
        # Show first 3 entries
        for i in range(min(3, idx_count)):
            base = idx_off + i * 32
            type_id  = struct.unpack_from('<I', raw, base + 0)[0]
            res_off  = struct.unpack_from('<I', raw, base + 16)[0]
            size_raw = struct.unpack_from('<I', raw, base + 20)[0]
            mem_size = struct.unpack_from('<I', raw, base + 24)[0]
            comp_type = struct.unpack_from('<H', raw, base + 28)[0]
            size_act = size_raw & 0x7FFFFFFF
            print(f"  Entry {i}: TypeID={hex(type_id)} offset={res_off} size={size_act} mem={mem_size} comp={hex(comp_type)}")
            if 96 <= res_off < file_size and 0 < size_act < 500000:
                d = raw[res_off:res_off+min(size_act, 20)]
                print(f"    bytes: {d.hex()}")
                # Try zlib
                try:
                    full = raw[res_off:res_off+size_act]
                    dec = zlib.decompress(full)
                    print(f"    zlib ok: {len(dec)} bytes -> {dec[:40]}")
                except:
                    pass
                # Try raw deflate
                try:
                    full = raw[res_off:res_off+size_act]
                    dec = zlib.decompress(full, -15)
                    print(f"    raw deflate ok: {len(dec)} bytes -> {dec[:40]}")
                except:
                    pass
