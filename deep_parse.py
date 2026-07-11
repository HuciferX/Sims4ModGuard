"""
Deep parse of lastException.txt to find exactly which CC objects
are causing the script_object.py tuning conflicts.
"""
import re, xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

log_path = Path(r'C:\Users\merli\Documents\Electronic Arts\The Sims 4\lastException.txt')
content = log_path.read_text(encoding='utf-8', errors='replace')

# Wrap and parse
try:
    root = ET.fromstring(f"<root>{content}</root>")
except ET.ParseError as e:
    print(f"XML parse error: {e}")
    # Fall back to regex
    root = None

if root is not None:
    print(f"Total reports: {len(root.findall('report'))}")
    print()

    # Extract all desyncdata blocks
    errors = Counter()
    object_names = Counter()
    raw_texts = []

    for report in root.findall('report'):
        dd = report.find('desyncdata')
        if dd is not None and dd.text:
            text = dd.text.strip()
            raw_texts.append(text)

            # Get first meaningful line as key
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            if lines:
                errors[lines[0][:150]] += 1

            # Extract object/resource names from error text
            # Patterns like: "ClassName", tuning IDs, hash references
            names = re.findall(r"'([^']{5,60})'", text)
            for n in names:
                if not n.startswith('0x') and len(n) > 4:
                    object_names[n] += 1

    print("TOP ERROR MESSAGES (most frequent first):")
    print("-" * 60)
    for msg, count in errors.most_common(15):
        print(f"  [{count:4d}x]  {msg[:100]}")

    print()
    print("OBJECTS/RESOURCES MENTIONED IN ERRORS:")
    print("-" * 60)
    for name, count in object_names.most_common(20):
        print(f"  [{count:4d}x]  {name}")

    # Look for file/object references
    print()
    print("SAMPLE RAW ERROR TEXTS (first 5 unique):")
    print("-" * 60)
    seen = set()
    shown = 0
    for text in raw_texts:
        key = text[:60]
        if key not in seen:
            seen.add(key)
            print(f"\n--- Error #{shown+1} ---")
            for line in text.splitlines()[:15]:
                print(f"  {line}")
            shown += 1
        if shown >= 5:
            break
else:
    # Regex fallback
    print("Using regex fallback...")
    desync_blocks = re.findall(r'<desyncdata>(.*?)</desyncdata>', content, re.DOTALL)
    print(f"Found {len(desync_blocks)} error blocks")
    errors = Counter()
    for block in desync_blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if lines:
            errors[lines[0][:120]] += 1

    print("\nTOP ERRORS:")
    for msg, count in errors.most_common(10):
        print(f"  [{count}x] {msg}")
