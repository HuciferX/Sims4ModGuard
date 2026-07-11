raw = open(r'C:\Users\merli\Sims4ModGuard\gui_app.py', 'rb').read()
old = b'            ("[??]   ABOUT",         "about",   self._build_about_tab),\r\n        ]'
new = (b'            ("[>G] LAUNCHER",      "launcher", self._build_launcher_tab),\r\n'
       b'            ("[??]   ABOUT",         "about",   self._build_about_tab),\r\n        ]')
if old in raw:
    raw = raw.replace(old, new)
    open(r'C:\Users\merli\Sims4ModGuard\gui_app.py', 'wb').write(raw)
    print('LAUNCHER tab added to navigation')
else:
    idx = raw.find(b'[??]')
    print(f'Not found. Context: {repr(raw[idx-5:idx+60])}')
