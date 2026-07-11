"""
Byte-level fix for gui_app.py.
Stays entirely in BINARY MODE to avoid Windows CRLF line-doubling bug.
"""

with open(r'C:\Users\merli\Sims4ModGuard\gui_app.py', 'rb') as f:
    raw = f.read()

print(f"Original: {len(raw)} bytes, {raw.count(b'chr(10)')} lines")

replacements = [
    (b'\xc3\xa2\xe2\x80\x9e\xc2\xb9\xc3\xaf\xc2\xb8\xc2\x8f', b'[??]'),  # info emoji
    (b'\xc3\xb0\xc5\xb8\xe2\x80\x9d\xc2\x8d', b'[>>]'),   # magnifier
    (b'\xc3\xb0\xc5\xb8\xe2\x80\x9c\xc2\xa6', b'[##]'),   # package
    (b'\xc3\xb0\xc5\xb8\xe2\x80\x9c\xe2\x80\xb9', b'[!!]'), # clipboard
    (b'\xc3\xb0\xc5\xb8\xe2\x80\x9d\xc2\xa7', b'[WR]'),   # wrench
    (b'\xc3\xb0\xc5\xb8\xe2\x80\x99\xc2\xbb', b'[>_]'),   # laptop
    (b'\xc3\xb0\xc5\xb8\xe2\x80\x9d\xc2\xb7', b'[>>]'),   # blue diamond
    (b'\xc3\xb0\xc5\xb8\xc2\xa6\xe2\x80\xb0', b''),        # owl (remove)
    (b'\xc3\xb0\xc5\xb8\xe2\x80\x94\xe2\x80\x98', b'XX'),  # trash
    (b'\xc3\xb0\xc5\xb8\xe2\x80\x9c\xe2\x80\x9a', b'->'),  # open folder
    (b'\xc3\xb0\xc5\xb8\xc5\xb8\xc2\xa2', b'[OK]'),        # green circle
    (b'\xc3\xb0\xc5\xb8\xe2\x80\x9d\xc2\xb4', b'[!!]'),   # red circle
    (b'\xc3\xb0\xc5\xb8\xc5\xb8\xc2\xa1', b'[~~]'),        # yellow circle
    (b'\xc3\xa2\xc5\xa1\xc2\xa1', b'>>'),                   # lightning
    (b'\xc3\xa2\xe2\x84\xa2\xc2\xbb', b'~~'),               # recycle
    (b'\xc3\xa2\xe2\x96\xb6', b'>>'),                       # play triangle
    (b'\xc3\xa2\xe2\x86\x92', b'->'),                       # right arrow
    (b'\xc3\xa2\xe2\x82\xac\xe2\x80\x9d', b'--'),          # em dash
    (b'\xc3\xa2\xe2\x9c\x97', b'[XX]'),                    # cross
    (b'\xc3\xa2\xe2\x9c\x93', b'[OK]'),                    # check
    (b'\xc3\xa2\xe2\x9a\xa0', b'[!]'),                     # warning triangle
]

count = 0
for old, new in replacements:
    n = raw.count(old)
    if n:
        raw = raw.replace(old, new)
        print(f"  {n}x  {new.decode()}")
        count += n

print(f"Total: {count} replacements")

# ASCII-only fixes (safe in binary mode on both CRLF and LF files)
raw = raw.replace(
    b'        content.columnconfigure(0, weight=1)\r\n        content.rowconfigure(1, weight=1)',
    b'        content.columnconfigure(0, weight=1)'
)
raw = raw.replace(
    b'        content.columnconfigure(0, weight=1)\n        content.rowconfigure(1, weight=1)',
    b'        content.columnconfigure(0, weight=1)'
)
print("  Fixed dead space")

raw = raw.replace(b'fg_color=BG_HEADER, width=160)', b'fg_color=BG_HEADER, width=190)')
print("  Widened sidebar to 190px")

# Write in BINARY mode - no line ending conversion
with open(r'C:\Users\merli\Sims4ModGuard\gui_app.py', 'wb') as f:
    f.write(raw)

print(f"\nFinal: {len(raw)} bytes, {raw.count(chr(10).encode())} lines")
print("Done!")
