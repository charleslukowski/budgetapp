"""Coal supply and inventory calculation module.

Calculates:
- Coal supply from contracts + uncommitted
- Inventory management (target days supply)
- Weighted average coal cost
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Dict, Optional
from datetime import date
import logging

from sqlalchemy.orm import Session

from src.models.coal_contract import (
    CoalContract, CoalDelivery, UncommittedCoal,
    CoalContractPricing, UncommittedCoalPrice,
)
from src.models.actuals import CoalInventory, CoalStartingInventory

logger = logging.getLogger(__name__)


@dataclass
class CoalSupplySource:
    """A source of coal supply (contract or spot)."""
    source_id: str
    source_type: str  # "contract" or "uncommitted"
    supplier: str
    tons: Decimal
    btu_per_lb: Decimal
    coal_price: Decimal
    barge_price: Decimal
    so2_lb_per_mmbtu: Decimal = Decimal("0")
    ash_pct: Decimal = Decimal("0")
    
    @property
    def delivered_cost(self) -> Decimal:
        """Total delivered cost per ton."""
        return self.coal_price + self.barge_price
    
    @property
    def total_cost(self) -> Decimal:
        """Total cost for this supply."""
        return self.tons * self.delivered_cost
    
    @property
    def mmbtu_per_ton(self) -> Decimal:
        """MMBtu per ton."""
        return self.btu_per_lb * Decimal("2000") / Decimal("1000000")
    
    @property
    def cost_per_mmbtu(self) -> Decimal:
        """Cost per MMBtu."""
        if self.mmbtu_per_ton > 0:
            return self.delivered_cost / self.mmbtu_per_ton
        return Decimal("0")


@dataclass
class CoalSupplyResult:
    """Result of coal supply calculation."""
    period_year: int
    period_month: int
    plant_name: str
    
    # Supply sources
    sources: List[CoalSupplySource] = field(default_factory=list)
    
    # Totals
    total_tons: Decimal = Decimal("0")
    total_cost: Decimal = Decimal("0")
    
    # Weighted averages
    weighted_avg_btu: Decimal = Decimal("0")
    weighted_avg_cost_per_ton: Decimal = Decimal("0")
    weighted_avg_cost_per_mmbtu: Decimal = Decimal("0")
    
    # Inventory
    beginning_inventory_tons: Decimal = Decimal("0")
    ending_inventory_tons: Decimal = Decimal("0")
    consumption_tons: Decimal = Decimal("0")
    days_supply: Decimal = Decimal("0")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "period": f"{self.period_year}-{self.period_month:02d}",
            "plant": self.plant_name,
            "source_count": len(self.sources),
            "total_tons": float(self.total_tons),
            "total_cost": float(self.total_cost),
            "weighted_avg_btu": float(self.weighted_avg_btu),
            "weighted_avg_cost_per_ton": float(self.weighted_avg_cost_per_ton),
            "weighted_avg_cost_per_mmbtu": float(self.weighted_avg_cost_per_mmbtu),
            "beginning_inventory_tons": float(self.beginning_inventory_tons),
            "ending_inventory_tons": float(self.ending_inventory_tons),
            "consumption_tons": float(self.consumption_tons),
            "days_supply": float(self.days_supply),
        }


def calculate_weighted_averages(sources: List[CoalSupplySource]) -> Dict:
    """Calculate weighted average coal properties.
    
    Args:
        sources: List of coal supply sources
        
    Returns:
        Dictionary with weighted averages
    """
    if not sources:
        return {
            "btu": Decimal("0"),
            "cost_per_ton": Decimal("0"),
            "cost_per_mmbtu": Decimal("0"),
            "so2": Decimal("0"),
            "ash": Decimal("0"),
        }
    
    total_tons = sum(s.tons for s in sources)
    if total_tons == 0:
        return {
            "btu": Decimal("0"),
            "cost_per_ton": Decimal("0"),
            "cost_per_mmbtu": Decimal("0"),
            "so2": Decimal("0"),
            "ash": Decimal("0"),
        }
    
    total_cost = sum(s.total_cost for s in sources)
    
    # Weighted average BTU
    weighted_btu = sum(s.btu_per_lb * s.tons for s in sources) / total_tons
    
    # Weighted average cost per ton
    weighted_cost = total_cost / total_tons
    
    # Weighted average SO2
    weighted_so2 = sum(s.so2_lb_per_mmbtu * s.tons for s in sources) / total_tons
    
    # Weighted average ash
    weighted_ash = sum(s.ash_pct * s.tons for s in sources) / total_tons
    
    # Cost per MMBtu
    mmbtu_per_ton = weighted_btu * Decimal("2000") / Decimal("1000000")
    cost_per_mmbtu = weighted_cost / mmbtu_per_ton if mmbtu_per_ton > 0 else Decimal("0")
    
    return {
        "btu": weighted_btu,
        "cost_per_ton": weighted_cost,
        "cost_per_mmbtu": cost_per_mmbtu,
        "so2": weighted_so2,
        "ash": weighted_ash,
    }


def get_contract_deliveries(
    db: Session,
    plant_id: int,
    period_yyyymm: str,
) -> List[CoalSupplySource]:
    """Get contracted coal deliveries for a period.
    
    Args:
        db: Database session
        plant_id: Plant ID
        period_yyyymm: Period in YYYYMM format
        
    Returns:
        List of CoalSupplySource
    """
    deliveries = db.query(CoalDelivery).join(CoalContract).filter(
        CoalContract.plant_id == plant_id,
        CoalDelivery.period_yyyymm == period_yyyymm,
    ).all()
    
    sources = []
    for d in deliveries:
        c = d.contract
        
        # Check for period-specific pricing from CoalContractPricing
        period_pricing = db.query(CoalContractPricing).filter(
            CoalContractPricing.contract_id == c.id,
            CoalContractPricing.effective_month == period_yyyymm,
        ).first()
        
        # Use period pricing if available, otherwise contract defaults
        if period_pricing:
            coal_price = period_pricing.coal_price_per_ton
            barge_price = period_pricing.barge_price_per_ton
            btu = period_pricing.btu_per_lb or c.btu_per_lb
            so2 = period_pricing.so2_lb_per_mmbtu or c.so2_lb_per_mmbtu
        else:
            coal_price = c.coal_price_per_ton
            barge_price = c.barge_price_per_ton
            btu = c.btu_per_lb
            so2 = c.so2_lb_per_mmbtu
        
        # Actuals override everything if available
        sources.append(CoalSupplySource(
            source_id=c.contract_id,
            source_type="contract",
            supplier=c.supplier,
            tons=d.actual_tons or d.scheduled_tons,
            btu_per_lb=d.actual_btu_per_lb or btu,
            coal_price=d.actual_coal_price or coal_price,
            barge_price=d.actual_barge_price or barge_price,
            so2_lb_per_mmbtu=d.actual_so2 or so2 or Decimal("0"),
            ash_pct=d.actual_ash or c.ash_pct or Decimal("0"),
        ))
    
    return sources


def get_contract_pricing_for_period(
    db: Session,
    contract_id: int,
    period_yyyymm: str,
) -> Dict:
    """Get pricing for a contract for a specific period.
    
    Checks for period-specific pricing first, falls back to contract defaults.
    
    Args:
        db: Database session
        contract_id: Contract ID
        period_yyyymm: Period in YYYYMM format
        
    Returns:
        Dict with coal_price, barge_price, btu_per_lb, so2
    """
    # Get contract
    contract = db.query(CoalContract).filter(CoalContract.id == contract_id).first()
    if not contract:
        return None
    
    # Check for period-specific pricing
    period_pricing = db.query(CoalContractPricing).filter(
        CoalContractPricing.contract_id == contract_id,
        CoalContractPricing.effective_month == period_yyyymm,
    ).first()
    
    if period_pricing:
        return {
            "coal_price": period_pricing.coal_price_per_ton,
            "barge_price": period_pricing.barge_price_per_ton or Decimal("0"),
            "btu_per_lb": period_pricing.btu_per_lb or contract.btu_per_lb,
            "so2_lb_per_mmbtu": period_pricing.so2_lb_per_mmbtu or contract.so2_lb_per_mmbtu or Decimal("0"),
            "source": "period_pricing",
        }
    else:
        return {
            "coal_price": contract.coal_price_per_ton,
            "barge_price": contract.barge_price_per_ton or Decimal("0"),
            "btu_per_lb": contract.btu_per_lb,
            "so2_lb_per_mmbtu": contract.so2_lb_per_mmbtu or Decimal("0"),
            "source": "contract_default",
        }


def get_uncommitted_coal(
    db: Session,
    plant_id: int,
    period_yyyymm: str,
) -> List[CoalSupplySource]:
    """Get uncommitted (spot) coal for a period.
    
    Args:
        db: Database session
        plant_id: Plant ID
        period_yyyymm: Period
        
    Returns:
        List of CoalSupplySource
    """
    uncommitted = db.query(UncommittedCoal).filter(
        UncommittedCoal.plant_id == plant_id,
        UncommittedCoal.period_yyyymm == period_yyyymm,
    ).all()
    
    sources = []
    for u in uncommitted:
        sources.append(CoalSupplySource(
            source_id=f"UNCOMMITTED-{u.id}",
            source_type="uncommitted",
            supplier=f"Spot Market ({u.coal_region})",
            tons=u.tons,
            btu_per_lb=u.btu_per_lb,
            coal_price=u.market_price_per_ton,
            barge_price=u.barge_price_per_ton,
            so2_lb_per_mmbtu=u.so2_lb_per_mmbtu or Decimal("0"),
        ))
    
    return sources


def get_uncommitted_pricing_for_period(
    db: Session,
    plant_id: int,
    year: int,
    month: int,
) -> Optional[Dict]:
    """Get uncommitted coal pricing for a period.
    
    Used for forecasting when burn exceeds contracted supply.
    
    Args:
        db: Database session
        plant_id: Plant ID
        year: Year
        month: Month
        
    Returns:
        Dict with pricing info or None if not set
    """
    pricing = db.query(UncommittedCoalPrice).filter(
        UncommittedCoalPrice.plant_id == plant_id,
        UncommittedCoalPrice.year == year,
        UncommittedCoalPrice.month == month,
    ).first()
    
    if pricing:
        return {
            "price_per_ton": pricing.price_per_ton,
            "barge_per_ton": pricing.barge_per_ton or Decimal("0"),
            "delivered_cost": pricing.delivered_cost_per_ton,
            "btu_per_lb": pricing.btu_per_lb,
            "source_name": pricing.source_name,
        }
    
    return None


def calculate_forecast_coal_supply(
    db: Session,
    plant_id: int,
    year: int,
    month: int,
    consumption_tons: Decimal,
) -> CoalSupplyResult:
    """Calculate forecasted coal supply for a period.
    
    Uses contract schedules and uncommitted pricing to project supply costs.
    This is for forecasting, not actuals.
    
    Args:
        db: Database session
        plant_id: Plant ID
        year: Year
        month: Month
        consumption_tons: Expected coal consumption
        
    Returns:
        CoalSupplyResult with forecasted supply
    """
    from datetime import date
    
    period_yyyymm = f"{year}{month:02d}"
    plant_name = "Kyger Creek" if plant_id == 1 else "Clifty Creek"
    period_date = date(year, month, 1)
    
    result = CoalSupplyResult(
        period_year=year,
        period_month=month,
        plant_name=plant_name,
        consumption_tons=consumption_tons,
    )
    
    sources = []
    contracted_tons = Decimal("0")
    
    # Get active contracts for this period
    contracts = db.query(CoalContract).filter(
        CoalContract.plant_id == plant_id,
        CoalContract.is_active == True,
        CoalContract.start_date <= period_date,
        CoalContract.end_date >= period_date,
    ).all()
    
    for c in contracts:
        # Get period-specific pricing
        pricing = get_contract_pricing_for_period(db, c.id, period_yyyymm)
        
        # Allocate monthly tons (simple: annual / 12)
        monthly_tons = c.annual_tons / Decimal("12")
        
        sources.append(CoalSupplySource(
            source_id=c.contract_id,
            source_type="contract",
            supplier=c.supplier,
            tons=monthly_tons,
            btu_per_lb=pricing["btu_per_lb"],
            coal_price=pricing["coal_price"],
            barge_price=pricing["barge_price"],
            so2_lb_per_mmbtu=pricing["so2_lb_per_mmbtu"],
            ash_pct=c.ash_pct or Decimal("0"),
        ))
        
        contracted_tons += monthly_tons
    
    # If consumption exceeds contracted supply, add uncommitted
    if consumption_tons > contracted_tons:
        uncommitted_tons = consumption_tons - contracted_tons
        
        # Get uncommitted pricing
        uncommitted_pricing = get_uncommitted_pricing_for_period(db, plant_id, year, month)
        
        if uncommitted_pricing:
            sources.append(CoalSupplySource(
                source_id=f"UNCOMMITTED-{year}{month:02d}",
                source_type="uncommitted",
                supplier=f"Spot Market ({uncommitted_pricing['source_name']})",
                tons=uncommitted_tons,
                btu_per_lb=uncommitted_pricing["btu_per_lb"],
                coal_price=uncommitted_pricing["price_per_ton"],
                barge_price=uncommitted_pricing["barge_per_ton"],
            ))
        else:
            # Use default pricing if no uncommitted pricing set
            sources.append(CoalSupplySource(
                source_id=f"UNCOMMITTED-{year}{month:02d}",
                source_type="uncommitted",
                supplier="Spot Market (Est.)",
                tons=uncommitted_tons,
                btu_per_lb=Decimal("12500"),
                coal_price=Decimal("65"),  # Default spot price
                barge_price=Decimal("8"),
            ))
    
    result.sources = sources
    
    # Calculate totals
    result.total_tons = sum(s.tons for s in result.sources)
    result.total_cost = sum(s.total_cost for s in result.sources)
    
    # Calculate weighted averages
    averages = calculate_weighted_averages(result.sources)
    result.weighted_avg_btu = averages["btu"]
    result.weighted_avg_cost_per_ton = averages["cost_per_ton"]
    result.weighted_avg_cost_per_mmbtu = averages["cost_per_mmbtu"]
    
    return result


def calculate_coal_supply(
    db: Session,
    plant_id: int,
    year: int,
    month: int,
    consumption_tons: Decimal,
    target_days_supply: int = 50,
) -> CoalSupplyResult:
    """Calculate coal supply for a period.
    
    Args:
        db: Database session
        plant_id: Plant ID
        year: Year
        month: Month
        consumption_tons: Expected coal consumption in tons
        target_days_supply: Target inventory days
        
    Returns:
        CoalSupplyResult
    """
    period_yyyymm = f"{year}{month:02d}"
    plant_name = "Kyger Creek" if plant_id == 1 else "Clifty Creek"
    
    result = CoalSupplyResult(
        period_year=year,
        period_month=month,
        plant_name=plant_name,
        consumption_tons=consumption_tons,
    )
    
    # Get contract deliveries
    contract_sources = get_contract_deliveries(db, plant_id, period_yyyymm)
    
    # Get uncommitted coal
    uncommitted_sources = get_uncommitted_coal(db, plant_id, period_yyyymm)
    
    # Combine sources
    result.sources = contract_sources + uncommitted_sources
    
    # Calculate totals
    result.total_tons = sum(s.tons for s in result.sources)
    result.total_cost = sum(s.total_cost for s in result.sources)
    
    # Calculate weighted averages
    averages = calculate_weighted_averages(result.sources)
    result.weighted_avg_btu = averages["btu"]
    result.weighted_avg_cost_per_ton = averages["cost_per_ton"]
    result.weighted_avg_cost_per_mmbtu = averages["cost_per_mmbtu"]
    
    # Get inventory from Aligne data
    inventory = db.query(CoalInventory).filter(
        CoalInventory.plant_id == plant_id,
        CoalInventory.period_yyyymm == period_yyyymm,
    ).first()
    
    if inventory:
        result.ending_inventory_tons = inventory.ending_inventory_tons or Decimal("0")
    
    # Calculate beginning inventory
    if month == 1:
        # For January, first check for explicit starting inventory from Excel import
        starting_inv = db.query(CoalStartingInventory).filter(
            CoalStartingInventory.plant_id == plant_id,
            CoalStartingInventory.year == year,
        ).first()
        
        if starting_inv:
            result.beginning_inventory_tons = starting_inv.beginning_inventory_tons or Decimal("0")
        else:
            # Fall back to previous December's ending inventory
            prev_period = f"{year - 1}12"
            prev_inventory = db.query(CoalInventory).filter(
                CoalInventory.plant_id == plant_id,
                CoalInventory.period_yyyymm == prev_period,
            ).first()
            if prev_inventory:
                result.beginning_inventory_tons = prev_inventory.ending_inventory_tons or Decimal("0")
    else:
        # For other months, use previous month's ending inventory
        prev_month = month - 1
        prev_period = f"{year}{prev_month:02d}"
        
        prev_inventory = db.query(CoalInventory).filter(
            CoalInventory.plant_id == plant_id,
            CoalInventory.period_yyyymm == prev_period,
        ).first()
        
        if prev_inventory:
            result.beginning_inventory_tons = prev_inventory.ending_inventory_tons or Decimal("0")
    
    # Calculate days supply
    if consumption_tons > 0:
        # Days in month
        from calendar import monthrange
        days_in_month = monthrange(year, month)[1]
        daily_consumption = consumption_tons / days_in_month
        if daily_consumption > 0:
            result.days_supply = result.ending_inventory_tons / daily_consumption
    
    return result


def calculate_uncommitted_needed(
    target_days_supply: int,
    daily_consumption: Decimal,
    current_inventory: Decimal,
    contracted_deliveries: Decimal,
) -> Decimal:
    """Calculate uncommitted coal needed to meet inventory target.
    
    Args:
        target_days_supply: Target inventory days
        daily_consumption: Daily coal consumption
        current_inventory: Current inventory
        contracted_deliveries: Contracted deliveries for period
        
    Returns:
        Uncommitted tons needed
    """
    target_inventory = target_days_supply * daily_consumption
    expected_inventory = current_inventory + contracted_deliveries - (daily_consumption * Decimal("30"))  # Approximate month
    
    gap = target_inventory - expected_inventory
    return max(Decimal("0"), gap)


def get_weighted_coal_pricing(
    db: Session,
    plant_id: int,
    year: int,
    month: int,
) -> Dict:
    """Get weighted-average coal pricing from contracts and uncommitted sources.
    
    This is the main entry point for the fuel model to get coal pricing.
    It reads from coal_contract_pricing and uncommitted_coal_prices tables.
    
    Args:
        db: Database session
        plant_id: Plant ID (1=Kyger, 2=Clifty)
        year: Year
        month: Month
        
    Returns:
        Dict with:
        - coal_price_per_ton: Weighted average FOB mine price
        - barge_price_per_ton: Weighted average transportation
        - delivered_cost_per_ton: Total delivered cost
        - btu_per_lb: Weighted average BTU content
        - cost_per_mmbtu: Cost per MMBtu
        - source_breakdown: List of sources with percentages
    """
    from datetime import date
    
    period_yyyymm = f"{year}{month:02d}"
    period_date = date(year, month, 1)
    
    sources = []
    
    # Get active contracts for this period
    contracts = db.query(CoalContract).filter(
        CoalContract.plant_id == plant_id,
        CoalContract.is_active == True,
        CoalContract.start_date <= period_date,
        CoalContract.end_date >= period_date,
    ).all()
    
    for c in contracts:
        # Get period-specific pricing from CoalContractPricing
        pricing = get_contract_pricing_for_period(db, c.id, period_yyyymm)
        if pricing:
            # Monthly allocation (annual / 12)
            monthly_tons = c.annual_tons / Decimal("12")
            
            sources.append(CoalSupplySource(
                source_id=c.contract_id,
                source_type="contract",
                supplier=c.supplier,
                tons=monthly_tons,
                btu_per_lb=pricing["btu_per_lb"],
                coal_price=pricing["coal_price"],
                barge_price=pricing["barge_price"],
                so2_lb_per_mmbtu=pricing.get("so2_lb_per_mmbtu", Decimal("0")),
            ))
    
    # Get uncommitted pricing for any gap or as fallback
    uncommitted_pricing = get_uncommitted_pricing_for_period(db, plant_id, year, month)
    
    # If no contracts, use uncommitted as sole source
    if not sources:
        if uncommitted_pricing:
            return {
                "coal_price_per_ton": uncommitted_pricing["price_per_ton"],
                "barge_price_per_ton": uncommitted_pricing["barge_per_ton"],
                "delivered_cost_per_ton": uncommitted_pricing["delivered_cost"],
                "btu_per_lb": uncommitted_pricing["btu_per_lb"],
                "cost_per_mmbtu": _calc_cost_per_mmbtu(
                    uncommitted_pricing["delivered_cost"],
                    uncommitted_pricing["btu_per_lb"]
                ),
                "source_breakdown": [{
                    "source": uncommitted_pricing["source_name"],
                    "type": "uncommitted",
                    "pct": 100,
                }],
            }
        else:
            # Ultimate fallback - default pricing
            default_btu = Decimal("12500")
            default_coal = Decimal("55")
            default_barge = Decimal("6")
            return {
                "coal_price_per_ton": default_coal,
                "barge_price_per_ton": default_barge,
                "delivered_cost_per_ton": default_coal + default_barge,
                "btu_per_lb": default_btu,
                "cost_per_mmbtu": _calc_cost_per_mmbtu(default_coal + default_barge, default_btu),
                "source_breakdown": [{
                    "source": "Default",
                    "type": "default",
                    "pct": 100,
                }],
            }
    
    # Calculate weighted averages from contracts
    averages = calculate_weighted_averages(sources)
    total_tons = sum(s.tons for s in sources)
    
    # Build source breakdown
    breakdown = []
    for s in sources:
        pct = float(s.tons / total_tons * 100) if total_tons > 0 else 0
        breakdown.append({
            "source": s.supplier,
            "type": s.source_type,
            "pct": round(pct, 1),
        })
    
    return {
        "coal_price_per_ton": averages["cost_per_ton"] - sum(s.barge_price * s.tons for s in sources) / total_tons if total_tons > 0 else Decimal("0"),
        "barge_price_per_ton": sum(s.barge_price * s.tons for s in sources) / total_tons if total_tons > 0 else Decimal("0"),
        "delivered_cost_per_ton": averages["cost_per_ton"],
        "btu_per_lb": averages["btu"],
        "cost_per_mmbtu": averages["cost_per_mmbtu"],
        "source_breakdown": breakdown,
    }


def _calc_cost_per_mmbtu(delivered_cost: Decimal, btu_per_lb: Decimal) -> Decimal:
    """Calculate cost per MMBtu from delivered cost and BTU content."""
    mmbtu_per_ton = btu_per_lb * Decimal("2000") / Decimal("1000000")
    if mmbtu_per_ton > 0:
        return delivered_cost / mmbtu_per_ton
    return Decimal("0")

