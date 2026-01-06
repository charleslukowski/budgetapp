"""Load coal starting inventory for forecast years.

This script populates the coal_starting_inventory table with January 1st
beginning inventory values derived from previous December's ending inventory.

Usage:
    python scripts/load_starting_inventory.py

Or specify specific values:
    python scripts/load_starting_inventory.py --year 2026 --kyger 1012816 --clifty 1400579
"""

import argparse
import csv
import sys
from pathlib import Path
from decimal import Decimal

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.postgres import get_session
from src.models.actuals import CoalStartingInventory, CoalInventory


def get_december_ending_inventory(db, year: int, plant_id: int) -> Decimal:
    """Get December ending inventory for a given year and plant."""
    period_yyyymm = f"{year}12"
    inventory = db.query(CoalInventory).filter(
        CoalInventory.plant_id == plant_id,
        CoalInventory.period_yyyymm == period_yyyymm,
    ).first()
    
    if inventory and inventory.ending_inventory_tons:
        return inventory.ending_inventory_tons
    return None


def load_from_csv(db, csv_path: Path) -> dict:
    """Load starting inventory from monthly_ending_coal_qty.csv.
    
    Uses December ending inventory as January beginning inventory for the next year.
    """
    stats = {"loaded": 0, "updated": 0, "errors": 0}
    
    # Read all December values from CSV
    december_values = {}  # {(year, plant_id): ending_qty}
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            period = row.get("YYYYMM", "").strip().strip('"')
            if not period or len(period) != 6:
                continue
            
            # Only December values
            if not period.endswith("12"):
                continue
            
            year = int(period[:4])
            company_id = row.get("COMPANY_ID", "").strip().strip('"')
            plant_id = 1 if company_id == "1" else 2
            ending_qty = Decimal(row.get("PERIODENDQTY", "0").strip().strip('"'))
            
            december_values[(year, plant_id)] = ending_qty
    
    print(f"Found {len(december_values)} December ending inventory values")
    
    # Create starting inventory for next year
    for (dec_year, plant_id), ending_qty in december_values.items():
        starting_year = dec_year + 1
        plant_name = "Kyger" if plant_id == 1 else "Clifty"
        
        # Check if already exists
        existing = db.query(CoalStartingInventory).filter(
            CoalStartingInventory.year == starting_year,
            CoalStartingInventory.plant_id == plant_id,
        ).first()
        
        if existing:
            existing.beginning_inventory_tons = ending_qty
            existing.source = f"From Dec {dec_year} ending inventory (CSV import)"
            stats["updated"] += 1
            print(f"  Updated {starting_year} {plant_name}: {ending_qty:,.0f} tons")
        else:
            new_record = CoalStartingInventory(
                year=starting_year,
                plant_id=plant_id,
                beginning_inventory_tons=ending_qty,
                source=f"From Dec {dec_year} ending inventory (CSV import)",
            )
            db.add(new_record)
            stats["loaded"] += 1
            print(f"  Created {starting_year} {plant_name}: {ending_qty:,.0f} tons")
    
    db.commit()
    return stats


def set_manual_inventory(db, year: int, kyger_tons: Decimal, clifty_tons: Decimal, source: str = "Manual entry") -> dict:
    """Set starting inventory manually for a specific year."""
    stats = {"loaded": 0, "updated": 0}
    
    for plant_id, tons in [(1, kyger_tons), (2, clifty_tons)]:
        plant_name = "Kyger" if plant_id == 1 else "Clifty"
        
        existing = db.query(CoalStartingInventory).filter(
            CoalStartingInventory.year == year,
            CoalStartingInventory.plant_id == plant_id,
        ).first()
        
        if existing:
            existing.beginning_inventory_tons = tons
            existing.source = source
            stats["updated"] += 1
            print(f"  Updated {year} {plant_name}: {tons:,.0f} tons")
        else:
            new_record = CoalStartingInventory(
                year=year,
                plant_id=plant_id,
                beginning_inventory_tons=tons,
                source=source,
            )
            db.add(new_record)
            stats["loaded"] += 1
            print(f"  Created {year} {plant_name}: {tons:,.0f} tons")
    
    db.commit()
    return stats


def show_current_inventory(db):
    """Display current starting inventory values."""
    records = db.query(CoalStartingInventory).order_by(
        CoalStartingInventory.year, 
        CoalStartingInventory.plant_id
    ).all()
    
    if not records:
        print("No starting inventory records found.")
        return
    
    print("\nCurrent Starting Inventory Values:")
    print("-" * 60)
    for r in records:
        plant_name = "Kyger Creek" if r.plant_id == 1 else "Clifty Creek"
        print(f"  {r.year} | {plant_name:15} | {float(r.beginning_inventory_tons):>12,.0f} tons | {r.source or ''}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Load coal starting inventory")
    parser.add_argument("--from-csv", action="store_true", help="Load from monthly_ending_coal_qty.csv")
    parser.add_argument("--year", type=int, help="Year to set manually")
    parser.add_argument("--kyger", type=float, help="Kyger starting inventory (tons)")
    parser.add_argument("--clifty", type=float, help="Clifty starting inventory (tons)")
    parser.add_argument("--source", type=str, default="Manual entry", help="Source description")
    parser.add_argument("--show", action="store_true", help="Show current inventory values")
    
    args = parser.parse_args()
    
    with get_session() as db:
        if args.show:
            show_current_inventory(db)
            return
        
        if args.from_csv:
            csv_path = Path(__file__).parent.parent / "docs" / "source_documents" / "monthly_ending_coal_qty.csv"
            if not csv_path.exists():
                print(f"Error: CSV file not found at {csv_path}")
                return
            
            print(f"Loading starting inventory from {csv_path}")
            stats = load_from_csv(db, csv_path)
            print(f"\nComplete: {stats['loaded']} created, {stats['updated']} updated")
            show_current_inventory(db)
            
        elif args.year and args.kyger is not None and args.clifty is not None:
            print(f"Setting {args.year} starting inventory manually:")
            stats = set_manual_inventory(
                db, 
                args.year, 
                Decimal(str(args.kyger)), 
                Decimal(str(args.clifty)),
                args.source
            )
            print(f"\nComplete: {stats['loaded']} created, {stats['updated']} updated")
            show_current_inventory(db)
            
        else:
            print("Usage:")
            print("  Load from CSV:     python scripts/load_starting_inventory.py --from-csv")
            print("  Set manually:      python scripts/load_starting_inventory.py --year 2026 --kyger 1012816 --clifty 1400579")
            print("  Show current:      python scripts/load_starting_inventory.py --show")


if __name__ == "__main__":
    main()
