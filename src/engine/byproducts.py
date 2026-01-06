"""Byproducts calculation module.

Calculates byproduct production and revenue/costs:
- Fly ash (sales or disposal)
- Bottom ash (sales or disposal)
- Gypsum (from FGD, sales or disposal)
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List
import logging

from src.engine.coal_burn import CoalBurnResult
from src.engine.consumables import ConsumablesResult

logger = logging.getLogger(__name__)


@dataclass
class AshParams:
    """Parameters for ash handling."""
    fly_ash_pct: Decimal = Decimal("0.40")  # 40% of ash is fly ash
    bottom_ash_pct: Decimal = Decimal("0.60")  # 60% is bottom ash
    
    # Fly ash
    fly_ash_sold_pct: Decimal = Decimal("0")  # % of fly ash sold
    fly_ash_sale_price: Decimal = Decimal("-1")  # $/ton (negative = revenue)
    fly_ash_disposal_cost: Decimal = Decimal("4")  # $/ton
    
    # Bottom ash
    bottom_ash_sold_pct: Decimal = Decimal("0.55")  # % of bottom ash sold
    bottom_ash_sale_price: Decimal = Decimal("-9")  # $/ton (negative = revenue)
    bottom_ash_disposal_cost: Decimal = Decimal("4")  # $/ton


@dataclass
class GypsumParams:
    """Parameters for gypsum handling.
    
    Excel Q4 2025 values:
    - Gypsum sold %: 80%
    - Gypsum sale price: -$17.50/ton (negative = revenue)
    - Pad-to-pad cost: $4/ton (applies to ALL sold gypsum)
    - Disposal cost: $4/ton (for unsold gypsum)
    """
    # Gypsum production: ~1.7 tons gypsum per ton SO2 removed
    tons_gypsum_per_ton_so2: Decimal = Decimal("2.85")  # MW/ton basis
    
    # Sales
    gypsum_sold_pct: Decimal = Decimal("0.80")  # % of gypsum sold
    gypsum_sale_price: Decimal = Decimal("-17.50")  # $/ton (negative = revenue)
    gypsum_pad_to_pad_cost: Decimal = Decimal("4.00")  # $/ton for sold gypsum handling
    gypsum_disposal_cost: Decimal = Decimal("4.00")  # $/ton for unsold


@dataclass
class ByproductMiscParams:
    """Miscellaneous byproduct expenses.
    
    Excel shows ~$310,000/month fixed "Misc. Byproduct Expenses" that covers
    various handling, equipment, and operational costs not tied to specific
    byproduct volumes.
    """
    # Fixed monthly expenses (per plant)
    kyger_monthly_misc_expense: Decimal = Decimal("310000")  # $/month
    clifty_monthly_misc_expense: Decimal = Decimal("310000")  # $/month (estimate)


@dataclass
class ByproductsResult:
    """Result of byproducts calculation."""
    period_year: int
    period_month: int
    plant_name: str
    
    # Ash produced
    total_ash_tons: Decimal = Decimal("0")
    fly_ash_tons: Decimal = Decimal("0")
    bottom_ash_tons: Decimal = Decimal("0")
    
    # Fly ash disposition
    fly_ash_sold_tons: Decimal = Decimal("0")
    fly_ash_disposed_tons: Decimal = Decimal("0")
    fly_ash_revenue: Decimal = Decimal("0")  # Negative = revenue
    fly_ash_disposal_cost: Decimal = Decimal("0")
    fly_ash_net_cost: Decimal = Decimal("0")
    
    # Bottom ash disposition
    bottom_ash_sold_tons: Decimal = Decimal("0")
    bottom_ash_disposed_tons: Decimal = Decimal("0")
    bottom_ash_revenue: Decimal = Decimal("0")
    bottom_ash_disposal_cost: Decimal = Decimal("0")
    bottom_ash_net_cost: Decimal = Decimal("0")
    
    # Total ash net cost
    total_ash_net_cost: Decimal = Decimal("0")
    
    # Gypsum
    gypsum_produced_tons: Decimal = Decimal("0")
    gypsum_sold_tons: Decimal = Decimal("0")
    gypsum_disposed_tons: Decimal = Decimal("0")
    gypsum_revenue: Decimal = Decimal("0")
    gypsum_disposal_cost: Decimal = Decimal("0")
    gypsum_net_cost: Decimal = Decimal("0")
    
    # Miscellaneous byproduct expenses (fixed monthly)
    misc_byproduct_expense: Decimal = Decimal("0")
    
    # Aggregated totals (split by sales vs costs)
    total_sales_revenue: Decimal = Decimal("0")  # Negative = credit/income
    total_disposal_costs: Decimal = Decimal("0")  # Positive = expense
    
    # Grand total (positive = cost, negative = revenue)
    total_net_cost: Decimal = Decimal("0")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "period": f"{self.period_year}-{self.period_month:02d}",
            "plant": self.plant_name,
            "total_ash_tons": float(self.total_ash_tons),
            "fly_ash_tons": float(self.fly_ash_tons),
            "bottom_ash_tons": float(self.bottom_ash_tons),
            "fly_ash_revenue": float(self.fly_ash_revenue),
            "fly_ash_disposal_cost": float(self.fly_ash_disposal_cost),
            "fly_ash_net_cost": float(self.fly_ash_net_cost),
            "bottom_ash_revenue": float(self.bottom_ash_revenue),
            "bottom_ash_disposal_cost": float(self.bottom_ash_disposal_cost),
            "bottom_ash_net_cost": float(self.bottom_ash_net_cost),
            "total_ash_net_cost": float(self.total_ash_net_cost),
            "gypsum_produced_tons": float(self.gypsum_produced_tons),
            "gypsum_sold_tons": float(self.gypsum_sold_tons),
            "gypsum_revenue": float(self.gypsum_revenue),
            "gypsum_disposal_cost": float(self.gypsum_disposal_cost),
            "gypsum_net_cost": float(self.gypsum_net_cost),
            "misc_byproduct_expense": float(self.misc_byproduct_expense),
            "total_sales_revenue": float(self.total_sales_revenue),
            "total_disposal_costs": float(self.total_disposal_costs),
            "total_net_cost": float(self.total_net_cost),
        }


LBS_PER_TON = Decimal("2000")


def calculate_ash(
    coal_burn: CoalBurnResult,
    params: AshParams = None,
) -> Dict:
    """Calculate ash production and costs.
    
    Args:
        coal_burn: Coal burn result with ash tons produced
        params: Ash parameters
        
    Returns:
        Dictionary with ash breakdown
    """
    params = params or AshParams()
    
    total_ash = coal_burn.ash_tons_produced
    
    # Split into fly and bottom ash
    fly_ash = total_ash * params.fly_ash_pct
    bottom_ash = total_ash * params.bottom_ash_pct
    
    # Fly ash disposition
    fly_ash_sold = fly_ash * params.fly_ash_sold_pct
    fly_ash_disposed = fly_ash - fly_ash_sold
    fly_ash_revenue = fly_ash_sold * params.fly_ash_sale_price  # Negative = revenue
    fly_ash_disposal = fly_ash_disposed * params.fly_ash_disposal_cost
    fly_ash_net = fly_ash_revenue + fly_ash_disposal
    
    # Bottom ash disposition
    bottom_ash_sold = bottom_ash * params.bottom_ash_sold_pct
    bottom_ash_disposed = bottom_ash - bottom_ash_sold
    bottom_ash_revenue = bottom_ash_sold * params.bottom_ash_sale_price
    bottom_ash_disposal = bottom_ash_disposed * params.bottom_ash_disposal_cost
    bottom_ash_net = bottom_ash_revenue + bottom_ash_disposal
    
    return {
        "total_ash_tons": total_ash,
        "fly_ash_tons": fly_ash,
        "bottom_ash_tons": bottom_ash,
        "fly_ash_sold": fly_ash_sold,
        "fly_ash_disposed": fly_ash_disposed,
        "fly_ash_revenue": fly_ash_revenue,
        "fly_ash_disposal_cost": fly_ash_disposal,
        "fly_ash_net_cost": fly_ash_net,
        "bottom_ash_sold": bottom_ash_sold,
        "bottom_ash_disposed": bottom_ash_disposed,
        "bottom_ash_revenue": bottom_ash_revenue,
        "bottom_ash_disposal_cost": bottom_ash_disposal,
        "bottom_ash_net_cost": bottom_ash_net,
        "total_ash_net_cost": fly_ash_net + bottom_ash_net,
    }


def calculate_gypsum(
    consumables: ConsumablesResult,
    params: GypsumParams = None,
) -> Dict:
    """Calculate gypsum production and costs.
    
    Gypsum is produced from SO2 removal in the FGD.
    
    Args:
        consumables: Consumables result with SO2 removed
        params: Gypsum parameters
        
    Returns:
        Dictionary with gypsum breakdown
    """
    params = params or GypsumParams()
    
    # Convert SO2 removed (lbs) to tons
    so2_removed_tons = consumables.so2_removed_lbs / LBS_PER_TON
    
    # Gypsum produced
    gypsum_tons = so2_removed_tons * params.tons_gypsum_per_ton_so2
    
    # Disposition
    gypsum_sold = gypsum_tons * params.gypsum_sold_pct
    gypsum_disposed = gypsum_tons - gypsum_sold
    
    gypsum_revenue = gypsum_sold * params.gypsum_sale_price  # Negative = revenue
    gypsum_pad_to_pad = gypsum_sold * params.gypsum_pad_to_pad_cost  # Cost for sold gypsum handling
    gypsum_disposal = gypsum_disposed * params.gypsum_disposal_cost
    gypsum_net = gypsum_revenue + gypsum_pad_to_pad + gypsum_disposal
    
    return {
        "gypsum_produced_tons": gypsum_tons,
        "gypsum_sold_tons": gypsum_sold,
        "gypsum_disposed_tons": gypsum_disposed,
        "gypsum_revenue": gypsum_revenue,
        "gypsum_pad_to_pad_cost": gypsum_pad_to_pad,
        "gypsum_disposal_cost": gypsum_disposal,
        "gypsum_net_cost": gypsum_net,
    }


def calculate_all_byproducts(
    coal_burn: CoalBurnResult,
    consumables: ConsumablesResult,
    ash_params: AshParams = None,
    gypsum_params: GypsumParams = None,
    misc_expense: Decimal = None,
) -> ByproductsResult:
    """Calculate all byproducts for a period.
    
    Args:
        coal_burn: Coal burn result
        consumables: Consumables result
        ash_params: Optional ash parameters
        gypsum_params: Optional gypsum parameters
        misc_expense: Optional fixed monthly misc byproduct expense
        
    Returns:
        ByproductsResult with all calculations
    """
    result = ByproductsResult(
        period_year=coal_burn.period_year,
        period_month=coal_burn.period_month,
        plant_name=coal_burn.plant_name,
    )
    
    # Calculate ash
    ash = calculate_ash(coal_burn, ash_params)
    result.total_ash_tons = ash["total_ash_tons"]
    result.fly_ash_tons = ash["fly_ash_tons"]
    result.bottom_ash_tons = ash["bottom_ash_tons"]
    result.fly_ash_sold_tons = ash["fly_ash_sold"]
    result.fly_ash_disposed_tons = ash["fly_ash_disposed"]
    result.fly_ash_revenue = ash["fly_ash_revenue"]
    result.fly_ash_disposal_cost = ash["fly_ash_disposal_cost"]
    result.fly_ash_net_cost = ash["fly_ash_net_cost"]
    result.bottom_ash_sold_tons = ash["bottom_ash_sold"]
    result.bottom_ash_disposed_tons = ash["bottom_ash_disposed"]
    result.bottom_ash_revenue = ash["bottom_ash_revenue"]
    result.bottom_ash_disposal_cost = ash["bottom_ash_disposal_cost"]
    result.bottom_ash_net_cost = ash["bottom_ash_net_cost"]
    result.total_ash_net_cost = ash["total_ash_net_cost"]
    
    # Calculate gypsum
    gypsum = calculate_gypsum(consumables, gypsum_params)
    result.gypsum_produced_tons = gypsum["gypsum_produced_tons"]
    result.gypsum_sold_tons = gypsum["gypsum_sold_tons"]
    result.gypsum_disposed_tons = gypsum["gypsum_disposed_tons"]
    result.gypsum_revenue = gypsum["gypsum_revenue"]
    result.gypsum_disposal_cost = gypsum["gypsum_disposal_cost"]
    result.gypsum_net_cost = gypsum["gypsum_net_cost"]
    
    # Apply misc byproduct expense if provided
    result.misc_byproduct_expense = misc_expense or Decimal("0")
    
    # Calculate aggregated totals (split by sales vs costs)
    result.total_sales_revenue = (
        result.fly_ash_revenue +
        result.bottom_ash_revenue +
        result.gypsum_revenue
    )
    
    result.total_disposal_costs = (
        result.fly_ash_disposal_cost +
        result.bottom_ash_disposal_cost +
        result.gypsum_disposal_cost +
        result.misc_byproduct_expense
    )
    
    # Total net cost (positive = cost, negative = revenue)
    result.total_net_cost = (
        result.total_sales_revenue +  # Negative values = credits
        result.total_disposal_costs   # Positive values = costs
    )
    
    return result


def summarize_annual_byproducts(results: List[ByproductsResult]) -> Dict:
    """Summarize annual byproducts.
    
    Args:
        results: List of monthly ByproductsResult
        
    Returns:
        Dictionary with annual totals
    """
    if not results:
        return {}
    
    return {
        "plant": results[0].plant_name,
        "year": results[0].period_year,
        "total_ash_tons": float(sum(r.total_ash_tons for r in results)),
        "total_ash_net_cost": float(sum(r.total_ash_net_cost for r in results)),
        "fly_ash_revenue": float(sum(r.fly_ash_revenue for r in results)),
        "bottom_ash_revenue": float(sum(r.bottom_ash_revenue for r in results)),
        "total_gypsum_tons": float(sum(r.gypsum_produced_tons for r in results)),
        "gypsum_revenue": float(sum(r.gypsum_revenue for r in results)),
        "gypsum_disposal_cost": float(sum(r.gypsum_disposal_cost for r in results)),
        "gypsum_net_cost": float(sum(r.gypsum_net_cost for r in results)),
        "misc_byproduct_expense": float(sum(r.misc_byproduct_expense for r in results)),
        "total_sales_revenue": float(sum(r.total_sales_revenue for r in results)),
        "total_disposal_costs": float(sum(r.total_disposal_costs for r in results)),
        "total_net_cost": float(sum(r.total_net_cost for r in results)),
    }

