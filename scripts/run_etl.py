"""
Run the GL Actuals ETL.

Usage:
    python scripts/run_etl.py                  # Load 2025 full year
    python scripts/run_etl.py 2025             # Load 2025 full year
    python scripts/run_etl.py 2025 11          # Load 2025 November only
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.etl.gl_actuals import load_gl_actuals


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    month = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    load_gl_actuals(year, month)


if __name__ == "__main__":
    main()

