"""Fix the window title mojibake and header plumbob icon."""

with open(r'C:\Users\merli\Sims4ModGuard\gui_app.py', 'rb') as f:
    raw = f.read()

# Fix the window title - the broken bytes are the mojibake for the diamond ◈ character
broken = b'self.title(\"\xc3\xa2\xe2\x80\x94\xcb\x86 Sims4 Mod Guardian \xc3\xa2\xe2\x80\x94\xcb\x86  by Hucifer & Hypatia\")'
clean  = b'self.title(\"[ SIMS4 MOD GUARDIAN ]  by Hucifer + Hypatia\")'

if broken in raw:
    raw = raw.replace(broken, clean)
    print('Fixed window title')
else:
    print('Title pattern not found - showing current:')
    idx = raw.find(b'self.title(')
    end = raw.find(b')', idx)
    print(raw[idx:end+2])

# Fix header plumbob icon: [>>] is too plain, use a diamond text instead
for crlf in [b'\r\n', b'\n']:
    raw = raw.replace(
        b'text="[>>]",' + crlf + b'                     font=("Courier New", 28),',
        b'text="<>",' + crlf + b'                     font=("Courier New", 32, "bold"),'
    )

# Also fix the BANNER_ART variable which still has mojibake
# â—ˆ = C3A2 E28094 CB86 = mojibake for ◈
banner_broken = b'BANNER_ART = \"\xc3\xa2\xe2\x80\x94\xcb\x86 SIMS 4 MOD GUARDIAN \xc3\xa2\xe2\x80\x94\xcb\x86\"'
banner_clean  = b'BANNER_ART = \"** SIMS 4 MOD GUARDIAN **\"'
if banner_broken in raw:
    raw = raw.replace(banner_broken, banner_clean)
    print('Fixed BANNER_ART')

with open(r'C:\Users\merli\Sims4ModGuard\gui_app.py', 'wb') as f:
    f.write(raw)

print(f'Done. Size: {len(raw)} bytes')
