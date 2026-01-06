"""
Explore GLCUFA.GLPTX1 table structure and sample data.

Run this script to see available columns and sample records.

Usage:
    python scripts/explore_glptx1.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import pyodbc
    import pandas as pd
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip install pyodbc pandas python-dotenv")
    sys.exit(1)

# Load environment variables
load_dotenv(project_root / '.env')


def get_connection():
    """Create DB2 connection via ODBC DSN."""
    dsn = os.getenv('DB2_DSN', 'CRYSTAL-CLIENT EXPRESS')
    username = os.getenv('INFINIUM_USER')
    password = os.getenv('INFINIUM_PW')
    
    if not username or not password:
        raise ValueError("INFINIUM_USER and INFINIUM_PW must be set in .env")
    
    conn_string = f'DSN={dsn};UID={username};PWD={password}'
    return pyodbc.connect(conn_string)


def explore_table():
    """Explore GLPTX1 table structure and sample data."""
    
    print("=" * 60)
    print("Exploring GLCUFA.GLPTX1")
    print("=" * 60)
    
    try:
        conn = get_connection()
        print("[OK] Connected to DB2")
        
        cursor = conn.cursor()
        
        # Get column info (iSeries/AS400 catalog)
        print("\n--- COLUMNS ---")
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, LENGTH, NUMERIC_SCALE, IS_NULLABLE
            FROM QSYS2.SYSCOLUMNS 
            WHERE TABLE_NAME = 'GLPTX1' AND TABLE_SCHEMA = 'GLCUFA'
            ORDER BY ORDINAL_POSITION
        """)
        
        columns = cursor.fetchall()
        print(f"{'Column':<20} {'Type':<15} {'Length':<8} {'Scale':<6} {'Nulls'}")
        print("-" * 60)
        for col in columns:
            col_name = col[0] or ''
            col_type = col[1] or ''
            col_len = col[2] if col[2] is not None else ''
            col_scale = col[3] if col[3] is not None else ''
            col_nulls = col[4] or ''
            print(f"{col_name:<20} {col_type:<15} {str(col_len):<8} {str(col_scale):<6} {col_nulls}")
        
        # Get row count
        print("\n--- ROW COUNT ---")
        cursor.execute("SELECT COUNT(*) FROM GLCUFA.GLPTX1 WHERE TXYEAR = 2025")
        count = cursor.fetchone()[0]
        print(f"Rows for 2025: {count:,}")
        
        # Get sample data
        print("\n--- SAMPLE DATA (5 rows) ---")
        df = pd.read_sql(
            "SELECT * FROM GLCUFA.GLPTX1 WHERE TXYEAR = 2025 FETCH FIRST 5 ROWS ONLY",
            conn
        )
        print(df.to_string())
        
        # Save full column list to file
        output_file = project_root / 'data' / 'queries' / 'infinium' / 'glptx1_columns.txt'
        with open(output_file, 'w') as f:
            f.write("GLCUFA.GLPTX1 Columns\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"{'Column':<20} {'Type':<15} {'Length':<8} {'Scale':<6} {'Nulls'}\n")
            f.write("-" * 60 + "\n")
            for col in columns:
                col_name = col[0] or ''
                col_type = col[1] or ''
                col_len = col[2] if col[2] is not None else ''
                col_scale = col[3] if col[3] is not None else ''
                col_nulls = col[4] or ''
                f.write(f"{col_name:<20} {col_type:<15} {str(col_len):<8} {str(col_scale):<6} {col_nulls}\n")
        print(f"\n[OK] Column list saved to: {output_file}")
        
        conn.close()
        print("\n[OK] Done")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    explore_table()

