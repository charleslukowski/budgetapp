"""Variance reporting - Actual vs Budget analysis.

Generates variance reports comparing actual costs to budget,
supporting the RPTData format with types:
- Actual
- Budget
- Forecast
- FcastActuals (YTD Actual + Remaining Forecast)
- Variance
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Dict, Optional
from enum import Enum
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models.actuals import EnergyActual, ExpenseActual, BudgetLine

logger = logging.getLogger(__name__)


class VarianceType(str, Enum):
    """Types of variance data."""
    ACTUAL = "Actual"
    BUDGET = "Budget"
    FORECAST = "Forecast"
    FCAST_ACTUALS = "FcastActuals"
    VARIANCE = "Variance"


@dataclass
class MonthlyValues:
    """Monthly values for a cost category."""
    jan: Decimal = Decimal("0")
    feb: Decimal = Decimal("0")
    mar: Decimal = Decimal("0")
    apr: Decimal = Decimal("0")
    may: Decimal = Decimal("0")
    jun: Decimal = Decimal("0")
    jul: Decimal = Decimal("0")
    aug: Decimal = Decimal("0")
    sep: Decimal = Decimal("0")
    oct: Decimal = Decimal("0")
    nov: Decimal = Decimal("0")
    dec: Decimal = Decimal("0")
    
    def get_month(self, month: int) -> Decimal:
        """Get value for a specific month (1-12)."""
        months = [None, self.jan, self.feb, self.mar, self.apr, self.may, self.jun,
                  self.jul, self.aug, self.sep, self.oct, self.nov, self.dec]
        return months[month] if 1 <= month <= 12 else Decimal("0")
    
    def set_month(self, month: int, value: Decimal):
        """Set value for a specific month (1-12)."""
        attr_names = [None, 'jan', 'feb', 'mar', 'apr', 'may', 'jun',
                      'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        if 1 <= month <= 12:
            setattr(self, attr_names[month], value)
    
    @property
    def total(self) -> Decimal:
        """Sum of all months."""
        return (self.jan + self.feb + self.mar + self.apr + self.may + self.jun +
                self.jul + self.aug + self.sep + self.oct + self.nov + self.dec)
    
    def ytd(self, through_month: int) -> Decimal:
        """Year-to-date total through specified month."""
        total = Decimal("0")
        for m in range(1, through_month + 1):
            total += self.get_month(m)
        return total
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "jan": float(self.jan), "feb": float(self.feb), "mar": float(self.mar),
            "apr": float(self.apr), "may": float(self.may), "jun": float(self.jun),
            "jul": float(self.jul), "aug": float(self.aug), "sep": float(self.sep),
            "oct": float(self.oct), "nov": float(self.nov), "dec": float(self.dec),
            "total": float(self.total),
        }


@dataclass
class VarianceLine:
    """A single line in a variance report."""
    category: str
    group: str
    plant: str
    ferc_account: Optional[str] = None
    labor_type: Optional[str] = None
    
    actual: MonthlyValues = field(default_factory=MonthlyValues)
    budget: MonthlyValues = field(default_factory=MonthlyValues)
    forecast: MonthlyValues = field(default_factory=MonthlyValues)
    
    @property
    def variance(self) -> MonthlyValues:
        """Calculate variance (Budget - Actual). Positive = favorable."""
        v = MonthlyValues()
        for month in range(1, 13):
            v.set_month(month, self.budget.get_month(month) - self.actual.get_month(month))
        return v
    
    def fcast_actuals(self, current_month: int) -> MonthlyValues:
        """YTD Actuals + Remaining Forecast."""
        fa = MonthlyValues()
        for month in range(1, 13):
            if month <= current_month:
                fa.set_month(month, self.actual.get_month(month))
            else:
                fa.set_month(month, self.forecast.get_month(month))
        return fa


def get_actuals_by_period(
    db: Session,
    year: int,
    plant_id: int = None,
    is_energy: bool = True,
) -> Dict[str, Dict[int, Decimal]]:
    """Get actual costs aggregated by category and month.
    
    Args:
        db: Database session
        year: Year to query
        plant_id: Optional plant filter
        is_energy: True for energy actuals, False for expense actuals
        
    Returns:
        Dictionary: {category: {month: amount}}
    """
    Model = EnergyActual if is_energy else ExpenseActual
    group_field = Model.cost_group if is_energy else Model.department
    
    # Build query for each month
    results = {}
    
    for month in range(1, 13):
        period_yyyymm = f"{year}{month:02d}"
        
        query = db.query(
            group_field.label("category"),
            func.sum(Model.amount).label("total"),
        ).filter(
            Model.period_yyyymm == period_yyyymm
        )
        
        if plant_id:
            query = query.filter(Model.plant_id == plant_id)
        
        query = query.group_by(group_field)
        
        for row in query.all():
            category = row.category or "Unknown"
            if category not in results:
                results[category] = {}
            results[category][month] = row.total or Decimal("0")
    
    return results


def get_budget_by_period(
    db: Session,
    year: int,
    plant_id: int = None,
) -> Dict[str, MonthlyValues]:
    """Get budget amounts by department/category.
    
    Args:
        db: Database session
        year: Budget year
        plant_id: Optional plant filter
        
    Returns:
        Dictionary: {department: MonthlyValues}
    """
    query = db.query(BudgetLine).filter(BudgetLine.budget_year == year)
    
    if plant_id:
        query = query.filter(BudgetLine.plant_id == plant_id)
    
    results = {}
    
    for line in query.all():
        dept = line.department or "Unknown"
        if dept not in results:
            results[dept] = MonthlyValues()
        
        monthly = line.get_monthly_amounts()
        for month, amount in monthly.items():
            if amount:
                current = results[dept].get_month(month)
                results[dept].set_month(month, current + amount)
    
    return results


def generate_variance_report(
    db: Session,
    year: int,
    current_month: int,
    plant_id: int = None,
    is_energy: bool = False,
) -> List[VarianceLine]:
    """Generate a complete variance report.
    
    Args:
        db: Database session
        year: Year for report
        current_month: Current month (1-12) for YTD calculations
        plant_id: Optional plant filter
        is_energy: True for energy/fuel, False for O&M
        
    Returns:
        List of VarianceLine objects
    """
    # Get actuals
    actuals = get_actuals_by_period(db, year, plant_id, is_energy)
    
    # Get budget
    budgets = get_budget_by_period(db, year, plant_id)
    
    # Combine into variance lines
    all_categories = set(actuals.keys()) | set(budgets.keys())
    
    lines = []
    for category in sorted(all_categories):
        line = VarianceLine(
            category=category,
            group=category,
            plant="Kyger Creek" if plant_id == 1 else "Clifty Creek" if plant_id == 2 else "All",
        )
        
        # Populate actuals
        if category in actuals:
            for month, amount in actuals[category].items():
                line.actual.set_month(month, amount)
        
        # Populate budget
        if category in budgets:
            line.budget = budgets[category]
            # Use budget as initial forecast
            line.forecast = budgets[category]
        
        lines.append(line)
    
    return lines


def variance_report_to_dict(
    lines: List[VarianceLine],
    current_month: int,
) -> List[Dict]:
    """Convert variance report to dictionary format.
    
    Args:
        lines: List of VarianceLine objects
        current_month: Current month for YTD
        
    Returns:
        List of dictionaries with all variance data
    """
    results = []
    
    for line in lines:
        base = {
            "category": line.category,
            "group": line.group,
            "plant": line.plant,
        }
        
        # Actual row
        actual_row = {**base, "type": VarianceType.ACTUAL.value}
        actual_row.update(line.actual.to_dict())
        actual_row["ytd"] = float(line.actual.ytd(current_month))
        results.append(actual_row)
        
        # Budget row
        budget_row = {**base, "type": VarianceType.BUDGET.value}
        budget_row.update(line.budget.to_dict())
        budget_row["ytd"] = float(line.budget.ytd(current_month))
        results.append(budget_row)
        
        # Forecast row
        forecast_row = {**base, "type": VarianceType.FORECAST.value}
        forecast_row.update(line.forecast.to_dict())
        forecast_row["ytd"] = float(line.forecast.ytd(current_month))
        results.append(forecast_row)
        
        # FcastActuals row
        fcast_actuals = line.fcast_actuals(current_month)
        fa_row = {**base, "type": VarianceType.FCAST_ACTUALS.value}
        fa_row.update(fcast_actuals.to_dict())
        fa_row["ytd"] = float(fcast_actuals.ytd(current_month))
        results.append(fa_row)
        
        # Variance row
        variance = line.variance
        var_row = {**base, "type": VarianceType.VARIANCE.value}
        var_row.update(variance.to_dict())
        var_row["ytd"] = float(variance.ytd(current_month))
        results.append(var_row)
    
    return results


def get_ytd_variance_summary(
    db: Session,
    year: int,
    current_month: int,
    plant_id: int = None,
) -> Dict:
    """Get a high-level YTD variance summary.
    
    Args:
        db: Database session
        year: Year for report
        current_month: Current month (1-12)
        plant_id: Optional plant filter
        
    Returns:
        Dictionary with summary metrics
    """
    # Get expense actuals
    expense_lines = generate_variance_report(
        db, year, current_month, plant_id, is_energy=False
    )
    
    # Get energy actuals
    energy_lines = generate_variance_report(
        db, year, current_month, plant_id, is_energy=True
    )
    
    # Calculate totals
    expense_actual_ytd = sum(l.actual.ytd(current_month) for l in expense_lines)
    expense_budget_ytd = sum(l.budget.ytd(current_month) for l in expense_lines)
    
    energy_actual_ytd = sum(l.actual.ytd(current_month) for l in energy_lines)
    energy_budget_ytd = sum(l.budget.ytd(current_month) for l in energy_lines)
    
    return {
        "year": year,
        "through_month": current_month,
        "plant_id": plant_id,
        "expense": {
            "actual_ytd": float(expense_actual_ytd),
            "budget_ytd": float(expense_budget_ytd),
            "variance_ytd": float(expense_budget_ytd - expense_actual_ytd),
            "variance_pct": float((expense_budget_ytd - expense_actual_ytd) / expense_budget_ytd * 100) if expense_budget_ytd else 0,
        },
        "energy": {
            "actual_ytd": float(energy_actual_ytd),
            "budget_ytd": float(energy_budget_ytd),
            "variance_ytd": float(energy_budget_ytd - energy_actual_ytd),
            "variance_pct": float((energy_budget_ytd - energy_actual_ytd) / energy_budget_ytd * 100) if energy_budget_ytd else 0,
        },
        "total": {
            "actual_ytd": float(expense_actual_ytd + energy_actual_ytd),
            "budget_ytd": float(expense_budget_ytd + energy_budget_ytd),
            "variance_ytd": float((expense_budget_ytd + energy_budget_ytd) - (expense_actual_ytd + energy_actual_ytd)),
        },
    }

