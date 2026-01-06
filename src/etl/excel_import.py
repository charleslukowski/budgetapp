"""Import forecast data from Excel files."""

from decimal import Decimal
from pathlib import Path
from typing import Optional
import pandas as pd
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.models import Plant, Period, CostCategory, Scenario, Forecast
from src.models.period import Granularity


def import_forecast_excel(
    file_path: str,
    scenario_id: int,
    plant_id: Optional[int] = None,
    db: Session = None,
) -> dict:
    """
    Import forecast data from an Excel file.
    
    Expected Excel format:
    - First column: Category name or short_name
    - Subsequent columns: Period headers (e.g., "Jan 2025", "2026", etc.)
    - Values: Cost amounts in dollars
    
    Args:
        file_path: Path to Excel file
        scenario_id: Target scenario ID
        plant_id: Optional plant ID (None for combined)
        db: Database session (creates one if not provided)
    
    Returns:
        dict with import statistics
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    try:
        # Read Excel file
        df = pd.read_excel(file_path, sheet_name=0)
        
        # Get the first column as category identifier
        category_col = df.columns[0]
        period_cols = df.columns[1:]
        
        # Load reference data
        categories = {c.short_name: c for c in db.query(CostCategory).all()}
        categories.update({c.name: c for c in db.query(CostCategory).all()})
        
        periods = {}
        for p in db.query(Period).all():
            # Create lookup keys for different formats
            if p.granularity == Granularity.MONTHLY:
                from calendar import month_abbr
                key1 = f"{month_abbr[p.month]} {p.year}"
                key2 = f"{p.month}/{p.year}"
                key3 = f"{p.year}-{p.month:02d}"
                periods[key1] = p
                periods[key2] = p
                periods[key3] = p
            else:
                periods[str(p.year)] = p
                periods[p.year] = p
        
        stats = {
            "rows_processed": 0,
            "forecasts_created": 0,
            "forecasts_updated": 0,
            "errors": [],
        }
        
        for _, row in df.iterrows():
            cat_name = str(row[category_col]).strip()
            
            # Skip empty rows or section headers
            if not cat_name or cat_name.upper() in ['FUEL COSTS', 'OPERATING COSTS', 'NON-OPERATING COSTS', 'CAPITAL COSTS']:
                continue
            
            # Remove leading spaces/indentation
            cat_name = cat_name.strip()
            
            category = categories.get(cat_name)
            if not category:
                stats["errors"].append(f"Category not found: {cat_name}")
                continue
            
            stats["rows_processed"] += 1
            
            for period_col in period_cols:
                period = periods.get(period_col) or periods.get(str(period_col))
                if not period:
                    continue
                
                value = row[period_col]
                if pd.isna(value) or value == '' or value == 0:
                    continue
                
                # Check if forecast exists
                existing = (
                    db.query(Forecast)
                    .filter(
                        Forecast.scenario_id == scenario_id,
                        Forecast.plant_id == plant_id,
                        Forecast.category_id == category.id,
                        Forecast.period_id == period.id,
                    )
                    .first()
                )
                
                if existing:
                    existing.cost_dollars = Decimal(str(value))
                    stats["forecasts_updated"] += 1
                else:
                    forecast = Forecast(
                        scenario_id=scenario_id,
                        plant_id=plant_id,
                        category_id=category.id,
                        period_id=period.id,
                        cost_dollars=Decimal(str(value)),
                    )
                    db.add(forecast)
                    stats["forecasts_created"] += 1
        
        db.commit()
        return stats
        
    finally:
        if close_db:
            db.close()


def import_generation_data(
    file_path: str,
    scenario_id: int,
    db: Session = None,
) -> dict:
    """
    Import generation data from Excel.
    
    Expected format:
    - Row per plant
    - Columns for each period
    - Values in MWh
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    try:
        df = pd.read_excel(file_path, sheet_name="Generation")
        
        plants = {p.name: p for p in db.query(Plant).all()}
        plants.update({p.short_name: p for p in db.query(Plant).all()})
        
        periods = {}
        for p in db.query(Period).all():
            if p.granularity == Granularity.MONTHLY:
                from calendar import month_abbr
                periods[f"{month_abbr[p.month]} {p.year}"] = p
            else:
                periods[str(p.year)] = p
        
        # Get a default category for generation (we store generation on forecast records)
        # Using the first fuel category as a proxy
        gen_category = db.query(CostCategory).first()
        
        stats = {"plants_processed": 0, "records_created": 0}
        
        plant_col = df.columns[0]
        for _, row in df.iterrows():
            plant_name = str(row[plant_col]).strip()
            plant = plants.get(plant_name)
            if not plant:
                continue
            
            stats["plants_processed"] += 1
            
            for col in df.columns[1:]:
                period = periods.get(col) or periods.get(str(col))
                if not period:
                    continue
                
                gen_value = row[col]
                if pd.isna(gen_value):
                    continue
                
                # Update or create forecast with generation
                existing = (
                    db.query(Forecast)
                    .filter(
                        Forecast.scenario_id == scenario_id,
                        Forecast.plant_id == plant.id,
                        Forecast.category_id == gen_category.id,
                        Forecast.period_id == period.id,
                    )
                    .first()
                )
                
                if existing:
                    existing.generation_mwh = Decimal(str(gen_value))
                else:
                    forecast = Forecast(
                        scenario_id=scenario_id,
                        plant_id=plant.id,
                        category_id=gen_category.id,
                        period_id=period.id,
                        generation_mwh=Decimal(str(gen_value)),
                    )
                    db.add(forecast)
                    stats["records_created"] += 1
        
        db.commit()
        return stats
        
    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python -m src.etl.excel_import <file_path> <scenario_id>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    scenario_id = int(sys.argv[2])
    
    print(f"Importing from {file_path} to scenario {scenario_id}...")
    result = import_forecast_excel(file_path, scenario_id)
    print(f"Results: {result}")

