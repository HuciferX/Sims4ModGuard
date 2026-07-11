import sys
sys.path.insert(0, r'C:\Users\merli\Sims4ModGuard')
from sims4modguard.cache_manager import clear_caches
from pathlib import Path
result = clear_caches(Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4'), verbose=True)
mb = result['bytes_freed'] // (1024*1024)
count = len(result['files'])
print(f'Cleared {count} cache files ({mb} MB freed)')
