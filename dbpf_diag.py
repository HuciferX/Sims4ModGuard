"""Diagnose the actual DBPF resource format in one known package."""
import struct, zlib
from pathlib import Path

mods = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\Mods')
packages = list(mods.rglob('*.package'))

# Look at the first few packages and print index entry details + raw resource headers
for pkg in packages[:5]:
    try:
        raw = pkg.read_bytes()
        if len(raw) < 96 or raw[:4] != b'DBPF': continue

        major     = struct.unpack_from('<I', raw, 4)[0]
        idx_count = struct.unpack_from('<I', raw, 36)[0]
        idx_off   = struct.unpack_from('<I', raw, 40)[0]

        print(f"\n{'='*60}")
        print(f"FILE: {pkg.name}")
        print(f"  Major: {major}, Index entries: {idx_count}, Index offset: {idx_off}")

        for i in range(min(idx_count, 5)):
            base = idx_off + i * 32
            if base + 32 > len(raw): break

            type_id   = struct.unpack_from('<I', raw, base + 0)[0]
            group_id  = struct.unpack_from('<I', raw, base + 4)[0]
            inst_hi   = struct.unpack_from('<I', raw, base + 8)[0]
            inst_lo   = struct.unpack_from('<I', raw, base + 12)[0]
            offset    = struct.unpack_from('<I', raw, base + 16)[0]
            size_raw  = struct.unpack_from('<I', raw, base + 20)[0]
            field24   = struct.unpack_from('<I', raw, base + 24)[0]
            comp_type = struct.unpack_from('<H', raw, base + 28)[0]
            committed = struct.unpack_from('<H', raw, base + 30)[0]

            size_actual = size_raw & 0x7FFFFFFF
            has_ext = bool(size_raw & 0x80000000)

            print(f"\n  Entry {i}: TypeID={hex(type_id)} Offset={offset}")
            print(f"    size_raw={hex(size_raw)} actual={size_actual} has_ext_flag={has_ext}")
            print(f"    field24={field24} comp_type={hex(comp_type)} committed={committed}")

            # Show first 20 bytes of resource data
            if 0 < size_actual < 100_000 and offset + size_actual <= len(raw):
                res_data = raw[offset:offset + min(size_actual, 20)]
                print(f"    First bytes: {res_data.hex()}")

                # Try to detect compression by looking at the data
                if res_data[:2] in (b'\x78\x9c', b'\x78\x01', b'\x78\xda', b'\x78\x5e'):
                    print(f"    -> Looks like ZLib (wbits 15 header)")
                    try:
                        dec = zlib.decompress(raw[offset:offset+size_actual])
                        print(f"    -> Decompressed to {len(dec)} bytes: {dec[:30]}")
                    except: print(f"    -> Decompress failed")

                elif res_data[:2] == b'\x78\x9c' or (len(res_data) >= 9 and res_data[0] == 0x78):
                    print(f"    -> Might be raw zlib")

                # Try decompress raw deflate
                try:
                    dec = zlib.decompress(raw[offset:offset+size_actual], -15)
                    print(f"    -> Raw deflate OK: {len(dec)} bytes: {dec[:30]}")
                except: pass

                # Check for the internal compression format (9-byte header)
                if len(res_data) >= 9:
                    # Header: 4 bytes uncompressed size (BE) + 2 bytes + 1 byte flags + 2 bytes
                    unc_size = struct.unpack_from('>I', res_data, 0)[0]
                    flags = res_data[6]
                    maybe_zlib = res_data[7:9]
                    print(f"    -> If 9-byte header: unc_size={unc_size} flags={hex(flags)} next={maybe_zlib.hex()}")
                    if maybe_zlib in (b'\x78\x9c', b'\x78\x01', b'\x78\xda', b'\x78\x5e'):
                        print(f"    -> MATCH: 9-byte internal header with zlib data after!")
                        try:
                            body = raw[offset+9:offset+size_actual]
                            # Try with raw deflate (strip zlib header)
                            dec = zlib.decompress(raw[offset+7:offset+size_actual])
                            print(f"    -> Decompressed {len(dec)} bytes: {dec[:50]}")
                        except Exception as e:
                            print(f"    -> Failed: {e}")

        break  # just first valid package
    except Exception as e:
        print(f"Error on {pkg.name}: {e}")
        continue
