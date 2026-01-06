"""
Load mapping CSV files into PostgreSQL.
"""

import pandas as pd
from pathlib import Path
from sqlalchemy.orm import sessionmaker
from src.db.postgres import get_engine
from src.models.mapping_tables import Base, ProjectMapping, AccountDeptMapping
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Path to master data CSVs
MASTER_DATA_DIR = Path(__file__).parent.parent.parent / 'data' / 'master'


def load_project_mappings():
    """Load project_mappings.csv into PostgreSQL."""
    logging.info("Loading project_mappings.csv...")
    
    csv_path = MASTER_DATA_DIR / 'project_mappings.csv'
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    
    # Read CSV, skip comment lines
    df = pd.read_csv(csv_path, comment='#')
    logging.info(f"Read {len(df)} project mappings from CSV")
    
    # Get database session
    engine = get_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Delete existing mappings (full refresh)
        deleted = session.query(ProjectMapping).delete()
        logging.info(f"Deleted {deleted} existing project mappings")
        
        # Insert new mappings
        for _, row in df.iterrows():
            mapping = ProjectMapping(
                project_number=str(row['project_number']).strip(),
                txn_count=int(row['txn_count']) if pd.notna(row['txn_count']) else 0,
                dept_code=str(row['dept_code']).strip()
            )
            session.add(mapping)
        
        session.commit()
        logging.info(f"Inserted {len(df)} project mappings")
        
    except Exception as e:
        session.rollback()
        logging.error(f"Failed to load project mappings: {e}")
        raise
    finally:
        session.close()


def load_account_dept_mappings():
    """Load account_dept_mappings.csv into PostgreSQL."""
    logging.info("Loading account_dept_mappings.csv...")
    
    csv_path = MASTER_DATA_DIR / 'account_dept_mappings.csv'
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    
    # Read CSV, skip comment lines
    df = pd.read_csv(csv_path, comment='#')
    logging.info(f"Read {len(df)} account dept mappings from CSV")
    
    # Get database session
    engine = get_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Delete existing mappings (full refresh)
        deleted = session.query(AccountDeptMapping).delete()
        logging.info(f"Deleted {deleted} existing account dept mappings")
        
        # Insert new mappings
        for _, row in df.iterrows():
            mapping = AccountDeptMapping(
                ctuf01=str(row['ctuf01']).strip(),
                account_count=int(row['account_count']) if pd.notna(row['account_count']) else 0,
                dept_code=str(row['dept_code']).strip()
            )
            session.add(mapping)
        
        session.commit()
        logging.info(f"Inserted {len(df)} account dept mappings")
        
    except Exception as e:
        session.rollback()
        logging.error(f"Failed to load account dept mappings: {e}")
        raise
    finally:
        session.close()


def load_all_mappings():
    """Load all mapping tables."""
    logging.info("=" * 60)
    logging.info("Loading Mapping Tables")
    logging.info("=" * 60)
    
    load_project_mappings()
    load_account_dept_mappings()
    
    logging.info("=" * 60)
    logging.info("All mappings loaded successfully")
    logging.info("=" * 60)


if __name__ == "__main__":
    load_all_mappings()

