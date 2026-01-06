"""
Import budget data from CSV to budget_lines table.

Usage:
    python scripts/import_budget.py                    # Import 2025 budget (default)
    python scripts/import_budget.py 2025              # Import specific year
    python scripts/import_budget.py 2025 --clear      # Clear existing and import
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.etl.budget_import import import_budget
from src.db.postgres import get_session


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    clear_existing = "--clear" in sys.argv
    
    csv_path = project_root / "docs" / "source_documents" / "PTProd_AcctGL_Budget.csv"
    
    if not csv_path.exists():
        print(f"Error: CSV file not found at {csv_path}")
        sys.exit(1)
    
    print(f"Importing budget data for year {year}...")
    print(f"Source: {csv_path}")
    print(f"Clear existing: {clear_existing}")
    print()
    
    db = get_session()
    
    try:
        stats = import_budget(
            db=db,
            file_path=csv_path,
            clear_existing=clear_existing,
            budget_year=year
        )
        
        print()
        print("=" * 50)
        print("Import Complete!")
        print("=" * 50)
        print(f"  Total rows in CSV: {stats['total_rows']}")
        print(f"  Imported:          {stats['imported']}")
        print(f"  Skipped:           {stats['skipped']}")
        print(f"  Errors:            {stats['errors']}")
        print(f"  Total Budget:      ${stats['total_budget']:,.2f}")
        print("=" * 50)
        
    except Exception as e:
        print(f"Error during import: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

