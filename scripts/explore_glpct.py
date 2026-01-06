"""
Explore GLDBFA.GLPCT account master table.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.db.infinium import get_infinium_connection
import pandas as pd


def main():
    print("=" * 60)
    print("Exploring GLDBFA.GLPCT (Account Master)")
    print("=" * 60)
    
    conn = get_infinium_connection()
    print("[OK] Connected to DB2")
    
    # Get columns
    print("\n--- COLUMNS ---")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, LENGTH 
        FROM QSYS2.SYSCOLUMNS 
        WHERE TABLE_NAME = 'GLPCT' AND TABLE_SCHEMA = 'GLDBFA'
        ORDER BY ORDINAL_POSITION
    """)
    columns = cursor.fetchall()
    print(f"{'Column':<20} {'Type':<15} {'Length'}")
    print("-" * 50)
    for col in columns:
        print(f"{col[0]:<20} {col[1]:<15} {col[2]}")
    
    # Get row count
    print("\n--- ROW COUNT ---")
    cursor.execute("SELECT COUNT(*) FROM GLDBFA.GLPCT WHERE CTACTV='1' AND CTMORS='M' AND CTCO='003'")
    count = cursor.fetchone()[0]
    print(f"Active OVEC accounts: {count:,}")
    
    # Sample data
    print("\n--- SAMPLE DATA (5 rows) ---")
    df = pd.read_sql(
        "SELECT * FROM GLDBFA.GLPCT WHERE CTACTV='1' AND CTMORS='M' AND CTCO='003' FETCH FIRST 5 ROWS ONLY",
        conn
    )
    print(df.to_string())
    
    conn.close()
    print("\n[OK] Done")


if __name__ == "__main__":
    main()

