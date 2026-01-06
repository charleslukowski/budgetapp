"""
ETL for GL Account Master from Infinium DB2 to PostgreSQL.

Full refresh approach: truncate and reload all active accounts.
"""

import pandas as pd
from datetime import datetime
from sqlalchemy import text
from src.db.infinium import get_infinium_connection
from src.db.postgres import get_engine, init_db
from src.models.gl_account import GLAccount


# SQL query for account master
GL_ACCOUNTS_QUERY = """
SELECT 
    CTACCT,
    CTDESC,
    CTCO,
    CTACTV,
    CTMORS,
    CTUF01,
    CTUF02,
    CTUF03,
    CTUF04,
    CTRC01,
    CTRC02,
    CTRC03,
    CTRC04,
    CTRC05,
    CTRC06,
    CTRC07,
    CTRC08,
    CTRC09
FROM GLDBFA.GLPCT 
WHERE CTACTV = '1' 
  AND CTMORS = 'M' 
  AND CTCO = '003'
"""


def extract_gl_accounts() -> pd.DataFrame:
    """
    Extract GL accounts from Infinium DB2.
    
    Returns:
        DataFrame with GL accounts
    """
    print(f"[EXTRACT] Connecting to Infinium DB2...")
    conn = get_infinium_connection()
    
    print(f"[EXTRACT] Running query for active OVEC accounts...")
    df = pd.read_sql(GL_ACCOUNTS_QUERY, conn)
    conn.close()
    
    print(f"[EXTRACT] Retrieved {len(df):,} accounts")
    return df


def transform_gl_accounts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform GL accounts data.
    
    Args:
        df: Raw DataFrame from DB2
        
    Returns:
        Transformed DataFrame ready for PostgreSQL
    """
    print(f"[TRANSFORM] Processing {len(df):,} accounts...")
    
    # Lowercase column names
    df.columns = df.columns.str.lower()
    
    # Strip whitespace from string columns
    str_columns = df.select_dtypes(include=['object']).columns
    for col in str_columns:
        df[col] = df[col].str.strip() if df[col].dtype == 'object' else df[col]
    
    print(f"[TRANSFORM] Complete")
    return df


def load_gl_accounts():
    """
    Full refresh ETL for GL accounts.
    """
    start_time = datetime.now()
    print("=" * 60)
    print("GL Account Master ETL")
    print("=" * 60)
    
    # Initialize database tables if needed
    print("[INIT] Ensuring database tables exist...")
    init_db()
    
    # Extract
    df = extract_gl_accounts()
    
    if df.empty:
        print("[LOAD] No data to load")
        return
    
    # Transform
    df = transform_gl_accounts(df)
    
    # Load
    print(f"[LOAD] Loading to PostgreSQL...")
    engine = get_engine()
    
    # Delete all existing accounts
    with engine.connect() as conn:
        result = conn.execute(text("DELETE FROM gl_accounts"))
        deleted = result.rowcount
        conn.commit()
        print(f"[LOAD] Deleted {deleted:,} existing accounts")
    
    # Insert new data
    df.to_sql(
        'gl_accounts',
        engine,
        if_exists='append',
        index=False,
        method='multi',
        chunksize=500
    )
    
    elapsed = datetime.now() - start_time
    print(f"[LOAD] Inserted {len(df):,} accounts")
    print("=" * 60)
    print(f"Complete in {elapsed.total_seconds():.1f} seconds")
    print("=" * 60)


if __name__ == "__main__":
    load_gl_accounts()

