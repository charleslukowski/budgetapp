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


@router.get("/scenarios", response_class=HTMLResponse)
async def scenarios_list_page(request: Request):
    """Render the scenarios list page."""
    from src.models.scenario import Scenario

    with get_session() as db:
        scenarios_raw = db.query(Scenario).filter(
            Scenario.is_active == True
        ).order_by(Scenario.created_at.desc()).all()

        scenarios = []
        for s in scenarios_raw:
            scenarios.append({
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "type": s.scenario_type.value if s.scenario_type else "internal_forecast",
                "status": s.status.value if s.status else "draft",
                "version": s.version,
                "created_at": s.created_at,
                "is_locked": s.is_locked,
            })

    return templates.TemplateResponse("scenarios/list.html", {
        "request": request,
        "scenarios": scenarios,
        "active_page": "scenarios"
    })
