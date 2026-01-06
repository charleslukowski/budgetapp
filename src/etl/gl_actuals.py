"""
ETL for GL Actuals from Infinium DB2 to PostgreSQL.

Full refresh approach: truncate and reload for specified year/month.
"""

import pandas as pd
from datetime import datetime
from sqlalchemy import text
from src.db.infinium import get_infinium_connection
from src.db.postgres import get_engine, init_db
from src.models.gl_transaction import GLTransaction


# SQL query for GL actuals
GL_ACTUALS_QUERY = """
SELECT 
    GXJRNL,
    GXACCT,
    GXCO,
    TXYEAR,
    TXMNTH,
    THEDAT,
    TH8DAT,
    GXFAMT,
    GXDRCR,
    CTDESC,
    GXDESC,
    GXDSC2,
    THSRC,
    THREF,
    "GXVND#" AS GXVNDNUM,
    GXVNDN,
    GXPJCO,
    GXPJNO,
    PHDESC,
    GXPJDEPT,
    GXPJDESC,
    GXPWBS,
    WBDESC,
    GXWBS,
    WBSSUB01,
    WBSSUB02,
    GXEQFC,
    GXEQUN,
    GXEQOS,
    GXEQSC,
    GXEQCL,
    GXEQTY,
    "GXEQ#" AS GXEQNUM,
    GXEQCT,
    "GXEQC#" AS GXEQCNUM,
    GXEQDV,
    GXEQAR,
    GXEQNM,
    INVSUB01,
    INVSUB02,
    INVSUB03,
    POSUB01,
    POSUB02,
    POSUB03,
    POSUB04,
    POSUB05,
    CNSUB01,
    CNSUB02,
    CNSUB03,
    CNSUB04,
    GXSHUT,
    GXPREF,
    GXRFTY,
    "GXRF#" AS GXRFNUM,
    GXPLAN,
    GXCTID,
    GXWOTD
FROM GLCUFA.GLPTX1 
WHERE TXYEAR = {year}
"""


def extract_gl_actuals(year: int, month: int = None) -> pd.DataFrame:
    """
    Extract GL actuals from Infinium DB2.
    
    Args:
        year: Fiscal year (e.g., 2025)
        month: Optional month (1-12). If None, extracts full year.
        
    Returns:
        DataFrame with GL transactions
    """
    print(f"[EXTRACT] Connecting to Infinium DB2...")
    conn = get_infinium_connection()
    
    query = GL_ACTUALS_QUERY.format(year=year)
    if month:
        query += f" AND TXMNTH = {month}"
    
    print(f"[EXTRACT] Running query for {year}" + (f"-{month:02d}" if month else " full year") + "...")
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    print(f"[EXTRACT] Retrieved {len(df):,} rows")
    return df


def transform_gl_actuals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform GL actuals data.
    
    Args:
        df: Raw DataFrame from DB2
        
    Returns:
        Transformed DataFrame ready for PostgreSQL
    """
    print(f"[TRANSFORM] Processing {len(df):,} rows...")
    
    # Lowercase column names to match PostgreSQL model
    df.columns = df.columns.str.lower()
    
    # Strip whitespace from string columns
    str_columns = df.select_dtypes(include=['object']).columns
    for col in str_columns:
        df[col] = df[col].str.strip() if df[col].dtype == 'object' else df[col]
    
    # Convert date column
    if 'thedat' in df.columns:
        df['thedat'] = pd.to_datetime(df['thedat'], errors='coerce')
    
    print(f"[TRANSFORM] Complete")
    return df


def load_gl_actuals(year: int, month: int = None):
    """
    Full refresh ETL for GL actuals.
    
    Args:
        year: Fiscal year
        month: Optional month. If None, loads full year.
    """
    start_time = datetime.now()
    print("=" * 60)
    print(f"GL Actuals ETL - {year}" + (f"-{month:02d}" if month else " Full Year"))
    print("=" * 60)
    
    # Initialize database tables if needed
    print("[INIT] Ensuring database tables exist...")
    init_db()
    
    # Extract
    df = extract_gl_actuals(year, month)
    
    if df.empty:
        print("[LOAD] No data to load")
        return
    
    # Transform
    df = transform_gl_actuals(df)
    
    # Load
    print(f"[LOAD] Loading to PostgreSQL...")
    engine = get_engine()
    
    # Delete existing data for this period
    with engine.connect() as conn:
        if month:
            delete_sql = text(f"DELETE FROM gl_transactions WHERE txyear = {year} AND txmnth = {month}")
        else:
            delete_sql = text(f"DELETE FROM gl_transactions WHERE txyear = {year}")
        
        result = conn.execute(delete_sql)
        deleted = result.rowcount
        conn.commit()
        print(f"[LOAD] Deleted {deleted:,} existing rows")
    
    # Insert new data
    df.to_sql(
        'gl_transactions',
        engine,
        if_exists='append',
        index=False,
        method='multi',
        chunksize=1000
    )
    
    elapsed = datetime.now() - start_time
    print(f"[LOAD] Inserted {len(df):,} rows")
    print("=" * 60)
    print(f"Complete in {elapsed.total_seconds():.1f} seconds")
    print("=" * 60)


if __name__ == "__main__":
    # Default: load current year
    import sys
    
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    month = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    load_gl_actuals(year, month)

