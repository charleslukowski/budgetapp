"""Initialize new database tables for fuel model enhancements.

Creates tables for:
- use_factor_inputs
- heat_rate_inputs  
- coal_contract_pricing
- uncommitted_coal_prices

Run this script once to create the tables.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import inspect
from src.database import engine, Base
from src.models import (
    UseFactorInput,
    HeatRateInput,
    CoalContractPricing,
    UncommittedCoalPrice,
)


def check_table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def create_tables():
    """Create new tables if they don't exist."""
    tables_to_create = [
        ('use_factor_inputs', UseFactorInput),
        ('heat_rate_inputs', HeatRateInput),
        ('coal_contract_pricing', CoalContractPricing),
        ('uncommitted_coal_prices', UncommittedCoalPrice),
    ]
    
    print("Checking and creating fuel model tables...")
    print("-" * 50)
    
    for table_name, model in tables_to_create:
        if check_table_exists(table_name):
            print(f"  [EXISTS] {table_name}")
        else:
            print(f"  [CREATE] {table_name}")
            model.__table__.create(engine)
    
    print("-" * 50)
    print("Done!")


if __name__ == "__main__":
    create_tables()

