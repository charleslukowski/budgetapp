"""
Summary API endpoints.
"""

from fastapi import APIRouter, Query
from sqlalchemy import text
from decimal import Decimal
from typing import List, Optional

from src.db.postgres import get_engine
from src.api.schemas import (
    CorporateSummary, PlantSummary, DepartmentSummary, MonthlyAmount
)

router = APIRouter()


@router.get("/summary/{year}", response_model=CorporateSummary)
async def get_corporate_summary(
    year: int,
    current_month: int = Query(default=11, description="Current month for YTD calculations")
):
    """
    Get corporate-level summary with plant and department breakdowns.
    """
    engine = get_engine()
    
    with engine.connect() as conn:
        # Get monthly actuals by plant and department
        query = text("""
            SELECT 
                plant_code,
                dept_code,
                txmnth,
                SUM(gxfamt) as total_amt,
                COUNT(*) as txn_count
            FROM transaction_budget_groups
            WHERE txyear = :year
            GROUP BY plant_code, dept_code, txmnth
            ORDER BY plant_code, dept_code, txmnth
        """)
        
        result = conn.execute(query, {"year": year})
        rows = result.fetchall()
    
    # Build summary structure
    plants_data = {}
    
    for row in rows:
        plant_code = row[0]
        dept_code = row[1]
        month = row[2]
        amount = Decimal(str(row[3])) if row[3] else Decimal("0")
        
        # Initialize plant if not exists
        if plant_code not in plants_data:
            plants_data[plant_code] = {
                "plant_code": plant_code,
                "plant_name": "Kyger Creek" if plant_code == "KC" else "Clifty Creek",
                "departments": {}
            }
        
        # Initialize department if not exists
        if dept_code not in plants_data[plant_code]["departments"]:
            plants_data[plant_code]["departments"][dept_code] = {
                "dept_code": dept_code,
                "dept_name": dept_code,  # TODO: lookup from departments table
                "plant_code": plant_code,
                "is_outage": dept_code.startswith("PLANNED") or dept_code == "UNPLANNED" or dept_code == "OUTAGE",
                "months": {m: {"month": m, "actual": Decimal("0")} for m in range(1, 13)}
            }
        
        # Add amount to month
        plants_data[plant_code]["departments"][dept_code]["months"][month]["actual"] = amount
    
    # Convert to response models
    plants = []
    grand_total_actual = Decimal("0")
    
    for plant_code, plant_data in plants_data.items():
        departments = []
        plant_total = Decimal("0")
        
        for dept_code, dept_data in plant_data["departments"].items():
            months = [
                MonthlyAmount(
                    month=m,
                    actual=dept_data["months"][m]["actual"],
                    budget=Decimal("0"),  # TODO: from budget table
                    forecast=Decimal("0"),  # TODO: from forecast table
                    variance=Decimal("0")
                )
                for m in range(1, 13)
            ]
            
            ytd_actual = sum(
                dept_data["months"][m]["actual"] 
                for m in range(1, current_month + 1)
            )
            plant_total += ytd_actual
            
            departments.append(DepartmentSummary(
                dept_code=dept_code,
                dept_name=dept_data["dept_name"],
                plant_code=plant_code,
                is_outage=dept_data["is_outage"],
                months=months,
                ytd_actual=ytd_actual,
                ytd_budget=Decimal("0"),
                ytd_variance=Decimal("0"),
                year_end_projection=ytd_actual  # Simplified for now
            ))
        
        # Sort departments: non-outage first, then outage
        departments.sort(key=lambda d: (d.is_outage, d.dept_code))
        
        grand_total_actual += plant_total
        
        plants.append(PlantSummary(
            plant_code=plant_code,
            plant_name=plant_data["plant_name"],
            departments=departments,
            total_actual=plant_total,
            total_budget=Decimal("0"),
            total_variance=Decimal("0")
        ))
    
    return CorporateSummary(
        year=year,
        current_month=current_month,
        plants=plants,
        grand_total_actual=grand_total_actual,
        grand_total_budget=Decimal("0"),
        grand_total_variance=Decimal("0")
    )


@router.get("/departments/{plant_code}/{year}/{month}")
async def get_department_summary(
    plant_code: str,
    year: int,
    month: int
):
    """
    Get department summary for a specific plant and month.
    """
    engine = get_engine()
    
    with engine.connect() as conn:
        query = text("""
            SELECT 
                dept_code,
                outage_group,
                SUM(gxfamt) as total_amt,
                COUNT(*) as txn_count
            FROM transaction_budget_groups
            WHERE plant_code = :plant_code 
              AND txyear = :year 
              AND txmnth = :month
            GROUP BY dept_code, outage_group
            ORDER BY dept_code
        """)
        
        result = conn.execute(query, {
            "plant_code": plant_code,
            "year": year,
            "month": month
        })
        rows = result.fetchall()
    
    departments = []
    for row in rows:
        departments.append({
            "dept_code": row[0],
            "outage_group": row[1],
            "total_amount": float(row[2]) if row[2] else 0,
            "transaction_count": row[3]
        })
    
    return {
        "plant_code": plant_code,
        "year": year,
        "month": month,
        "departments": departments
    }

