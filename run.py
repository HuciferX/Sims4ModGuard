#!/usr/bin/env python3
"""
Convenience runner. Double-click or run:
  python run.py              # interactive scan
  python run.py --fix        # auto-fix all critical issues
  python run.py --full       # scripts + CC package scan
  python run.py --scan-only  # report only, no changes
  python run.py --restore    # restore quarantined files
  python run.py --cc-scan    # CC package scan only
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from sims4modguard.main import main
main()
