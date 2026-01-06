"""
HTML page routes using Jinja2 templates.
"""

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pathlib import Path
from datetime import datetime
from collections import OrderedDict

from src.db.postgres import get_engine
from sqlalchemy import text
from decimal import Decimal

from src.engine.generation import (
    create_kyger_params, create_clifty_params,
    calculate_annual_generation, summarize_annual_generation,
    get_system_generation
)
from src.engine.fuel_model import (
    calculate_annual_fuel_costs, summarize_annual_fuel_costs,
    FuelModelInputs, calculate_system_fuel_costs
)
from src.engine.generation import create_kyger_params, create_clifty_params
from src.engine.coal_supply import calculate_coal_supply
from src.db.postgres import get_session

router = APIRouter()

# Set up templates
templates_path = Path(__file__).parent.parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

# Month name lookup
MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
}

PLANT_NAMES = {
    "KC": "Kyger Creek",
    "CC": "Clifty Creek"
}


@router.get("/summary/{year}", response_class=HTMLResponse)
async def summary_page(request: Request, year: int, plant_code: str = "KC"):
    """Render the monthly summary page."""
    
    # Current month (use November for demo, or actual current month)
    current_month = 11  # datetime.now().month
    
    engine = get_engine()
    
    with engine.connect() as conn:
        # Get monthly actuals by department
        query = text("""
            SELECT 
                dept_code,
                txmnth,
                SUM(gxfamt) as total_amt,
                CASE 
                    WHEN dept_code LIKE 'PLANNED-%' OR dept_code IN ('UNPLANNED', 'OUTAGE') THEN 'OUTAGE'
                    ELSE 'NON-OUTAGE'
                END as group_name
            FROM transaction_budget_groups
            WHERE txyear = :year AND plant_code = :plant_code
            GROUP BY dept_code, txmnth
            ORDER BY group_name DESC, dept_code, txmnth
        """)
        
        result = conn.execute(query, {"year": year, "plant_code": plant_code})
        rows = result.fetchall()
    
    # Build department data structure
    departments = {}
    
    for row in rows:
        dept_code = row[0]
        month = row[1]
        amount = float(row[2]) if row[2] else 0
        group_name = row[3]
        
        if dept_code not in departments:
            departments[dept_code] = {
                "dept_code": dept_code,
                "dept_name": dept_code,
                "group_name": group_name,
                "months": [{} for _ in range(12)],
                "ytd_actual": 0,
                "ytd_budget": 0,
                "year_end_projection": 0
            }
        
        # Store monthly data (0-indexed)
        if 1 <= month <= 12:
            departments[dept_code]["months"][month - 1] = {
                "month": month,
                "actual": amount,
                "forecast": 0,  # TODO: from forecast table
                "budget": 0     # TODO: from budget table
            }
            
            if month <= current_month:
                departments[dept_code]["ytd_actual"] += amount
    
    # Calculate year-end projection (simplified: YTD actual for now)
    for dept in departments.values():
        dept["year_end_projection"] = dept["ytd_actual"]
    
    # Group departments
    grouped = OrderedDict()
    grouped["OUTAGE"] = []
    grouped["NON-OUTAGE"] = []
    
    for dept in departments.values():
        if dept["group_name"] == "OUTAGE":
            grouped["OUTAGE"].append(dept)
        else:
            grouped["NON-OUTAGE"].append(dept)
    
    # Sort within groups
    for group in grouped.values():
        group.sort(key=lambda d: d["dept_code"])
    
    # Calculate plant totals
    plant_total = {
        "ytd_actual": sum(d["ytd_actual"] for d in departments.values()),
        "budget": 0,
        "year_end_projection": sum(d["year_end_projection"] for d in departments.values())
    }
    
    return templates.TemplateResponse("monthly_summary.html", {
        "request": request,
        "year": year,
        "plant_code": plant_code,
        "plant_name": PLANT_NAMES.get(plant_code, plant_code),
        "current_month": current_month,
        "month_names": MONTH_NAMES,
        "grouped_departments": grouped,
        "plant_total": plant_total,
        "department_count": len(departments),
        "group_count": len([g for g in grouped.values() if g]),
        "last_updated": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "active_page": "summary"
    })


@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Redirect to default summary page."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/summary/2025")


@router.get("/forecast/{plant_code}", response_class=HTMLResponse)
async def forecast_page(request: Request, plant_code: str, year: int = 2025):
    """Render the forecast input page."""
    
    current_month = 11  # datetime.now().month
    engine = get_engine()
    actuals_rows = []
    budget_rows = []
    forecast_rows = []
    
    with engine.connect() as conn:
        # Get YTD actuals by department from transaction_budget_groups
        try:
            actuals_query = text("""
                SELECT 
                    dept_code,
                    txmnth,
                    SUM(gxfamt) as total_amt
                FROM transaction_budget_groups
                WHERE txyear = :year AND plant_code = :plant_code
                GROUP BY dept_code, txmnth
                ORDER BY dept_code, txmnth
            """)
            actuals_result = conn.execute(actuals_query, {"year": year, "plant_code": plant_code})
            actuals_rows = actuals_result.fetchall()
        except Exception:
            actuals_rows = []
        
        # Get budget by department from budget_lines
        plant_entity = "Kyger" if plant_code == "KC" else "Clifty"
        try:
            budget_query = text("""
                SELECT 
                    department,
                    SUM(jan) as jan, SUM(feb) as feb, SUM(mar) as mar,
                    SUM(apr) as apr, SUM(may) as may, SUM(jun) as jun,
                    SUM(jul) as jul, SUM(aug) as aug, SUM(sep) as sep,
                    SUM(oct) as oct, SUM(nov) as nov, SUM(dec) as dec,
                    SUM(total) as total
                FROM budget_lines
                WHERE budget_year = :year AND budget_entity = :entity
                GROUP BY department
                ORDER BY department
            """)
            budget_result = conn.execute(budget_query, {"year": year, "entity": plant_entity})
            budget_rows = budget_result.fetchall()
        except Exception:
            budget_rows = []
        
        # Get saved forecasts from department_forecasts (from approved budgets)
        try:
            forecast_query = text("""
                SELECT 
                    dept_code,
                    jan, feb, mar, apr, may, jun,
                    jul, aug, sep, oct, nov, dec,
                    total
                FROM department_forecasts
                WHERE budget_year = :year AND plant_code = :plant_code
                ORDER BY dept_code
            """)
            forecast_result = conn.execute(forecast_query, {"year": year, "plant_code": plant_code})
            forecast_rows = forecast_result.fetchall()
        except Exception:
            forecast_rows = []
    
    # Build department data structure
    departments = {}
    
    # Process actuals
    for row in actuals_rows:
        dept_code = row[0]
        month = row[1]
        amount = float(row[2]) if row[2] else 0
        
        if dept_code not in departments:
            departments[dept_code] = {
                "dept_code": dept_code,
                "actuals": [0] * 12,
                "budget": [0] * 12,
                "forecast": [0] * 12,
                "has_saved_forecast": False,
                "ytd_actual": 0,
                "ytd_budget": 0,
                "total_budget": 0
            }
        
        if 1 <= month <= 12:
            departments[dept_code]["actuals"][month - 1] = amount
            if month <= current_month:
                departments[dept_code]["ytd_actual"] += amount
    
    # Process budget
    month_cols = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
    for row in budget_rows:
        dept = row[0] or "UNKNOWN"
        if dept not in departments:
            departments[dept] = {
                "dept_code": dept,
                "actuals": [0] * 12,
                "budget": [0] * 12,
                "forecast": [0] * 12,
                "has_saved_forecast": False,
                "ytd_actual": 0,
                "ytd_budget": 0,
                "total_budget": 0
            }
        
        for i, col in enumerate(month_cols):
            val = float(row[i + 1]) if row[i + 1] else 0
            departments[dept]["budget"][i] = val
            if i < current_month:
                departments[dept]["ytd_budget"] += val
        
        departments[dept]["total_budget"] = float(row[13]) if row[13] else 0
        
        # Initialize forecast: YTD actuals + remaining budget (as default)
        for i in range(12):
            if i < current_month:
                departments[dept]["forecast"][i] = departments[dept]["actuals"][i]
            else:
                departments[dept]["forecast"][i] = departments[dept]["budget"][i]
    
    # Override with saved forecasts from department_forecasts table
    for row in forecast_rows:
        dept = row[0]
        if dept not in departments:
            departments[dept] = {
                "dept_code": dept,
                "actuals": [0] * 12,
                "budget": [0] * 12,
                "forecast": [0] * 12,
                "has_saved_forecast": True,
                "ytd_actual": 0,
                "ytd_budget": 0,
                "total_budget": 0
            }
        
        # Use saved forecast values
        departments[dept]["has_saved_forecast"] = True
        for i in range(12):
            val = float(row[i + 1]) if row[i + 1] else 0
            # For past months, use actuals; for future months, use saved forecast
            if i < current_month:
                departments[dept]["forecast"][i] = departments[dept]["actuals"][i]
            else:
                departments[dept]["forecast"][i] = val
    
    # Sort departments
    sorted_depts = sorted(departments.values(), key=lambda d: d["dept_code"])
    
    # Calculate totals
    totals = {
        "ytd_actual": sum(d["ytd_actual"] for d in departments.values()),
        "ytd_budget": sum(d["ytd_budget"] for d in departments.values()),
        "total_budget": sum(d["total_budget"] for d in departments.values()),
        "forecast": [sum(d["forecast"][i] for d in departments.values()) for i in range(12)]
    }
    
    return templates.TemplateResponse("forecast.html", {
        "request": request,
        "year": year,
        "plant_code": plant_code,
        "plant_name": PLANT_NAMES.get(plant_code, plant_code),
        "current_month": current_month,
        "month_names": MONTH_NAMES,
        "departments": sorted_depts,
        "totals": totals,
        "department_count": len(departments),
        "last_updated": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "active_page": "forecast"
    })


@router.get("/budget/{plant_code}", response_class=HTMLResponse)
async def budget_page(request: Request, plant_code: str, year: int = 2025):
    """Render the budget view page (read-only)."""
    
    engine = get_engine()
    plant_entity = "Kyger" if plant_code == "KC" else "Clifty"
    rows = []
    source = "budget_lines"
    
    with engine.connect() as conn:
        # Try budget_lines first (imported budget data)
        try:
            query = text("""
                SELECT 
                    department,
                    full_account,
                    account_description,
                    line_description,
                    labor_nonlabor,
                    jan, feb, mar, apr, may, jun,
                    jul, aug, sep, oct, nov, dec,
                    total,
                    ranking
                FROM budget_lines
                WHERE budget_year = :year AND budget_entity = :entity
                ORDER BY department, full_account
            """)
            result = conn.execute(query, {"year": year, "entity": plant_entity})
            rows = result.fetchall()
        except Exception:
            rows = []
        
        # If no budget_lines, try budget_entries (from budget entry workflow)
        if not rows:
            source = "budget_entries"
            try:
                query = text("""
                    SELECT 
                        e.dept_code,
                        e.account_code,
                        e.account_name,
                        e.line_description,
                        'N/A' as labor_nonlabor,
                        e.jan, e.feb, e.mar, e.apr, e.may, e.jun,
                        e.jul, e.aug, e.sep, e.oct, e.nov, e.dec,
                        e.total,
                        0 as ranking
                    FROM budget_entries e
                    JOIN budget_submissions s ON s.id = e.submission_id
                    WHERE s.plant_code = :plant_code AND s.budget_year = :year
                    ORDER BY e.dept_code, e.account_code
                """)
                result = conn.execute(query, {"plant_code": plant_code, "year": year})
                rows = result.fetchall()
            except Exception:
                rows = []
    
    # Build department structure
    departments = {}
    total_budget = 0
    
    for row in rows:
        dept = row[0] or "UNKNOWN"
        if dept not in departments:
            departments[dept] = {
                "dept_code": dept,
                "lines": [],
                "monthly_totals": [0] * 12,
                "total": 0
            }
        
        line = {
            "account": row[1],
            "account_desc": row[2],
            "description": row[3],
            "labor_type": row[4],
            "months": [float(row[i]) if row[i] else 0 for i in range(5, 17)],
            "total": float(row[17]) if row[17] else 0,
            "ranking": row[18]
        }
        
        departments[dept]["lines"].append(line)
        departments[dept]["total"] += line["total"]
        total_budget += line["total"]
        
        for i in range(12):
            departments[dept]["monthly_totals"][i] += line["months"][i]
    
    # Sort departments
    sorted_depts = sorted(departments.values(), key=lambda d: d["dept_code"])
    
    # Calculate grand totals by month
    grand_monthly_totals = [0] * 12
    for dept in departments.values():
        for i in range(12):
            grand_monthly_totals[i] += dept["monthly_totals"][i]
    
    return templates.TemplateResponse("budget.html", {
        "request": request,
        "year": year,
        "plant_code": plant_code,
        "plant_name": PLANT_NAMES.get(plant_code, plant_code),
        "month_names": MONTH_NAMES,
        "departments": sorted_depts,
        "total_budget": total_budget,
        "grand_monthly_totals": grand_monthly_totals,
        "department_count": len(departments),
        "line_count": sum(len(d["lines"]) for d in departments.values()),
        "last_updated": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "active_page": "budget",
        "data_source": source
    })


@router.get("/variance/{plant_code}", response_class=HTMLResponse)
async def variance_page(request: Request, plant_code: str, year: int = 2025, month: int = None):
    """Render the variance analysis page."""
    
    current_month = month or 11  # datetime.now().month
    engine = get_engine()
    plant_entity = "Kyger" if plant_code == "KC" else "Clifty"
    actuals_rows = []
    budget_rows = []
    
    with engine.connect() as conn:
        # Get YTD actuals by department
        try:
            actuals_query = text("""
                SELECT 
                    dept_code,
                    SUM(gxfamt) as total_amt
                FROM transaction_budget_groups
                WHERE txyear = :year 
                  AND plant_code = :plant_code 
                  AND txmnth <= :month
                GROUP BY dept_code
                ORDER BY dept_code
            """)
            actuals_result = conn.execute(actuals_query, {
                "year": year, 
                "plant_code": plant_code,
                "month": current_month
            })
            actuals_rows = actuals_result.fetchall()
        except Exception:
            actuals_rows = []
        
        # Get YTD budget by department
        try:
            budget_months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
            budget_sum_cols = ' + '.join([f'COALESCE({m}, 0)' for m in budget_months[:current_month]])
            
            budget_query = text(f"""
                SELECT 
                    department,
                    SUM({budget_sum_cols}) as ytd_budget,
                    SUM(total) as annual_budget
                FROM budget_lines
                WHERE budget_year = :year AND budget_entity = :entity
                GROUP BY department
                ORDER BY department
            """)
            budget_result = conn.execute(budget_query, {"year": year, "entity": plant_entity})
            budget_rows = budget_result.fetchall()
        except Exception:
            budget_rows = []
    
    # Build variance data
    actuals_by_dept = {row[0]: float(row[1]) if row[1] else 0 for row in actuals_rows}
    budgets_by_dept = {row[0]: {"ytd": float(row[1]) if row[1] else 0, "annual": float(row[2]) if row[2] else 0} for row in budget_rows}
    
    all_depts = set(actuals_by_dept.keys()) | set(budgets_by_dept.keys())
    
    variance_lines = []
    total_actual = 0
    total_budget = 0
    total_variance = 0
    
    for dept in sorted(all_depts):
        actual = actuals_by_dept.get(dept, 0)
        budget_info = budgets_by_dept.get(dept, {"ytd": 0, "annual": 0})
        ytd_budget = budget_info["ytd"]
        variance = ytd_budget - actual  # Positive = favorable (under budget)
        
        variance_lines.append({
            "dept_code": dept,
            "ytd_actual": actual,
            "ytd_budget": ytd_budget,
            "annual_budget": budget_info["annual"],
            "variance": variance,
            "variance_pct": (variance / ytd_budget * 100) if ytd_budget != 0 else 0,
            "is_favorable": variance >= 0
        })
        
        total_actual += actual
        total_budget += ytd_budget
        total_variance += variance
    
    return templates.TemplateResponse("variance.html", {
        "request": request,
        "year": year,
        "plant_code": plant_code,
        "plant_name": PLANT_NAMES.get(plant_code, plant_code),
        "current_month": current_month,
        "month_names": MONTH_NAMES,
        "variance_lines": variance_lines,
        "total_actual": total_actual,
        "total_budget": total_budget,
        "total_variance": total_variance,
        "total_variance_pct": (total_variance / total_budget * 100) if total_budget != 0 else 0,
        "is_total_favorable": total_variance >= 0,
        "department_count": len(variance_lines),
        "last_updated": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "active_page": "variance"
    })


@router.get("/funding/{plant_code}", response_class=HTMLResponse)
async def funding_page(request: Request, plant_code: str, year: int = 2025):
    """Render the funding changes page."""
    
    engine = get_engine()
    plant_entity = "Kyger" if plant_code == "KC" else "Clifty"
    dept_rows = []
    change_rows = []
    
    with engine.connect() as conn:
        # Get budget summary by department for context
        try:
            query = text("""
                SELECT 
                    department,
                    SUM(total) as total_budget,
                    COUNT(*) as line_count
                FROM budget_lines
                WHERE budget_year = :year AND budget_entity = :entity
                GROUP BY department
                ORDER BY department
            """)
            result = conn.execute(query, {"year": year, "entity": plant_entity})
            dept_rows = result.fetchall()
        except Exception:
            dept_rows = []
        
        # Get funding changes from database
        try:
            changes_query = text("""
                SELECT 
                    id, change_type, status, department, account, amount,
                    from_department, from_account, to_department, to_account,
                    reallocation_amount, reason, requested_by, approved_by,
                    created_at, approved_at
                FROM funding_changes
                WHERE plant_code = :plant_code AND budget_year = :year
                ORDER BY created_at DESC
            """)
            changes_result = conn.execute(changes_query, {"plant_code": plant_code, "year": year})
            change_rows = changes_result.fetchall()
        except Exception:
            change_rows = []
    
    departments = []
    total_budget = 0
    
    for row in dept_rows:
        dept = {
            "dept_code": row[0] or "UNKNOWN",
            "total_budget": float(row[1]) if row[1] else 0,
            "line_count": row[2]
        }
        departments.append(dept)
        total_budget += dept["total_budget"]
    
    # Process funding changes
    funding_changes = []
    amendment_total = 0
    reallocation_total = 0
    
    for row in change_rows:
        change = {
            "id": row[0],
            "type": row[1],
            "status": row[2],
            "department": row[3] or (f"{row[6]} → {row[8]}" if row[6] else ""),
            "account": row[4] or "",
            "amount": float(row[5]) if row[5] else (float(row[10]) if row[10] else 0),
            "reason": row[11] or "",
            "requested_by": row[12] or "",
            "approved_by": row[13] or "",
            "created_at": row[14].strftime("%Y-%m-%d") if row[14] else "",
            "approved_at": row[15].strftime("%Y-%m-%d") if row[15] else ""
        }
        funding_changes.append(change)
        
        if change["status"] == "approved":
            if row[1] == "amendment":
                amendment_total += change["amount"]
            else:
                reallocation_total += change["amount"]
    
    return templates.TemplateResponse("funding.html", {
        "request": request,
        "year": year,
        "plant_code": plant_code,
        "plant_name": PLANT_NAMES.get(plant_code, plant_code),
        "month_names": MONTH_NAMES,
        "departments": departments,
        "total_budget": total_budget,
        "funding_changes": funding_changes,
        "amendment_total": amendment_total,
        "reallocation_total": reallocation_total,
        "department_count": len(departments),
        "last_updated": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "active_page": "funding"
    })


@router.get("/budget-entry/{plant_code}", response_class=HTMLResponse)
async def budget_entry_page(request: Request, plant_code: str, year: int = 2025, dept: str = None):
    """Render the budget entry page for a department."""
    
    engine = get_engine()
    plant_entity = "Kyger" if plant_code == "KC" else "Clifty"
    
    with engine.connect() as conn:
        # Get list of departments
        try:
            dept_query = text("""
                SELECT DISTINCT department
                FROM budget_lines
                WHERE budget_year = :year AND budget_entity = :entity AND department IS NOT NULL
                ORDER BY department
            """)
            dept_result = conn.execute(dept_query, {"year": year, "entity": plant_entity})
            dept_rows = dept_result.fetchall()
            departments = [{"dept_code": row[0], "dept_name": row[0]} for row in dept_rows]
        except Exception:
            # If no budget_lines, use generic departments
            departments = [
                {"dept_code": "OPS", "dept_name": "Operations"},
                {"dept_code": "MAINT", "dept_name": "Maintenance"},
                {"dept_code": "ADMIN", "dept_name": "Administration"},
            ]
        
        # Default to first department if none specified
        current_dept = dept if dept else (departments[0]["dept_code"] if departments else "OPS")
        
        # Get submission status for this department
        submission = None
        entries = []
        try:
            sub_query = text("""
                SELECT id, status, submitted_at, submitted_by, approved_at, approved_by, rejection_reason
                FROM budget_submissions
                WHERE plant_code = :plant_code AND dept_code = :dept_code AND budget_year = :year
            """)
            sub_result = conn.execute(sub_query, {"plant_code": plant_code, "dept_code": current_dept, "year": year})
            sub_row = sub_result.fetchone()
            
            if sub_row:
                submission = {
                    "id": sub_row[0],
                    "status": sub_row[1],
                    "submitted_at": sub_row[2].strftime("%Y-%m-%d %H:%M") if sub_row[2] else None,
                    "submitted_by": sub_row[3],
                    "approved_at": sub_row[4].strftime("%Y-%m-%d %H:%M") if sub_row[4] else None,
                    "approved_by": sub_row[5],
                    "rejection_reason": sub_row[6]
                }
                
                # Get entries for this submission
                entry_query = text("""
                    SELECT id, account_code, account_name, line_description,
                           jan, feb, mar, apr, may, jun, jul, aug, sep, oct, nov, dec, total, notes
                    FROM budget_entries
                    WHERE submission_id = :submission_id
                    ORDER BY account_code
                """)
                entry_result = conn.execute(entry_query, {"submission_id": sub_row[0]})
                entry_rows = entry_result.fetchall()
                
                for row in entry_rows:
                    months = [float(row[i]) if row[i] else 0 for i in range(4, 16)]
                    entries.append({
                        "id": row[0],
                        "account_code": row[1],
                        "account_name": row[2],
                        "line_description": row[3],
                        "months": months,
                        "total": float(row[16]) if row[16] else sum(months),
                        "notes": row[17]
                    })
        except Exception:
            pass
    
    # Calculate totals
    by_month = [0] * 12
    for entry in entries:
        for i, val in enumerate(entry["months"]):
            by_month[i] += val
    
    totals = {
        "q1": sum(by_month[0:3]),
        "q2": sum(by_month[3:6]),
        "q3": sum(by_month[6:9]),
        "q4": sum(by_month[9:12]),
        "annual": sum(by_month),
        "by_month": by_month
    }
    
    return templates.TemplateResponse("budget_entry.html", {
        "request": request,
        "year": year,
        "plant_code": plant_code,
        "plant_name": PLANT_NAMES.get(plant_code, plant_code),
        "month_names": MONTH_NAMES,
        "departments": departments,
        "current_dept": current_dept,
        "submission": submission,
        "entries": entries,
        "totals": totals,
        "last_updated": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "active_page": "budget_entry"
    })


@router.get("/budget-approval/{plant_code}", response_class=HTMLResponse)
async def budget_approval_page(request: Request, plant_code: str, year: int = 2025):
    """Render the budget approval page for managers."""
    
    engine = get_engine()
    
    with engine.connect() as conn:
        # Get all submissions with monthly totals
        try:
            query = text("""
                SELECT 
                    s.id, s.plant_code, s.dept_code, s.budget_year, s.status,
                    s.submitted_at, s.submitted_by, s.approved_at, s.approved_by, s.rejection_reason,
                    COALESCE(SUM(e.jan), 0) as jan,
                    COALESCE(SUM(e.feb), 0) as feb,
                    COALESCE(SUM(e.mar), 0) as mar,
                    COALESCE(SUM(e.apr), 0) as apr,
                    COALESCE(SUM(e.may), 0) as may,
                    COALESCE(SUM(e.jun), 0) as jun,
                    COALESCE(SUM(e.jul), 0) as jul,
                    COALESCE(SUM(e.aug), 0) as aug,
                    COALESCE(SUM(e.sep), 0) as sep,
                    COALESCE(SUM(e.oct), 0) as oct,
                    COALESCE(SUM(e.nov), 0) as nov,
                    COALESCE(SUM(e.dec), 0) as dec,
                    COALESCE(SUM(e.total), 0) as total_budget
                FROM budget_submissions s
                LEFT JOIN budget_entries e ON e.submission_id = s.id
                WHERE s.plant_code = :plant_code AND s.budget_year = :year
                GROUP BY s.id
                ORDER BY s.dept_code
            """)
            result = conn.execute(query, {"plant_code": plant_code, "year": year})
            rows = result.fetchall()
        except Exception:
            rows = []
    
    submissions = []
    status_counts = {}
    total_budget = 0
    totals = {"months": [0] * 12}
    
    for row in rows:
        months = [float(row[i]) if row[i] else 0 for i in range(10, 22)]
        sub = {
            "id": row[0],
            "plant_code": row[1],
            "dept_code": row[2],
            "budget_year": row[3],
            "status": row[4],
            "submitted_at": row[5].strftime("%Y-%m-%d") if row[5] else None,
            "submitted_by": row[6],
            "approved_at": row[7].strftime("%Y-%m-%d") if row[7] else None,
            "approved_by": row[8],
            "rejection_reason": row[9],
            "months": months,
            "total_budget": float(row[22]) if row[22] else 0
        }
        submissions.append(sub)
        
        status_counts[sub["status"]] = status_counts.get(sub["status"], 0) + 1
        total_budget += sub["total_budget"]
        for i in range(12):
            totals["months"][i] += months[i]
    
    return templates.TemplateResponse("budget_approval.html", {
        "request": request,
        "year": year,
        "plant_code": plant_code,
        "plant_name": PLANT_NAMES.get(plant_code, plant_code),
        "month_names": MONTH_NAMES,
        "submissions": submissions,
        "status_counts": status_counts,
        "total_budget": total_budget,
        "totals": totals,
        "last_updated": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "active_page": "budget_approval"
    })


# ============================================================
# Energy Model Pages
# ============================================================

@router.get("/generation/{plant_code}", response_class=HTMLResponse)
async def generation_page(request: Request, plant_code: str, year: int = 2025, use_factor: float = 0.85):
    """Render the generation dashboard page."""
    
    # Get plant parameters
    if plant_code.upper() == "KC":
        plant = create_kyger_params()
        plant_id = 1
    else:
        plant = create_clifty_params()
        plant_id = 2
    
    # Create monthly use factors
    monthly_use_factors = {m: Decimal(str(use_factor)) for m in range(1, 13)}
    
    # Calculate generation
    monthly_results = calculate_annual_generation(plant, year, monthly_use_factors)
    annual_summary = summarize_annual_generation(monthly_results)
    
    # Get system totals
    system = get_system_generation(year)
    
    # Build monthly data for display
    monthly_data = []
    for r in monthly_results:
        monthly_data.append({
            "month": r.period_month,
            "month_name": MONTH_NAMES[r.period_month],
            "hours": r.hours_in_period,
            "gross_mwh": float(r.gross_mwh_available),
            "fgd_aux_mwh": float(r.fgd_aux_mwh),
            "gsu_loss_mwh": float(r.gsu_loss_mwh),
            "reserve_mwh": float(r.reserve_mwh),
            "lack_of_sales_mwh": float(r.lack_of_sales_mwh),
            "net_mwh": float(r.net_delivered_mwh),
            "capacity_factor": float(r.capacity_factor) * 100,
            "use_factor": float(r.use_factor) * 100,
        })
    
    # Unit breakdown
    units = []
    for u in plant.units:
        units.append({
            "unit_number": u.unit_number,
            "capacity_mw": float(u.capacity_mw),
            "available": u.is_available,
            "availability_factor": float(u.availability_factor) * 100
        })
    
    return templates.TemplateResponse("generation.html", {
        "request": request,
        "year": year,
        "plant_code": plant_code.upper(),
        "plant_name": PLANT_NAMES.get(plant_code.upper(), plant_code),
        "month_names": MONTH_NAMES,
        "use_factor": use_factor,
        "monthly_data": monthly_data,
        "annual": annual_summary,
        "system": system,
        "units": units,
        "plant_capacity": float(plant.total_capacity_mw),
        "last_updated": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "active_page": "generation"
    })


@router.get("/fuel/{plant_code}", response_class=HTMLResponse)
async def fuel_page(request: Request, plant_code: str, year: int = 2025, use_factor: float = 0.85):
    """Render the fuel cost summary page."""
    
    # Get plant parameters
    if plant_code.upper() == "KC":
        plant = create_kyger_params()
        plant_id = 1
    else:
        plant = create_clifty_params()
        plant_id = 2
    
    # Create fuel model inputs
    inputs = FuelModelInputs(
        plant_params=plant,
        use_factor=Decimal(str(use_factor)),
    )
    
    # Calculate fuel costs
    with get_session() as db:
        monthly_results = calculate_annual_fuel_costs(db, plant_id, year, inputs)
        annual_summary = summarize_annual_fuel_costs(monthly_results)
        system = calculate_system_fuel_costs(db, year)
    
    # Build monthly data for display
    monthly_data = []
    for r in monthly_results:
        monthly_data.append({
            "month": r.period_month,
            "month_name": MONTH_NAMES[r.period_month],
            "net_mwh": float(r.net_delivered_mwh),
            "coal_tons": float(r.coal_tons_consumed),
            "coal_mmbtu": float(r.coal_mmbtu_consumed),
            "heat_rate": float(r.heat_rate),
            "coal_cost": float(r.coal_cost),
            "coal_cost_per_ton": float(r.coal_cost_per_ton),
            "coal_cost_per_mmbtu": float(r.coal_cost_per_mmbtu),
            "consumables_cost": float(r.consumables_cost),
            "urea_cost": float(r.urea_cost),
            "limestone_cost": float(r.limestone_cost),
            "byproduct_net": float(r.byproduct_net_cost),
            "byproduct_sales_revenue": float(r.byproduct_sales_revenue),
            "byproduct_disposal_costs": float(r.byproduct_disposal_costs),
            "byproduct_misc_expense": float(r.byproduct_misc_expense),
            "total_fuel_cost": float(r.total_fuel_cost),
            "fuel_cost_per_mwh": float(r.fuel_cost_per_mwh),
        })
    
    return templates.TemplateResponse("fuel.html", {
        "request": request,
        "year": year,
        "plant_code": plant_code.upper(),
        "plant_name": PLANT_NAMES.get(plant_code.upper(), plant_code),
        "month_names": MONTH_NAMES,
        "use_factor": use_factor,
        "monthly_data": monthly_data,
        "annual": annual_summary,
        "system": system,
        "last_updated": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "active_page": "fuel"
    })


@router.get("/fuel/system", response_class=HTMLResponse)
async def fuel_system_page(request: Request, year: int = 2025, use_factor: float = 0.85):
    """Render the combined system fuel cost summary page."""
    
    # Get plant parameters
    kyger = create_kyger_params()
    clifty = create_clifty_params()
    
    # Create fuel model inputs
    kyger_inputs = FuelModelInputs(
        plant_params=kyger,
        use_factor=Decimal(str(use_factor)),
    )
    clifty_inputs = FuelModelInputs(
        plant_params=clifty,
        use_factor=Decimal(str(use_factor)),
    )
    
    # Calculate fuel costs for both plants
    with get_session() as db:
        kyger_monthly = calculate_annual_fuel_costs(db, 1, year, kyger_inputs)
        clifty_monthly = calculate_annual_fuel_costs(db, 2, year, clifty_inputs)
        kyger_annual = summarize_annual_fuel_costs(kyger_monthly)
        clifty_annual = summarize_annual_fuel_costs(clifty_monthly)
    
    # Build monthly data for display - combined
    monthly_data = []
    for i in range(12):
        kr = kyger_monthly[i]
        cr = clifty_monthly[i]
        monthly_data.append({
            "month": kr.period_month,
            "month_name": MONTH_NAMES[kr.period_month],
            # Kyger
            "kyger_net_mwh": float(kr.net_delivered_mwh),
            "kyger_coal_cost": float(kr.coal_cost),
            "kyger_consumables_cost": float(kr.consumables_cost),
            "kyger_byproduct_net": float(kr.byproduct_net_cost),
            "kyger_byproduct_sales": float(kr.byproduct_sales_revenue),
            "kyger_byproduct_costs": float(kr.byproduct_disposal_costs + kr.byproduct_misc_expense),
            "kyger_total_fuel_cost": float(kr.total_fuel_cost),
            "kyger_fuel_cost_per_mwh": float(kr.fuel_cost_per_mwh),
            # Clifty
            "clifty_net_mwh": float(cr.net_delivered_mwh),
            "clifty_coal_cost": float(cr.coal_cost),
            "clifty_consumables_cost": float(cr.consumables_cost),
            "clifty_byproduct_net": float(cr.byproduct_net_cost),
            "clifty_byproduct_sales": float(cr.byproduct_sales_revenue),
            "clifty_byproduct_costs": float(cr.byproduct_disposal_costs + cr.byproduct_misc_expense),
            "clifty_total_fuel_cost": float(cr.total_fuel_cost),
            "clifty_fuel_cost_per_mwh": float(cr.fuel_cost_per_mwh),
            # System totals
            "system_net_mwh": float(kr.net_delivered_mwh + cr.net_delivered_mwh),
            "system_coal_cost": float(kr.coal_cost + cr.coal_cost),
            "system_consumables_cost": float(kr.consumables_cost + cr.consumables_cost),
            "system_byproduct_net": float(kr.byproduct_net_cost + cr.byproduct_net_cost),
            "system_byproduct_sales": float(kr.byproduct_sales_revenue + cr.byproduct_sales_revenue),
            "system_byproduct_costs": float(kr.byproduct_disposal_costs + kr.byproduct_misc_expense + cr.byproduct_disposal_costs + cr.byproduct_misc_expense),
            "system_total_fuel_cost": float(kr.total_fuel_cost + cr.total_fuel_cost),
            "system_fuel_cost_per_mwh": float((kr.total_fuel_cost + cr.total_fuel_cost) / (kr.net_delivered_mwh + cr.net_delivered_mwh)) if (kr.net_delivered_mwh + cr.net_delivered_mwh) > 0 else 0,
        })
    
    # Calculate system annual totals
    system_annual = {
        "total_mwh": kyger_annual["total_mwh"] + clifty_annual["total_mwh"],
        "total_coal_tons": kyger_annual["total_coal_tons"] + clifty_annual["total_coal_tons"],
        "total_coal_mmbtu": kyger_annual["total_coal_mmbtu"] + clifty_annual["total_coal_mmbtu"],
        "avg_heat_rate": (kyger_annual["avg_heat_rate"] + clifty_annual["avg_heat_rate"]) / 2,
        "total_coal_cost": kyger_annual["total_coal_cost"] + clifty_annual["total_coal_cost"],
        "total_consumables_cost": kyger_annual["total_consumables_cost"] + clifty_annual["total_consumables_cost"],
        "total_byproduct_sales_revenue": kyger_annual["total_byproduct_sales_revenue"] + clifty_annual["total_byproduct_sales_revenue"],
        "total_byproduct_disposal_costs": kyger_annual["total_byproduct_disposal_costs"] + clifty_annual["total_byproduct_disposal_costs"],
        "total_byproduct_misc_expense": kyger_annual["total_byproduct_misc_expense"] + clifty_annual["total_byproduct_misc_expense"],
        "total_byproduct_net": kyger_annual["total_byproduct_net"] + clifty_annual["total_byproduct_net"],
        "total_fuel_cost": kyger_annual["total_fuel_cost"] + clifty_annual["total_fuel_cost"],
    }
    total_mwh = system_annual["total_mwh"]
    system_annual["avg_fuel_cost_per_mwh"] = system_annual["total_fuel_cost"] / total_mwh if total_mwh > 0 else 0
    
    return templates.TemplateResponse("fuel_system.html", {
        "request": request,
        "year": year,
        "month_names": MONTH_NAMES,
        "use_factor": use_factor,
        "monthly_data": monthly_data,
        "kyger": kyger_annual,
        "clifty": clifty_annual,
        "system": system_annual,
        "last_updated": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "active_page": "fuel"
    })


@router.get("/coal/{plant_code}", response_class=HTMLResponse)
async def coal_page(request: Request, plant_code: str, year: int = 2025):
    """Render the coal inventory page."""
    
    plant_id = 1 if plant_code.upper() == "KC" else 2
    
    # Get coal supply data for each month
    monthly_data = []
    with get_session() as db:
        for month in range(1, 13):
            consumption = Decimal("80000")  # Estimate
            result = calculate_coal_supply(db, plant_id, year, month, consumption)
            
            monthly_data.append({
                "month": month,
                "month_name": MONTH_NAMES[month],
                "beginning_inventory": float(result.beginning_inventory_tons),
                "ending_inventory": float(result.ending_inventory_tons),
                "total_tons": float(result.total_tons),
                "total_cost": float(result.total_cost),
                "avg_cost_per_ton": float(result.weighted_avg_cost_per_ton),
                "avg_btu": float(result.weighted_avg_btu),
                "days_supply": float(result.days_supply),
                "source_count": len(result.sources),
            })
    
    # Calculate annual totals
    annual = {
        "total_tons": sum(m["total_tons"] for m in monthly_data),
        "total_cost": sum(m["total_cost"] for m in monthly_data),
        "avg_cost_per_ton": sum(m["avg_cost_per_ton"] for m in monthly_data) / 12 if monthly_data else 0,
        "avg_days_supply": sum(m["days_supply"] for m in monthly_data) / 12 if monthly_data else 0,
    }
    
    return templates.TemplateResponse("coal.html", {
        "request": request,
        "year": year,
        "plant_code": plant_code.upper(),
        "plant_name": PLANT_NAMES.get(plant_code.upper(), plant_code),
        "month_names": MONTH_NAMES,
        "monthly_data": monthly_data,
        "annual": annual,
        "last_updated": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "active_page": "coal"
    })


@router.get("/coal/system", response_class=HTMLResponse)
async def coal_system_page(request: Request, year: int = 2025):
    """Render the combined system coal inventory page."""
    
    # Get coal supply data for both plants
    kyger_monthly = []
    clifty_monthly = []
    
    with get_session() as db:
        for month in range(1, 13):
            consumption = Decimal("80000")  # Estimate
            
            # Kyger data
            kyger_result = calculate_coal_supply(db, 1, year, month, consumption)
            kyger_monthly.append({
                "month": month,
                "month_name": MONTH_NAMES[month],
                "beginning_inventory": float(kyger_result.beginning_inventory_tons),
                "ending_inventory": float(kyger_result.ending_inventory_tons),
                "total_tons": float(kyger_result.total_tons),
                "total_cost": float(kyger_result.total_cost),
                "avg_cost_per_ton": float(kyger_result.weighted_avg_cost_per_ton),
                "days_supply": float(kyger_result.days_supply),
            })
            
            # Clifty data
            clifty_result = calculate_coal_supply(db, 2, year, month, consumption)
            clifty_monthly.append({
                "month": month,
                "month_name": MONTH_NAMES[month],
                "beginning_inventory": float(clifty_result.beginning_inventory_tons),
                "ending_inventory": float(clifty_result.ending_inventory_tons),
                "total_tons": float(clifty_result.total_tons),
                "total_cost": float(clifty_result.total_cost),
                "avg_cost_per_ton": float(clifty_result.weighted_avg_cost_per_ton),
                "days_supply": float(clifty_result.days_supply),
            })
    
    # Build combined monthly data
    monthly_data = []
    for i in range(12):
        kr = kyger_monthly[i]
        cr = clifty_monthly[i]
        system_deliveries = kr["total_tons"] + cr["total_tons"]
        system_cost = kr["total_cost"] + cr["total_cost"]
        monthly_data.append({
            "month": kr["month"],
            "month_name": kr["month_name"],
            # Kyger
            "kyger_deliveries": kr["total_tons"],
            "kyger_cost": kr["total_cost"],
            "kyger_days_supply": kr["days_supply"],
            "kyger_ending_inventory": kr["ending_inventory"],
            # Clifty
            "clifty_deliveries": cr["total_tons"],
            "clifty_cost": cr["total_cost"],
            "clifty_days_supply": cr["days_supply"],
            "clifty_ending_inventory": cr["ending_inventory"],
            # System totals
            "system_deliveries": system_deliveries,
            "system_cost": system_cost,
            "system_cost_per_ton": system_cost / system_deliveries if system_deliveries > 0 else 0,
        })
    
    # Calculate annual totals for each plant
    kyger_annual = {
        "total_tons": sum(m["total_tons"] for m in kyger_monthly),
        "total_cost": sum(m["total_cost"] for m in kyger_monthly),
        "avg_cost_per_ton": sum(m["avg_cost_per_ton"] for m in kyger_monthly) / 12 if kyger_monthly else 0,
        "avg_days_supply": sum(m["days_supply"] for m in kyger_monthly) / 12 if kyger_monthly else 0,
        "beginning_inventory": kyger_monthly[0]["beginning_inventory"] if kyger_monthly else 0,
        "ending_inventory": kyger_monthly[-1]["ending_inventory"] if kyger_monthly else 0,
    }
    
    clifty_annual = {
        "total_tons": sum(m["total_tons"] for m in clifty_monthly),
        "total_cost": sum(m["total_cost"] for m in clifty_monthly),
        "avg_cost_per_ton": sum(m["avg_cost_per_ton"] for m in clifty_monthly) / 12 if clifty_monthly else 0,
        "avg_days_supply": sum(m["days_supply"] for m in clifty_monthly) / 12 if clifty_monthly else 0,
        "beginning_inventory": clifty_monthly[0]["beginning_inventory"] if clifty_monthly else 0,
        "ending_inventory": clifty_monthly[-1]["ending_inventory"] if clifty_monthly else 0,
    }
    
    # System annual totals
    system_annual = {
        "total_tons": kyger_annual["total_tons"] + clifty_annual["total_tons"],
        "total_cost": kyger_annual["total_cost"] + clifty_annual["total_cost"],
        "avg_cost_per_ton": (kyger_annual["total_cost"] + clifty_annual["total_cost"]) / 
                           (kyger_annual["total_tons"] + clifty_annual["total_tons"]) 
                           if (kyger_annual["total_tons"] + clifty_annual["total_tons"]) > 0 else 0,
    }
    
    return templates.TemplateResponse("coal_system.html", {
        "request": request,
        "year": year,
        "month_names": MONTH_NAMES,
        "monthly_data": monthly_data,
        "kyger": kyger_annual,
        "clifty": clifty_annual,
        "system": system_annual,
        "last_updated": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "active_page": "coal"
    })


@router.get("/energy-inputs/{plant_code}", response_class=HTMLResponse)
async def energy_inputs_page(request: Request, plant_code: str, year: int = 2025):
    """Redirect to the merged inputs page."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/inputs/{year}")


@router.get("/forecast-inputs/{year}", response_class=HTMLResponse)
async def forecast_inputs_page(request: Request, year: int):
    """Redirect to the merged inputs page."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/inputs/{year}")


@router.get("/inputs/{year}", response_class=HTMLResponse)
async def inputs_page(request: Request, year: int):
    """Render the comprehensive inputs page covering all fuel model parameters."""
    
    # =========================================================================
    # SECTION 1: USE FACTORS
    # =========================================================================
    use_factors_kc = {m: 85 for m in range(1, 13)}
    use_factors_cc = {m: 85 for m in range(1, 13)}
    use_factors_kc_ozone = {m: 0 for m in range(5, 10)}  # Ozone season (May-Sep)
    use_factors_cc_ozone = {m: 0 for m in range(5, 10)}
    
    # =========================================================================
    # SECTION 2: HEAT RATES
    # =========================================================================
    heat_rates_kc = {m: 9850 for m in range(1, 13)}
    heat_rates_cc = {m: 9900 for m in range(1, 13)}
    
    # =========================================================================
    # SECTION 3: UNIT OUTAGES (5 KC units, 6 CC units)
    # =========================================================================
    # Structure: {unit_number: {month: {planned, forced, reserve}}}
    outages_kc = {u: {m: {"planned": 0, "forced": 0, "reserve": 0} for m in range(1, 13)} for u in range(1, 6)}
    outages_cc = {u: {m: {"planned": 0, "forced": 0, "reserve": 0} for m in range(1, 13)} for u in range(1, 7)}
    
    # =========================================================================
    # SECTION 4: PLANT PARAMETERS
    # =========================================================================
    kc_unit_capacities = {u: 217 for u in range(1, 6)}  # KC has 5 units
    cc_unit_capacities = {u: 217 for u in range(1, 7)}  # CC has 6 units
    
    # =========================================================================
    # SECTION 7: COAL PRICING (monthly)
    # =========================================================================
    coal_prices_contract = {m: 65.00 for m in range(1, 13)}
    coal_prices_spot = {m: 72.00 for m in range(1, 13)}
    barge_prices = {m: 6.00 for m in range(1, 13)}
    
    # =========================================================================
    # SECTION 8: UREA PRICING (monthly override option)
    # =========================================================================
    urea_prices = {m: None for m in range(1, 13)}  # None means use default
    
    # =========================================================================
    # LOAD DATA FROM DATABASE
    # =========================================================================
    inventory_kc = 1012816
    inventory_cc = 1400579
    coal_contracts = []
    scenarios = []
    
    try:
        with get_session() as db:
            # Load inventory
            from src.models.actuals import CoalStartingInventory
            kc_inv = db.query(CoalStartingInventory).filter(
                CoalStartingInventory.year == year,
                CoalStartingInventory.plant_id == 1
            ).first()
            if kc_inv:
                inventory_kc = float(kc_inv.beginning_inventory_tons)
            
            cc_inv = db.query(CoalStartingInventory).filter(
                CoalStartingInventory.year == year,
                CoalStartingInventory.plant_id == 2
            ).first()
            if cc_inv:
                inventory_cc = float(cc_inv.beginning_inventory_tons)
            
            # Load coal contracts
            try:
                from src.models.coal_contract import CoalContract
                contracts = db.query(CoalContract).filter(
                    CoalContract.is_active == True
                ).all()
                for c in contracts:
                    coal_contracts.append({
                        "contract_id": c.contract_id,
                        "supplier": c.supplier,
                        "plant_name": "Kyger Creek" if c.plant_id == 1 else "Clifty Creek",
                        "annual_tons": float(c.annual_tons) if c.annual_tons else 0,
                        "min_tons": float(c.min_tons) if c.min_tons else 0,
                        "max_tons": float(c.max_tons) if c.max_tons else 0,
                        "coal_price_per_ton": float(c.coal_price_per_ton) if c.coal_price_per_ton else 0,
                        "btu_per_lb": float(c.btu_per_lb) if c.btu_per_lb else 0,
                        "so2_lb_per_mmbtu": float(c.so2_lb_per_mmbtu) if c.so2_lb_per_mmbtu else 0,
                        "end_date": c.end_date,
                    })
            except Exception:
                pass
            
            # Load unit outages if available
            try:
                from src.models.unit_outage import UnitOutageInput
                kc_outages = db.query(UnitOutageInput).filter(
                    UnitOutageInput.plant_id == 1,
                    UnitOutageInput.year == year
                ).all()
                for o in kc_outages:
                    if o.unit_number in outages_kc and o.month in outages_kc[o.unit_number]:
                        outages_kc[o.unit_number][o.month] = {
                            "planned": float(o.planned_outage_days or 0),
                            "forced": float(o.forced_outage_days or 0),
                            "reserve": float(o.reserve_shutdown_days or 0),
                        }
                
                cc_outages = db.query(UnitOutageInput).filter(
                    UnitOutageInput.plant_id == 2,
                    UnitOutageInput.year == year
                ).all()
                for o in cc_outages:
                    if o.unit_number in outages_cc and o.month in outages_cc[o.unit_number]:
                        outages_cc[o.unit_number][o.month] = {
                            "planned": float(o.planned_outage_days or 0),
                            "forced": float(o.forced_outage_days or 0),
                            "reserve": float(o.reserve_shutdown_days or 0),
                        }
            except Exception:
                pass
                
    except Exception:
        pass
    
    return templates.TemplateResponse("inputs.html", {
        "request": request,
        "year": year,
        "month_names": MONTH_NAMES,
        "scenarios": scenarios,
        
        # Section 1: Use Factors
        "use_factors_kc": use_factors_kc,
        "use_factors_cc": use_factors_cc,
        "use_factors_kc_ozone": use_factors_kc_ozone,
        "use_factors_cc_ozone": use_factors_cc_ozone,
        
        # Section 2: Heat Rates
        "heat_rates_kc": heat_rates_kc,
        "heat_rates_cc": heat_rates_cc,
        "hr_kc_min_load": 10500,
        "hr_cc_min_load": 10600,
        "hr_kc_suf": 0,
        "hr_cc_suf": 0,
        "hr_kc_prb_pct": 0,
        "hr_cc_prb_pct": 0,
        
        # Section 3: Unit Outages
        "outages_kc": outages_kc,
        "outages_cc": outages_cc,
        
        # Section 4: Plant Parameters
        "kc_fgd_aux_mw": 25,
        "kc_bioreactor_mw": 6,
        "kc_gsu_loss_pct": 0.5545,
        "kc_reserve_mw": 10,
        "cc_fgd_aux_mw": 30,
        "cc_bioreactor_mw": 6,
        "cc_gsu_loss_pct": 0.5545,
        "cc_reserve_mw": 10,
        "kc_unit_capacities": kc_unit_capacities,
        "cc_unit_capacities": cc_unit_capacities,
        
        # Section 5: Coal Quality
        "coal_kc_btu_lb": 12500,
        "coal_kc_so2": 5.60,
        "coal_kc_ash_pct": 10,
        "coal_kc_moisture_pct": 6,
        "coal_cc_btu_lb": 12500,
        "coal_cc_so2": 5.60,
        "coal_cc_ash_pct": 10,
        "coal_cc_moisture_pct": 6,
        
        # Section 6: Coal Contracts
        "coal_contracts": coal_contracts,
        
        # Section 7: Monthly Coal Pricing
        "coal_prices_contract": coal_prices_contract,
        "coal_prices_spot": coal_prices_spot,
        "barge_prices": barge_prices,
        "inventory_kc": inventory_kc,
        "inventory_cc": inventory_cc,
        "kc_target_days": 50,
        "cc_target_days": 50,
        
        # Section 8: Urea Parameters
        "urea_nox_removed": 0.50,
        "urea_lb_per_nox": 0.685,
        "urea_price_ton": 459,
        "urea_prices": urea_prices,
        
        # Section 9: Limestone Parameters
        "fgd_efficiency": 97.5,
        "limestone_ratio": 1.45,
        "limestone_caco3": 90.5,
        "limestone_moisture": 5,
        "limestone_price": 25,
        
        # Section 10: Other Consumables
        "lime_rate": 0.1,
        "lime_price": 150,
        "pac_rate": 0.5,
        "pac_price": 0.75,
        "bromide_rate": 0.01,
        "bromide_price": 2.50,
        
        # Section 11: Fixed Monthly Costs
        "bioreactor_reagent": 15000,
        "bioreactor_support": 25000,
        "wwtp_reagent": 8000,
        "misc_reagent": 5000,
        "fuel_oil_day": 500,
        "labor_handling_day": 2500,
        "temp_coal_storage": 0,
        "labor_escalation": 2.0,
        
        # Section 12: Byproduct Parameters
        "fly_ash_pct": 40,
        "fly_ash_sold_pct": 0,
        "fly_ash_sale_price": -1,
        "fly_ash_disposal": 4,
        "bottom_ash_pct": 60,
        "bottom_ash_sold_pct": 55,
        "bottom_ash_sale_price": -9,
        "bottom_ash_disposal": 4,
        "gypsum_ratio": 2.85,
        "gypsum_sold_pct": 80,
        "gypsum_sale_price": -17.50,
        "gypsum_pad_cost": 4,
        "gypsum_disposal": 4,
        "kc_byproduct_misc": 310000,
        "cc_byproduct_misc": 310000,
        
        # Section 13: Emissions & Allowances
        "nox_ozone_rate": 2500,
        "nox_non_ozone_rate": 500,
        "nox_uncontrolled": 0.60,
        "scr_efficiency": 90,
        "co2_rate": 205,
        "co2_tax": 0,
        
        # Section 14: Multi-Year Escalation
        "esc_coal_y2": 2.5, "esc_coal_y3": 2.5, "esc_coal_y4": 2.5, "esc_coal_y5": 2.5,
        "esc_transport_y2": 3.0, "esc_transport_y3": 3.0, "esc_transport_y4": 3.0, "esc_transport_y5": 3.0,
        "esc_reagent_y2": 2.0, "esc_reagent_y3": 2.0, "esc_reagent_y4": 2.0, "esc_reagent_y5": 2.0,
        "esc_labor_y2": 3.0, "esc_labor_y3": 3.0, "esc_labor_y4": 3.0, "esc_labor_y5": 3.0,
        "esc_byproduct_y2": 1.0, "esc_byproduct_y3": 1.0, "esc_byproduct_y4": 1.0, "esc_byproduct_y5": 1.0,
        "esc_allowance_y2": 5.0, "esc_allowance_y3": 5.0, "esc_allowance_y4": 5.0, "esc_allowance_y5": 5.0,
        
        "last_updated": datetime.now().strftime("%b %d, %Y"),
        "active_page": "fuel_forecast",
        "active_tab": "inputs"
    })


@router.get("/fuel-forecast/{year}", response_class=HTMLResponse)
async def fuel_forecast_single_page(request: Request, year: int):
    """Render the merged fuel forecast page with monthly Year 1 and annual Years 2-5."""
    
    # Get plant parameters
    kyger = create_kyger_params()
    clifty = create_clifty_params()
    
    # Default use factors (Year 1 monthly)
    use_factors_kc = {m: 85 for m in range(1, 13)}
    use_factors_cc = {m: 85 for m in range(1, 13)}
    
    # Default heat rates (Year 1 monthly) 
    heat_rates_kc = {m: 9850 for m in range(1, 13)}
    heat_rates_cc = {m: 9900 for m in range(1, 13)}
    
    # Try to get starting inventory from database
    inventory_kc = 1012816
    inventory_cc = 1400579
    try:
        with get_session() as db:
            from src.models.actuals import CoalStartingInventory
            kc_inv = db.query(CoalStartingInventory).filter(
                CoalStartingInventory.year == year,
                CoalStartingInventory.plant_id == 1
            ).first()
            if kc_inv:
                inventory_kc = float(kc_inv.beginning_inventory_tons)
            
            cc_inv = db.query(CoalStartingInventory).filter(
                CoalStartingInventory.year == year,
                CoalStartingInventory.plant_id == 2
            ).first()
            if cc_inv:
                inventory_cc = float(cc_inv.beginning_inventory_tons)
    except Exception:
        pass
    
    # Mock scenarios list (would come from database)
    scenarios = []
    
    return templates.TemplateResponse("fuel_forecast.html", {
        "request": request,
        "year": year,
        "month_names": MONTH_NAMES,
        "scenarios": scenarios,
        # Year 1 monthly inputs
        "use_factors_kc": use_factors_kc,
        "use_factors_cc": use_factors_cc,
        "heat_rates_kc": heat_rates_kc,
        "heat_rates_cc": heat_rates_cc,
        # Inventory & pricing
        "inventory_kc": inventory_kc,
        "inventory_cc": inventory_cc,
        "inventory_target_days": 50,
        "coal_price_contract": 65.00,
        "coal_price_spot": 72.00,
        "barge_price": 6.00,
        "fgd_aux_pct": 2.5,
        "gsu_loss_pct": 0.5,
        "reserve_mw": 5,
        # Multi-year defaults (Years 2-5)
        "uf_kc_y2": 85, "uf_kc_y3": 85, "uf_kc_y4": 85, "uf_kc_y5": 85,
        "uf_cc_y2": 85, "uf_cc_y3": 85, "uf_cc_y4": 85, "uf_cc_y5": 85,
        "hr_kc_y2": 9850, "hr_kc_y3": 9850, "hr_kc_y4": 9850, "hr_kc_y5": 9850,
        "hr_cc_y2": 9900, "hr_cc_y3": 9900, "hr_cc_y4": 9900, "hr_cc_y5": 9900,
        "esc_coal_y2": 2.5, "esc_coal_y3": 2.5, "esc_coal_y4": 2.5, "esc_coal_y5": 2.5,
        "esc_transport_y2": 3.0, "esc_transport_y3": 3.0, "esc_transport_y4": 3.0, "esc_transport_y5": 3.0,
        "esc_reagent_y2": 2.0, "esc_reagent_y3": 2.0, "esc_reagent_y4": 2.0, "esc_reagent_y5": 2.0,
        "active_page": "fuel_forecast",
        "active_tab": "forecast"
    })


@router.get("/energy-summary/{year}", response_class=HTMLResponse)
async def energy_summary_page(request: Request, year: int):
    """Render the system energy summary page."""
    
    # Get generation for both plants
    generation = get_system_generation(year)
    
    # Get fuel costs for both plants (annual summaries and monthly details)
    with get_session() as db:
        fuel_costs = calculate_system_fuel_costs(db, year)
        
        # Get monthly fuel cost details for each plant
        kyger_inputs = FuelModelInputs(plant_params=create_kyger_params())
        clifty_inputs = FuelModelInputs(plant_params=create_clifty_params())
        monthly_kyger = calculate_annual_fuel_costs(db, 1, year, kyger_inputs)
        monthly_clifty = calculate_annual_fuel_costs(db, 2, year, clifty_inputs)
    
    # Calculate combined metrics
    system_mwh = generation["system"]["net_delivered_mwh"]
    system_fuel_cost = fuel_costs["system"]["total_fuel_cost"]
    
    summary = {
        "total_mwh": system_mwh,
        "total_fuel_cost": system_fuel_cost,
        "avg_fuel_cost_per_mwh": system_fuel_cost / system_mwh if system_mwh > 0 else 0,
        "kyger_mwh": generation["kyger"]["net_delivered_mwh"],
        "clifty_mwh": generation["clifty"]["net_delivered_mwh"],
        "kyger_pct": generation["kyger"]["net_delivered_mwh"] / system_mwh * 100 if system_mwh > 0 else 0,
        "clifty_pct": generation["clifty"]["net_delivered_mwh"] / system_mwh * 100 if system_mwh > 0 else 0,
        "kyger_fuel_cost": fuel_costs["kyger"]["total_fuel_cost"],
        "clifty_fuel_cost": fuel_costs["clifty"]["total_fuel_cost"],
        "kyger_cost_per_mwh": fuel_costs["kyger"]["avg_fuel_cost_per_mwh"],
        "clifty_cost_per_mwh": fuel_costs["clifty"]["avg_fuel_cost_per_mwh"],
    }
    
    return templates.TemplateResponse("energy_summary.html", {
        "request": request,
        "year": year,
        "plant_code": "KC",  # Default for nav links
        "generation": generation,
        "fuel_costs": fuel_costs,
        "summary": summary,
        "monthly_clifty": monthly_clifty,
        "monthly_kyger": monthly_kyger,
        "last_updated": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "active_page": "energy_summary"
    })


# =============================================================================
# Coal Contract Pages
# =============================================================================

@router.get("/coal-contracts", response_class=HTMLResponse)
async def coal_contracts_list_page(request: Request):
    """Render the coal contracts list page."""
    from src.models.coal_contract import CoalContract
    from datetime import date, timedelta
    
    with get_session() as db:
        # Get all contracts
        contracts = db.query(CoalContract).order_by(
            CoalContract.is_active.desc(),
            CoalContract.supplier
        ).all()
        
        # Calculate summary stats
        active_contracts = [c for c in contracts if c.is_active]
        active_count = len(active_contracts)
        total_annual_tons = sum(float(c.annual_tons or 0) for c in active_contracts)
        
        # Calculate weighted average delivered cost
        if total_annual_tons > 0:
            weighted_cost = sum(
                float(c.annual_tons or 0) * c.delivered_cost_per_ton 
                for c in active_contracts
            )
            avg_delivered_cost = weighted_cost / total_annual_tons
        else:
            avg_delivered_cost = 0
        
        # Count contracts expiring soon (within 6 months)
        six_months = date.today() + timedelta(days=180)
        expiring_count = sum(
            1 for c in active_contracts 
            if c.end_date and c.end_date <= six_months
        )
        
        # Plant breakdown - Kyger (plant_id=1)
        kyger_contracts = [c for c in active_contracts if c.plant_id == 1]
        kyger_count = len(kyger_contracts)
        kyger_tons = sum(float(c.annual_tons or 0) for c in kyger_contracts)
        if kyger_tons > 0:
            kyger_avg_cost = sum(float(c.annual_tons or 0) * c.delivered_cost_per_ton for c in kyger_contracts) / kyger_tons
        else:
            kyger_avg_cost = 0
        
        # Plant breakdown - Clifty (plant_id=2)
        clifty_contracts = [c for c in active_contracts if c.plant_id == 2]
        clifty_count = len(clifty_contracts)
        clifty_tons = sum(float(c.annual_tons or 0) for c in clifty_contracts)
        if clifty_tons > 0:
            clifty_avg_cost = sum(float(c.annual_tons or 0) * c.delivered_cost_per_ton for c in clifty_contracts) / clifty_tons
        else:
            clifty_avg_cost = 0
    
    return templates.TemplateResponse("coal_contracts/list.html", {
        "request": request,
        "contracts": contracts,
        "active_count": active_count,
        "total_annual_tons": total_annual_tons,
        "avg_delivered_cost": avg_delivered_cost,
        "expiring_count": expiring_count,
        "kyger_count": kyger_count,
        "kyger_tons": kyger_tons,
        "kyger_avg_cost": kyger_avg_cost,
        "clifty_count": clifty_count,
        "clifty_tons": clifty_tons,
        "clifty_avg_cost": clifty_avg_cost,
        "active_page": "coal_contracts"
    })


@router.get("/coal-contracts/{contract_id}", response_class=HTMLResponse)
async def coal_contract_detail_page(request: Request, contract_id: int):
    """Render the coal contract detail page."""
    from src.models.coal_contract import CoalContract, CoalContractPricing
    
    with get_session() as db:
        # Get contract
        contract = db.query(CoalContract).filter(
            CoalContract.id == contract_id
        ).first()
        
        if not contract:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "Contract not found",
            })
        
        # Get monthly pricing
        pricing_records = db.query(CoalContractPricing).filter(
            CoalContractPricing.contract_id == contract_id
        ).all()
        
        # Build monthly pricing dict
        monthly_pricing = {}
        for p in pricing_records:
            month = int(p.effective_month[4:6]) if len(p.effective_month) == 6 else 1
            monthly_pricing[month] = {
                "coal_price": float(p.coal_price_per_ton or 0),
                "barge_price": float(p.barge_price_per_ton or 0),
            }
        
        # Placeholder delivery stats
        ytd_delivered = 0  # Would calculate from CoalDelivery table
        remaining = float(contract.annual_tons or 0) - ytd_delivered
    
    return templates.TemplateResponse("coal_contracts/detail.html", {
        "request": request,
        "contract": contract,
        "monthly_pricing": monthly_pricing,
        "ytd_delivered": ytd_delivered,
        "remaining": remaining,
        "active_page": "coal_contracts"
    })


# =============================================================================
# Scenario Comparison Pages
# =============================================================================

@router.get("/scenarios", response_class=HTMLResponse)
async def scenarios_list_page(request: Request):
    """Render the scenarios list page."""
    from src.models.scenario import Scenario
    from src.models.scenario_inputs import get_scenario_snapshot
    
    with get_session() as db:
        scenarios_raw = db.query(Scenario).filter(
            Scenario.is_active == True
        ).order_by(Scenario.created_at.desc()).all()
        
        scenarios = []
        for s in scenarios_raw:
            snapshot = get_scenario_snapshot(db, s.id)
            scenarios.append({
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "type": s.scenario_type.value if s.scenario_type else "internal_forecast",
                "status": s.status.value if s.status else "draft",
                "version": s.version,
                "created_at": s.created_at,
                "is_locked": s.is_locked,
                "has_snapshot": snapshot is not None,
                "year": snapshot.year if snapshot else None,
                "summary": snapshot.to_dict()["summary"] if snapshot else None,
            })
    
    return templates.TemplateResponse("scenarios/list.html", {
        "request": request,
        "scenarios": scenarios,
        "active_page": "scenarios"
    })


@router.get("/scenarios/compare", response_class=HTMLResponse)
async def scenarios_compare_page(request: Request, a: int = None, b: int = None):
    """Render the scenario comparison page."""
    from src.models.scenario import Scenario
    from src.models.scenario_inputs import get_scenario_snapshot, compare_snapshots
    
    with get_session() as db:
        # Get all scenarios for dropdown
        scenarios_raw = db.query(Scenario).filter(
            Scenario.is_active == True
        ).order_by(Scenario.created_at.desc()).all()
        
        scenarios = []
        for s in scenarios_raw:
            snapshot = get_scenario_snapshot(db, s.id)
            scenarios.append({
                "id": s.id,
                "name": s.name,
                "has_snapshot": snapshot is not None,
            })
        
        scenario_a = None
        scenario_b = None
        comparison = None
        
        if a and b:
            scenario_a_obj = db.query(Scenario).filter(Scenario.id == a).first()
            scenario_b_obj = db.query(Scenario).filter(Scenario.id == b).first()
            
            if scenario_a_obj and scenario_b_obj:
                snapshot_a = get_scenario_snapshot(db, a)
                snapshot_b = get_scenario_snapshot(db, b)
                
                if snapshot_a and snapshot_b:
                    comparison = compare_snapshots(snapshot_a, snapshot_b)
                    
                    scenario_a = {
                        "id": a,
                        "name": scenario_a_obj.name,
                        "summary": snapshot_a.to_dict()["summary"],
                    }
                    scenario_b = {
                        "id": b,
                        "name": scenario_b_obj.name,
                        "summary": snapshot_b.to_dict()["summary"],
                    }
    
    return templates.TemplateResponse("scenarios/compare.html", {
        "request": request,
        "scenarios": scenarios,
        "scenario_a": scenario_a,
        "scenario_b": scenario_b,
        "scenario_a_id": a,
        "scenario_b_id": b,
        "comparison": comparison,
        "active_page": "scenarios"
    })


@router.get("/scenarios/whatif", response_class=HTMLResponse)
async def scenarios_whatif_page(request: Request):
    """Render the what-if analysis page."""
    return templates.TemplateResponse("scenarios/whatif.html", {
        "request": request,
        "active_page": "scenarios"
    })


@router.get("/scenarios/outages", response_class=HTMLResponse)
async def scenarios_outages_page(request: Request):
    """Render the outage scenario modeling page."""
    return templates.TemplateResponse("scenarios/outage_scenarios.html", {
        "request": request,
        "active_page": "scenarios"
    }) 
