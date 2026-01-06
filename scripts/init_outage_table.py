"""Initialize the unit_outage_inputs table in the database.

This script:
1. Creates the unit_outage_inputs table if it doesn't exist
2. Optionally seeds with sample outage data for testing
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import inspect
from src.db.postgres import get_engine
from src.database import Base
from src.models.unit_outage import UnitOutageInput


def create_table():
    """Create the unit_outage_inputs table."""
    engine = get_engine()
    inspector = inspect(engine)
    
    existing_tables = inspector.get_table_names()
    
    if "unit_outage_inputs" in existing_tables:
        print("Table 'unit_outage_inputs' already exists.")
        return
    
    print("Creating 'unit_outage_inputs' table...")
    UnitOutageInput.__table__.create(engine)
    print("Table created successfully.")


def seed_sample_data():
    """Optionally seed with sample outage data."""
    from decimal import Decimal
    from src.db.postgres import get_session
    from src.models.unit_outage import upsert_unit_outage
    
    print("\nSeeding sample outage data for 2025...")
    
    with get_session() as db:
        # Kyger Creek (plant_id=1): Typical outage pattern
        # Unit 1: April outage (3 weeks)
        # Unit 2: October outage (3 weeks)
        sample_outages_kc = [
            (1, 4, 21, "MAJOR", "Spring overhaul"),
            (2, 10, 21, "MAJOR", "Fall overhaul"),
            (3, 3, 7, "MINOR", "Boiler inspection"),
            (4, 9, 7, "MINOR", "Turbine inspection"),
        ]
        
        for unit, month, days, otype, desc in sample_outages_kc:
            upsert_unit_outage(
                db,
                plant_id=1,
                unit_number=unit,
                year=2025,
                month=month,
                planned_outage_days=Decimal(str(days)),
                forced_outage_days=Decimal("0"),
                outage_type=otype,
                outage_description=desc,
                updated_by="init_script",
            )
            print(f"  KC Unit {unit}, Month {month}: {days} days ({otype})")
        
        # Clifty Creek (plant_id=2): Similar pattern
        # Note: Unit 6 has no SCR, may have reduced operations in ozone season
        sample_outages_cc = [
            (1, 4, 28, "MAJOR", "Spring overhaul"),
            (2, 10, 28, "MAJOR", "Fall overhaul"),
            (3, 3, 10, "MINOR", "Boiler inspection"),
            (5, 9, 10, "MINOR", "Turbine inspection"),
            # Unit 6 - no planned outages but will be curtailed during ozone season
        ]
        
        for unit, month, days, otype, desc in sample_outages_cc:
            upsert_unit_outage(
                db,
                plant_id=2,
                unit_number=unit,
                year=2025,
                month=month,
                planned_outage_days=Decimal(str(days)),
                forced_outage_days=Decimal("0"),
                outage_type=otype,
                outage_description=desc,
                updated_by="init_script",
            )
            print(f"  CC Unit {unit}, Month {month}: {days} days ({otype})")
    
    print("Sample data seeded successfully.")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize unit outage table")
    parser.add_argument("--seed", action="store_true", help="Seed sample data")
    args = parser.parse_args()
    
    create_table()
    
    if args.seed:
        seed_sample_data()
    
    print("\nDone!")


if __name__ == "__main__":
    main()

