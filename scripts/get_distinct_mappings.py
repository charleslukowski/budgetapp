"""
Get distinct values for mapping fields.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.db.postgres import get_engine
from sqlalchemy import text


def main():
    engine = get_engine()
    conn = engine.connect()
    
    # Get distinct GXSHUT (outage aliases)
    print("=" * 60)
    print("GXSHUT (Outage Aliases)")
    print("=" * 60)
    result = conn.execute(text("""
        SELECT DISTINCT gxshut, COUNT(*) as cnt
        FROM gl_transactions 
        WHERE gxshut IS NOT NULL AND TRIM(gxshut) != ''
        GROUP BY gxshut
        ORDER BY gxshut
    """))
    rows = result.fetchall()
    for r in rows:
        print(f"{r[0]:<15} ({r[1]:,} txns)")
    print(f"\nTotal: {len(rows)} distinct values")
    
    # Get distinct GXPJNO (project numbers)
    print("\n" + "=" * 60)
    print("GXPJNO (Project Numbers)")
    print("=" * 60)
    result = conn.execute(text("""
        SELECT DISTINCT gxpjno, COUNT(*) as cnt
        FROM gl_transactions 
        WHERE gxpjno IS NOT NULL AND TRIM(gxpjno) != ''
        GROUP BY gxpjno
        ORDER BY gxpjno
    """))
    rows = result.fetchall()
    for r in rows:
        print(f"{r[0]:<15} ({r[1]:,} txns)")
    print(f"\nTotal: {len(rows)} distinct values")
    
    # Get distinct CTUF01 (department codes from account master)
    print("\n" + "=" * 60)
    print("CTUF01 (Account Department Codes)")
    print("=" * 60)
    result = conn.execute(text("""
        SELECT DISTINCT ctuf01, COUNT(*) as cnt
        FROM gl_accounts 
        WHERE ctuf01 IS NOT NULL AND TRIM(ctuf01) != ''
        GROUP BY ctuf01
        ORDER BY ctuf01
    """))
    rows = result.fetchall()
    for r in rows:
        print(f"{r[0]:<15} ({r[1]:,} accounts)")
    print(f"\nTotal: {len(rows)} distinct values")
    
    conn.close()


if __name__ == "__main__":
    main()

