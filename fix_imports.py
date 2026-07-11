raw = open(r'C:\Users\merli\Sims4ModGuard\gui_app.py', 'rb').read()

# Remove any misplaced import subprocess inside method bodies
# Find where subprocess import actually is
idx = raw.find(b'import subprocess')
print(f'import subprocess found at byte {idx}')
print(f'Context: {repr(raw[idx-30:idx+30])}')

# The correct place is right after "import random"
if b'import random\r\nimport subprocess' not in raw and b'import random\r\nfrom datetime' in raw:
    raw = raw.replace(
        b'import random\r\nfrom datetime import datetime',
        b'import random\r\nimport subprocess\r\nimport re\r\nfrom datetime import datetime'
    )
    print('Added imports after random')
elif b'import random\nimport subprocess' not in raw and b'import random\nfrom datetime' in raw:
    raw = raw.replace(
        b'import random\nfrom datetime import datetime',
        b'import random\nimport subprocess\nimport re\nfrom datetime import datetime'
    )
    print('Added imports (LF variant)')
else:
    # Already somewhere - check location
    idx2 = raw.find(b'import random')
    print(f'import random at {idx2}, subprocess at {idx}')
    if idx > idx2 + 200:
        print('subprocess is too far down - needs to be at top level')

open(r'C:\Users\merli\Sims4ModGuard\gui_app.py', 'wb').write(raw)
print('Done')
