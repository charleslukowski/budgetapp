"""
Year-End Budget Rollover Script.

Copies approved budgets from budget_entries to department_forecasts table
to initialize the new year's forecast with approved budget values.

Usage:
    python scripts/year_rollover.py                 # Rollover current year to next
    python scripts/year_rollover.py 2025 2026       # Rollover 2025 budget to 2026 forecast
    python scripts/year_rollover.py 2025 2026 KC    # Rollover only Kyger Creek
"""

import sys
from pathlib import Path
from datetime import datetime
from decimal import Decimal

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.db.postgres import get_engine, get_session


def rollover_budget_to_forecast(
    source_year: int,
    target_year: int,
    plant_code: str = None
):
    """
    Copy approved budget entries to department_forecasts for the target year.
    
    Args:
        source_year: Year to copy budget from
        target_year: Year to create forecasts for
        plant_code: Optional plant filter (KC or CC)
    """
    engine = get_engine()
    session = get_session()
    
    print(f"Year-End Rollover: {source_year} Budget -> {target_year} Forecast")
    print("=" * 60)
    
    stats = {
        "departments_processed": 0,
        "forecasts_created": 0,
        "forecasts_updated": 0,
        "total_amount": Decimal("0"),
        "plants": []
    }
    
    try:
        with engine.connect() as conn:
            # Build plant filter
            plant_filter = ""
            params = {"source_year": source_year}
            
            if plant_code:
                plant_filter = "AND s.plant_code = :plant_code"
                params["plant_code"] = plant_code
            
            # Get approved budget entries grouped by department
            query = text(f"""
                SELECT 
                    s.plant_code,
                    e.dept_code,
                    SUM(e.jan) as jan,
                    SUM(e.feb) as feb,
                    SUM(e.mar) as mar,
                    SUM(e.apr) as apr,
                    SUM(e.may) as may,
                    SUM(e.jun) as jun,
                    SUM(e.jul) as jul,
                    SUM(e.aug) as aug,
                    SUM(e.sep) as sep,
                    SUM(e.oct) as oct,
                    SUM(e.nov) as nov,
                    SUM(e.dec) as dec,
                    SUM(e.total) as total
                FROM budget_entries e
                JOIN budget_submissions s ON s.id = e.submission_id
                WHERE s.budget_year = :source_year
                  AND s.status = 'approved'
                  {plant_filter}
                GROUP BY s.plant_code, e.dept_code
                ORDER BY s.plant_code, e.dept_code
            """)
            
            result = conn.execute(query, params)
            rows = result.fetchall()
            
            if not rows:
                print(f"No approved budgets found for {source_year}")
                return stats
            
            print(f"Found {len(rows)} department budgets to rollover")
            print()
            
            for row in rows:
                plant = row[0]
                dept = row[1]
                monthly = [float(row[i]) if row[i] else 0 for i in range(2, 14)]
                total = float(row[14]) if row[14] else 0
                
                # Check if forecast already exists
                check_query = text("""
                    SELECT id FROM department_forecasts
                    WHERE plant_code = :plant_code
                      AND dept_code = :dept_code
                      AND budget_year = :year
                """)
                existing = conn.execute(check_query, {
                    "plant_code": plant,
                    "dept_code": dept,
                    "year": target_year
                }).fetchone()
                
                if existing:
                    # Update existing forecast
                    update_query = text("""
                        UPDATE department_forecasts
                        SET jan = :jan, feb = :feb, mar = :mar,
                            apr = :apr, may = :may, jun = :jun,
                            jul = :jul, aug = :aug, sep = :sep,
                            oct = :oct, nov = :nov, dec = :dec,
                            total = :total,
                            updated_at = NOW(),
                            notes = :notes
                        WHERE id = :id
                    """)
                    conn.execute(update_query, {
                        "id": existing[0],
                        "jan": monthly[0], "feb": monthly[1], "mar": monthly[2],
                        "apr": monthly[3], "may": monthly[4], "jun": monthly[5],
                        "jul": monthly[6], "aug": monthly[7], "sep": monthly[8],
                        "oct": monthly[9], "nov": monthly[10], "dec": monthly[11],
                        "total": total,
                        "notes": f"Rolled over from {source_year} approved budget"
                    })
                    stats["forecasts_updated"] += 1
                    action = "Updated"
                else:
                    # Insert new forecast
                    insert_query = text("""
                        INSERT INTO department_forecasts
                        (plant_code, dept_code, budget_year,
                         jan, feb, mar, apr, may, jun,
                         jul, aug, sep, oct, nov, dec,
                         total, notes, created_at, updated_at)
                        VALUES
                        (:plant_code, :dept_code, :year,
                         :jan, :feb, :mar, :apr, :may, :jun,
                         :jul, :aug, :sep, :oct, :nov, :dec,
                         :total, :notes, NOW(), NOW())
                    """)
                    conn.execute(insert_query, {
                        "plant_code": plant,
                        "dept_code": dept,
                        "year": target_year,
                        "jan": monthly[0], "feb": monthly[1], "mar": monthly[2],
                        "apr": monthly[3], "may": monthly[4], "jun": monthly[5],
                        "jul": monthly[6], "aug": monthly[7], "sep": monthly[8],
                        "oct": monthly[9], "nov": monthly[10], "dec": monthly[11],
                        "total": total,
                        "notes": f"Rolled over from {source_year} approved budget"
                    })
                    stats["forecasts_created"] += 1
                    action = "Created"
                
                stats["departments_processed"] += 1
                stats["total_amount"] += Decimal(str(total))
                
                if plant not in stats["plants"]:
                    stats["plants"].append(plant)
                
                total_fmt = "{:,.0f}".format(total)
                print(f"  {action}: {plant}/{dept} = ${total_fmt}")
            
            conn.commit()
        
        print()
        print("=" * 60)
        print("Rollover Complete!")
        print("=" * 60)
        print(f"  Plants processed:     {', '.join(stats['plants'])}")
        print(f"  Departments:          {stats['departments_processed']}")
        print(f"  Forecasts created:    {stats['forecasts_created']}")
        print(f"  Forecasts updated:    {stats['forecasts_updated']}")
        print(f"  Total forecast:       ${stats['total_amount']:,.2f}")
        print("=" * 60)
        
    except Exception as e:
        print(f"Error during rollover: {e}")
        session.rollback()
        raise
    finally:
        session.close()
    
    return stats


def main():
    current_year = datetime.now().year
    
    # Parse arguments
    if len(sys.argv) >= 3:
        source_year = int(sys.argv[1])
        target_year = int(sys.argv[2])
    elif len(sys.argv) == 2:
        source_year = int(sys.argv[1])
        target_year = source_year + 1
    else:
        source_year = current_year
        target_year = current_year + 1
    
    plant_code = sys.argv[3] if len(sys.argv) > 3 else None
    
    rollover_budget_to_forecast(source_year, target_year, plant_code)


if __name__ == "__main__":
    main()

