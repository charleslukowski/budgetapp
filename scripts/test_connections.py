"""
Test database connections.

Usage:
    python scripts/test_connections.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.db.infinium import test_connection as test_infinium
from src.db.postgres import test_connection as test_postgres


def main():
    print("=" * 60)
    print("Testing Database Connections")
    print("=" * 60)
    
    # Test Infinium DB2
    print("\n[1] Infinium DB2...")
    success, message = test_infinium()
    status = "[OK]" if success else "[FAILED]"
    print(f"    {status} {message}")
    
    # Test PostgreSQL
    print("\n[2] PostgreSQL...")
    success, message = test_postgres()
    status = "[OK]" if success else "[FAILED]"
    print(f"    {status} {message}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()

