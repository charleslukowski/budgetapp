"""Export endpoints for downloading data as CSV."""

import csv
import io
from typing import Optional
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from src.db.postgres import get_engine

router = APIRouter(prefix="/api/export", tags=["exports"])


PLANT_NAMES = {
    "KC": "Kyger Creek",
    "CC": "Clifty Creek"
}


def create_csv_response(filename: str, headers: list, rows: list) -> StreamingResponse:
    """Create a streaming CSV response."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/budget/{plant_code}/{year}")
async def export_budget(plant_code: str, year: int):
    """Export budget data to CSV."""
    
    engine = get_engine()
    plant_entity = "Kyger" if plant_code == "KC" else "Clifty"
    
    with engine.connect() as conn:
        query = text("""
            SELECT 
                department,
                full_account,
                account_description,
                line_description,
                labor_nonlabor,
                jan, feb, mar, apr, may, jun,
                jul, aug, sep, oct, nov, dec,
                total
            FROM budget_lines
            WHERE budget_year = :year AND budget_entity = :entity
            ORDER BY department, full_account
        """)
        result = conn.execute(query, {"year": year, "entity": plant_entity})
        rows = result.fetchall()
    
    headers = [
        "Department", "Account", "Account Description", "Line Description",
        "Labor/Non-Labor", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Total"
    ]
    
    data_rows = []
    for row in rows:
        data_rows.append([
            row[0] or "",
            row[1] or "",
            row[2] or "",
            row[3] or "",
            row[4] or "",
            float(row[5]) if row[5] else 0,
            float(row[6]) if row[6] else 0,
            float(row[7]) if row[7] else 0,
            float(row[8]) if row[8] else 0,
            float(row[9]) if row[9] else 0,
            float(row[10]) if row[10] else 0,
            float(row[11]) if row[11] else 0,
            float(row[12]) if row[12] else 0,
            float(row[13]) if row[13] else 0,
            float(row[14]) if row[14] else 0,
            float(row[15]) if row[15] else 0,
            float(row[16]) if row[16] else 0,
            float(row[17]) if row[17] else 0,
        ])
    
    filename = f"{plant_code}_Budget_{year}.csv"
    return create_csv_response(filename, headers, data_rows)


@router.get("/forecast/{plant_code}/{year}")
async def export_forecast(plant_code: str, year: int):
    """Export forecast data to CSV."""
    
    engine = get_engine()
    
    with engine.connect() as conn:
        # Get saved forecasts
        query = text("""
            SELECT 
                dept_code,
                jan, feb, mar, apr, may, jun,
                jul, aug, sep, oct, nov, dec,
                total
            FROM department_forecasts
            WHERE plant_code = :plant_code AND budget_year = :year
            ORDER BY dept_code
        """)
        result = conn.execute(query, {"plant_code": plant_code, "year": year})
        rows = result.fetchall()
    
    headers = [
        "Department", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Total"
    ]
    
    data_rows = []
    for row in rows:
        data_rows.append([
            row[0] or "",
            float(row[1]) if row[1] else 0,
            float(row[2]) if row[2] else 0,
            float(row[3]) if row[3] else 0,
            float(row[4]) if row[4] else 0,
            float(row[5]) if row[5] else 0,
            float(row[6]) if row[6] else 0,
            float(row[7]) if row[7] else 0,
            float(row[8]) if row[8] else 0,
            float(row[9]) if row[9] else 0,
            float(row[10]) if row[10] else 0,
            float(row[11]) if row[11] else 0,
            float(row[12]) if row[12] else 0,
            float(row[13]) if row[13] else 0,
        ])
    
    filename = f"{plant_code}_Forecast_{year}.csv"
    return create_csv_response(filename, headers, data_rows)


@router.get("/variance/{plant_code}/{year}")
async def export_variance(plant_code: str, year: int, month: Optional[int] = None):
    """Export variance report to CSV."""
    
    engine = get_engine()
    plant_entity = "Kyger" if plant_code == "KC" else "Clifty"
    current_month = month or 11
    
    with engine.connect() as conn:
        # Get YTD actuals by department
        actuals_query = text("""
            SELECT 
                dept_code,
                SUM(gxfamt) as total_amt
            FROM transaction_budget_groups
            WHERE txyear = :year 
              AND plant_code = :plant_code 
              AND txmnth <= :month
            GROUP BY dept_code
        """)
        actuals_result = conn.execute(actuals_query, {
            "year": year, 
            "plant_code": plant_code,
            "month": current_month
        })
        actuals_rows = actuals_result.fetchall()
        
        # Get YTD budget by department
        budget_months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        budget_sum_cols = ' + '.join([f'COALESCE({m}, 0)' for m in budget_months[:current_month]])
        
        try:
            budget_query = text(f"""
                SELECT 
                    department,
                    SUM({budget_sum_cols}) as ytd_budget,
                    SUM(total) as annual_budget
                FROM budget_lines
                WHERE budget_year = :year AND budget_entity = :entity
                GROUP BY department
            """)
            budget_result = conn.execute(budget_query, {"year": year, "entity": plant_entity})
            budget_rows = budget_result.fetchall()
        except Exception:
            budget_rows = []
        
        # Get explanations
        expl_query = text("""
            SELECT dept_code, explanation
            FROM variance_explanations
            WHERE plant_code = :plant_code AND budget_year = :year AND period_month = 0
        """)
        expl_result = conn.execute(expl_query, {"plant_code": plant_code, "year": year})
        expl_rows = expl_result.fetchall()
    
    # Build data
    actuals_by_dept = {row[0]: float(row[1]) if row[1] else 0 for row in actuals_rows}
    budgets_by_dept = {row[0]: {"ytd": float(row[1]) if row[1] else 0, "annual": float(row[2]) if row[2] else 0} for row in budget_rows}
    expl_by_dept = {row[0]: row[1] for row in expl_rows}
    
    all_depts = set(actuals_by_dept.keys()) | set(budgets_by_dept.keys())
    
    headers = ["Department", "YTD Actual", "YTD Budget", "Variance $", "Variance %", "Annual Budget", "Explanation"]
    
    data_rows = []
    for dept in sorted(all_depts):
        actual = actuals_by_dept.get(dept, 0)
        budget_info = budgets_by_dept.get(dept, {"ytd": 0, "annual": 0})
        ytd_budget = budget_info["ytd"]
        variance = ytd_budget - actual
        variance_pct = (variance / ytd_budget * 100) if ytd_budget != 0 else 0
        
        data_rows.append([
            dept,
            actual,
            ytd_budget,
            variance,
            f"{variance_pct:.1f}%",
            budget_info["annual"],
            expl_by_dept.get(dept, "")
        ])
    
    filename = f"{plant_code}_Variance_{year}_M{current_month}.csv"
    return create_csv_response(filename, headers, data_rows)


@router.get("/funding/{plant_code}/{year}")
async def export_funding(plant_code: str, year: int):
    """Export funding changes to CSV."""
    
    engine = get_engine()
    
    with engine.connect() as conn:
        query = text("""
            SELECT 
                change_type,
                status,
                department,
                account,
                amount,
                from_department,
                from_account,
                to_department,
                to_account,
                reallocation_amount,
                reason,
                requested_by,
                approved_by,
                created_at,
                approved_at
            FROM funding_changes
            WHERE plant_code = :plant_code AND budget_year = :year
            ORDER BY created_at DESC
        """)
        result = conn.execute(query, {"plant_code": plant_code, "year": year})
        rows = result.fetchall()
    
    headers = [
        "Type", "Status", "Department", "Account", "Amount",
        "From Department", "From Account", "To Department", "To Account", 
        "Reallocation Amount", "Reason", "Requested By", "Approved By",
        "Created At", "Approved At"
    ]
    
    data_rows = []
    for row in rows:
        data_rows.append([
            row[0] or "",
            row[1] or "",
            row[2] or "",
            row[3] or "",
            float(row[4]) if row[4] else "",
            row[5] or "",
            row[6] or "",
            row[7] or "",
            row[8] or "",
            float(row[9]) if row[9] else "",
            row[10] or "",
            row[11] or "",
            row[12] or "",
            row[13].isoformat() if row[13] else "",
            row[14].isoformat() if row[14] else "",
        ])
    
    filename = f"{plant_code}_FundingChanges_{year}.csv"
    return create_csv_response(filename, headers, data_rows)

