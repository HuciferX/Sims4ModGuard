"""Get the full error detail from the lastException.txt"""
import re
from pathlib import Path

log = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\lastException.txt')
content = log.read_text(encoding='utf-8', errors='replace')

# Get desyncdata blocks
blocks = re.findall(r'<desyncdata>(.*?)</desyncdata>', content, re.DOTALL)
print(f"Total error blocks: {len(blocks)}")
print()

# Show first 5 unique full error texts
seen = set()
shown = 0
for block in blocks:
    first_line = block.strip().splitlines()[0][:80] if block.strip() else ''
    if first_line not in seen:
        seen.add(first_line)
        print(f"{'='*70}")
        print(f"ERROR #{shown+1}:")
        for line in block.strip().splitlines()[:20]:
            print(f"  {line}")
        print()
        shown += 1
    if shown >= 5:
        break

# Also check what the AttributeError is specifically
attr_errors = re.findall(r'AttributeError: ([^\n<]{5,200})', content)
print(f"{'='*70}")
print(f"UNIQUE AttributeError MESSAGES ({len(set(attr_errors))} unique):")
for e in sorted(set(attr_errors))[:10]:
    print(f"  {e}")
