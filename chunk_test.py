"""
1/8 chunk isolation test.
Keeps ONE chunk of packages active at a time.
The chunk that causes a crash = contains the culprit.
Then do 50/50 inside that chunk.

Usage:
  python chunk_test.py init          -- set up 8 chunks, activate chunk 1
  python chunk_test.py next          -- deactivate current, activate next chunk
  python chunk_test.py status        -- show what's currently active
  python chunk_test.py restore       -- put everything back
"""
import json, shutil, sys
from pathlib import Path

MODS   = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\Mods')
STAGE  = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\CHUNK_STAGE')
STATE  = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\chunk_state.json')
CHUNKS = 8

def save(data): STATE.write_text(json.dumps(data, indent=2))
def load(): return json.loads(STATE.read_text()) if STATE.exists() else None

def all_packages():
    return sorted(
        [str(p) for p in MODS.rglob('*.package')
         if 'MODS_DISABLED' not in p.parts
         and 'CHUNK_STAGE' not in str(p)],
        key=lambda x: Path(x).name.lower()
    )

def cmd_init():
    if STATE.exists():
        print('Test already running. Use: python chunk_test.py restore')
        return
    pkgs = all_packages()
    n = len(pkgs)
    size = n // CHUNKS
    chunks = []
    for i in range(CHUNKS):
        start = i * size
        end = start + size if i < CHUNKS - 1 else n
        chunks.append(pkgs[start:end])

    print(f'{n:,} packages split into {CHUNKS} chunks of ~{size} each')
    STAGE.mkdir(exist_ok=True)

    # Stage chunks 2-8, keep chunk 1 active
    staged = {}
    for i, chunk in enumerate(chunks[1:], start=2):
        staged[i] = []
        for p in chunk:
            name = Path(p).name
            dest = STAGE / f'chunk{i}' / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(p, str(dest))
            staged[i].append(p)
        print(f'  Chunk {i}: {len(chunk)} packages staged')

    save({'current': 1, 'chunks': [c for c in chunks], 'staged': staged, 'total_chunks': CHUNKS})
    active = all_packages()
    print(f'\nChunk 1 ACTIVE ({len(chunks[0])} packages)')
    print(f'Chunks 2-{CHUNKS} staged ({sum(len(c) for c in chunks[1:])} packages)')
    print()
    print('Launch the game.')
    print('  Loads OK  -> Chunk 1 is clean, run: python chunk_test.py next')
    print('  Crashes   -> Culprit is in Chunk 1, do 50/50 inside it')

def cmd_next():
    state = load()
    if not state:
        print('No test running. Run: python chunk_test.py init')
        return

    current = state['current']
    total   = state['total_chunks']

    if current >= total:
        print(f'Already on last chunk ({current}/{total}). Culprit not found - restore and try 50/50.')
        return

    # Stage current chunk, unstage next
    next_chunk = current + 1
    chunks     = state['chunks']
    staged     = state['staged']

    # Move current (active) to stage
    cur_pkgs = chunks[current - 1]
    staged[str(current)] = cur_pkgs
    stage_dir = STAGE / f'chunk{current}'
    stage_dir.mkdir(parents=True, exist_ok=True)
    for p in cur_pkgs:
        name = Path(p).name
        src  = MODS / name
        if src.exists():
            shutil.move(str(src), str(stage_dir / name))

    # Restore next chunk from stage
    next_stage = STAGE / f'chunk{next_chunk}'
    restored = 0
    if next_stage.exists():
        for f in next_stage.glob('*.package'):
            dest = MODS / f.name
            shutil.move(str(f), str(dest))
            restored += 1
        next_stage.rmdir()

    state['current'] = next_chunk
    staged.pop(str(next_chunk), None)
    state['staged'] = staged
    save(state)

    active = all_packages()
    print(f'Chunk {next_chunk} ACTIVE ({len(active)} packages) [was: chunk {current}]')
    print()
    print('Launch the game.')
    print(f'  Loads OK  -> Chunk {next_chunk} clean, run: python chunk_test.py next')
    print(f'  Crashes   -> Culprit is in Chunk {next_chunk}')

def cmd_status():
    state = load()
    if not state:
        print('No test running.')
        return
    cur = state['current']
    total = state['total_chunks']
    active = all_packages()
    print(f'Chunk {cur}/{total} active  |  {len(active)} packages in Mods')
    chunk = state['chunks'][cur - 1]
    print(f'First 5 in active chunk: {[Path(p).name for p in chunk[:5]]}')

def cmd_restore():
    state = load()
    if not state:
        print('No test running.')
        return
    # Move everything back from CHUNK_STAGE
    restored = 0
    if STAGE.exists():
        for f in STAGE.rglob('*.package'):
            dest = MODS / f.name
            shutil.move(str(f), str(dest))
            restored += 1
    # Cleanup
    for d in sorted(STAGE.rglob('*'), reverse=True):
        if d.is_dir():
            try: d.rmdir()
            except: pass
    try: STAGE.rmdir()
    except: pass
    STATE.unlink(missing_ok=True)
    print(f'Restored {restored} packages. All {len(all_packages()):,} packages now active.')

cmd = sys.argv[1].lower() if len(sys.argv) > 1 else 'status'
{'init': cmd_init, 'next': cmd_next, 'status': cmd_status, 'restore': cmd_restore}.get(cmd, cmd_status)()
