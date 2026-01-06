"""Emissions and allowance cost calculation module.

Calculates:
- NOx emissions from coal burn
- SO2 emissions (handled in consumables via limestone)
- Allowance costs based on emissions and market rates
- CO2 emissions (for future carbon pricing)
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from src.engine.generation import UnitParams, UnitGenerationResult

logger = logging.getLogger(__name__)


@dataclass
class AllowanceParams:
    """Parameters for emissions allowance cost calculation.
    
    Based on Excel model:
    - NOx allowances are required during ozone season (May-September)
    - Allowance rate varies by market conditions
    - CO2 tax is currently placeholder (not yet implemented)
    """
    # NOx allowance rates ($/ton NOx)
    nox_ozone_allowance_rate: Decimal = Decimal("2500")  # Ozone season rate
    nox_non_ozone_allowance_rate: Decimal = Decimal("500")  # Non-ozone season rate
    
    # NOx emission rate (lb NOx per MMBtu before SCR)
    nox_lb_per_mmbtu_uncontrolled: Decimal = Decimal("0.60")
    # SCR removal efficiency
    scr_removal_efficiency: Decimal = Decimal("0.90")  # 90% removal
    
    # CO2 emission rate (lb CO2 per MMBtu from coal)
    co2_lb_per_mmbtu: Decimal = Decimal("205.0")  # Typical for bituminous coal
    # CO2 tax rate ($/ton CO2) - currently 0, placeholder for future
    co2_tax_rate: Decimal = Decimal("0")
    
    # Include allowance costs in calculation
    include_allowance_costs: bool = True


@dataclass
class EmissionsResult:
    """Result of emissions calculation."""
    period_year: int
    period_month: int
    plant_name: str
    
    # Fuel consumption basis
    mmbtu_consumed: Decimal = Decimal("0")
    
    # NOx emissions
    nox_uncontrolled_lbs: Decimal = Decimal("0")
    nox_controlled_lbs: Decimal = Decimal("0")
    nox_tons: Decimal = Decimal("0")
    
    # CO2 emissions
    co2_lbs: Decimal = Decimal("0")
    co2_tons: Decimal = Decimal("0")
    
    # Allowance costs
    nox_allowance_cost: Decimal = Decimal("0")
    co2_tax_cost: Decimal = Decimal("0")
    total_allowance_cost: Decimal = Decimal("0")
    
    # Context
    is_ozone_season: bool = False
    allowance_rate_used: Decimal = Decimal("0")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "period": f"{self.period_year}-{self.period_month:02d}",
            "plant": self.plant_name,
            "mmbtu_consumed": float(self.mmbtu_consumed),
            "nox_tons": float(self.nox_tons),
            "co2_tons": float(self.co2_tons),
            "nox_allowance_cost": float(self.nox_allowance_cost),
            "co2_tax_cost": float(self.co2_tax_cost),
            "total_allowance_cost": float(self.total_allowance_cost),
            "is_ozone_season": self.is_ozone_season,
            "allowance_rate_used": float(self.allowance_rate_used),
        }


@dataclass
class UnitEmissionsResult:
    """Result of emissions calculation for a single unit.
    
    Key difference from plant-level: uses unit's actual SCR status
    instead of assuming all units have same SCR configuration.
    """
    unit_number: int
    has_scr: bool
    
    # Fuel consumption basis
    mmbtu_consumed: Decimal = Decimal("0")
    
    # NOx emissions
    nox_uncontrolled_lbs: Decimal = Decimal("0")
    nox_controlled_lbs: Decimal = Decimal("0")  # After SCR (0 if no SCR)
    nox_emitted_lbs: Decimal = Decimal("0")  # Actual emissions (controlled if SCR, uncontrolled if not)
    nox_tons: Decimal = Decimal("0")
    
    # NOx removed by SCR (for urea calculation)
    nox_removed_lbs: Decimal = Decimal("0")  # 0 if no SCR
    
    # CO2 emissions
    co2_lbs: Decimal = Decimal("0")
    co2_tons: Decimal = Decimal("0")
    
    # Allowance costs for this unit
    nox_allowance_cost: Decimal = Decimal("0")
    co2_tax_cost: Decimal = Decimal("0")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "unit_number": self.unit_number,
            "has_scr": self.has_scr,
            "mmbtu_consumed": float(self.mmbtu_consumed),
            "nox_uncontrolled_lbs": float(self.nox_uncontrolled_lbs),
            "nox_emitted_lbs": float(self.nox_emitted_lbs),
            "nox_removed_lbs": float(self.nox_removed_lbs),
            "nox_tons": float(self.nox_tons),
            "co2_tons": float(self.co2_tons),
            "nox_allowance_cost": float(self.nox_allowance_cost),
            "co2_tax_cost": float(self.co2_tax_cost),
        }


LBS_PER_TON = Decimal("2000")

# Ozone season months (May through September)
OZONE_SEASON_MONTHS = {5, 6, 7, 8, 9}


def is_ozone_season(month: int) -> bool:
    """Check if a month is in ozone season."""
    return month in OZONE_SEASON_MONTHS


def calculate_emissions(
    mmbtu_consumed: Decimal,
    year: int,
    month: int,
    plant_name: str,
    params: AllowanceParams = None,
) -> EmissionsResult:
    """Calculate emissions and allowance costs for a period.
    
    Args:
        mmbtu_consumed: MMBtu of fuel consumed
        year: Period year
        month: Period month (1-12)
        plant_name: Name of plant
        params: Optional allowance parameters
        
    Returns:
        EmissionsResult with emissions and costs
    """
    params = params or AllowanceParams()
    
    result = EmissionsResult(
        period_year=year,
        period_month=month,
        plant_name=plant_name,
        mmbtu_consumed=mmbtu_consumed,
    )
    
    # Calculate NOx emissions
    result.nox_uncontrolled_lbs = mmbtu_consumed * params.nox_lb_per_mmbtu_uncontrolled
    result.nox_controlled_lbs = result.nox_uncontrolled_lbs * (Decimal("1") - params.scr_removal_efficiency)
    result.nox_tons = result.nox_controlled_lbs / LBS_PER_TON
    
    # Calculate CO2 emissions
    result.co2_lbs = mmbtu_consumed * params.co2_lb_per_mmbtu
    result.co2_tons = result.co2_lbs / LBS_PER_TON
    
    # Determine allowance rate based on ozone season
    result.is_ozone_season = is_ozone_season(month)
    if result.is_ozone_season:
        result.allowance_rate_used = params.nox_ozone_allowance_rate
    else:
        result.allowance_rate_used = params.nox_non_ozone_allowance_rate
    
    # Calculate allowance costs
    if params.include_allowance_costs:
        result.nox_allowance_cost = result.nox_tons * result.allowance_rate_used
        result.co2_tax_cost = result.co2_tons * params.co2_tax_rate
        result.total_allowance_cost = result.nox_allowance_cost + result.co2_tax_cost
    
    return result


def calculate_unit_emissions(
    unit_number: int,
    has_scr: bool,
    mmbtu_consumed: Decimal,
    year: int,
    month: int,
    params: AllowanceParams = None,
    nox_lb_per_mmbtu_uncontrolled: Decimal = None,
    scr_removal_efficiency: Decimal = None,
) -> UnitEmissionsResult:
    """Calculate emissions for a single unit based on its SCR status.
    
    This function handles the key difference between SCR and non-SCR units:
    - SCR units: NOx is reduced by SCR removal efficiency (typically 90%)
    - Non-SCR units: Full uncontrolled NOx emissions
    
    Args:
        unit_number: Unit number
        has_scr: Whether unit has SCR installed
        mmbtu_consumed: MMBtu of fuel consumed by this unit
        year: Period year
        month: Period month (1-12)
        params: Optional allowance parameters for rates
        nox_lb_per_mmbtu_uncontrolled: Override uncontrolled NOx rate (from UnitParams)
        scr_removal_efficiency: Override SCR efficiency (from UnitParams)
        
    Returns:
        UnitEmissionsResult with unit-specific emissions
    """
    params = params or AllowanceParams()
    
    # Use provided rates or defaults from params
    nox_rate = nox_lb_per_mmbtu_uncontrolled or params.nox_lb_per_mmbtu_uncontrolled
    scr_eff = scr_removal_efficiency or params.scr_removal_efficiency
    
    result = UnitEmissionsResult(
        unit_number=unit_number,
        has_scr=has_scr,
        mmbtu_consumed=mmbtu_consumed,
    )
    
    # Calculate uncontrolled NOx (before any SCR)
    result.nox_uncontrolled_lbs = mmbtu_consumed * nox_rate
    
    # Apply SCR if equipped
    if has_scr:
        # SCR reduces NOx emissions
        result.nox_controlled_lbs = result.nox_uncontrolled_lbs * (Decimal("1") - scr_eff)
        result.nox_removed_lbs = result.nox_uncontrolled_lbs * scr_eff
        result.nox_emitted_lbs = result.nox_controlled_lbs
    else:
        # No SCR - full uncontrolled emissions
        result.nox_controlled_lbs = Decimal("0")
        result.nox_removed_lbs = Decimal("0")
        result.nox_emitted_lbs = result.nox_uncontrolled_lbs
    
    result.nox_tons = result.nox_emitted_lbs / LBS_PER_TON
    
    # Calculate CO2 emissions (same for all units)
    result.co2_lbs = mmbtu_consumed * params.co2_lb_per_mmbtu
    result.co2_tons = result.co2_lbs / LBS_PER_TON
    
    # Calculate allowance costs
    if params.include_allowance_costs:
        # Determine allowance rate based on ozone season
        if is_ozone_season(month):
            nox_rate = params.nox_ozone_allowance_rate
        else:
            nox_rate = params.nox_non_ozone_allowance_rate
        
        result.nox_allowance_cost = result.nox_tons * nox_rate
        result.co2_tax_cost = result.co2_tons * params.co2_tax_rate
    
    return result


def calculate_plant_emissions_by_unit(
    unit_mmbtu: Dict[int, Decimal],
    unit_scr_status: Dict[int, bool],
    year: int,
    month: int,
    plant_name: str,
    params: AllowanceParams = None,
) -> EmissionsResult:
    """Calculate plant emissions by summing unit-level emissions.
    
    This properly handles mixed SCR/non-SCR plants like Clifty Creek.
    
    Args:
        unit_mmbtu: Dict of unit_number -> MMBtu consumed
        unit_scr_status: Dict of unit_number -> has_scr
        year: Period year
        month: Period month
        plant_name: Plant name
        params: Optional allowance parameters
        
    Returns:
        EmissionsResult with plant totals
    """
    params = params or AllowanceParams()
    
    result = EmissionsResult(
        period_year=year,
        period_month=month,
        plant_name=plant_name,
        is_ozone_season=is_ozone_season(month),
    )
    
    # Determine allowance rate for this period
    if result.is_ozone_season:
        result.allowance_rate_used = params.nox_ozone_allowance_rate
    else:
        result.allowance_rate_used = params.nox_non_ozone_allowance_rate
    
    # Sum unit-level emissions
    total_mmbtu = Decimal("0")
    total_nox_uncontrolled = Decimal("0")
    total_nox_emitted = Decimal("0")
    total_co2 = Decimal("0")
    total_nox_cost = Decimal("0")
    total_co2_cost = Decimal("0")
    
    for unit_num, mmbtu in unit_mmbtu.items():
        has_scr = unit_scr_status.get(unit_num, True)
        unit_result = calculate_unit_emissions(
            unit_num, has_scr, mmbtu, year, month, params
        )
        
        total_mmbtu += mmbtu
        total_nox_uncontrolled += unit_result.nox_uncontrolled_lbs
        total_nox_emitted += unit_result.nox_emitted_lbs
        total_co2 += unit_result.co2_lbs
        total_nox_cost += unit_result.nox_allowance_cost
        total_co2_cost += unit_result.co2_tax_cost
    
    result.mmbtu_consumed = total_mmbtu
    result.nox_uncontrolled_lbs = total_nox_uncontrolled
    result.nox_controlled_lbs = total_nox_emitted  # This is actually "emitted" for mixed plants
    result.nox_tons = total_nox_emitted / LBS_PER_TON
    result.co2_lbs = total_co2
    result.co2_tons = total_co2 / LBS_PER_TON
    result.nox_allowance_cost = total_nox_cost
    result.co2_tax_cost = total_co2_cost
    result.total_allowance_cost = total_nox_cost + total_co2_cost
    
    return result


def calculate_annual_emissions(
    monthly_mmbtu: Dict[int, Decimal],
    year: int,
    plant_name: str,
    params: AllowanceParams = None,
) -> Dict:
    """Calculate annual emissions summary.
    
    Args:
        monthly_mmbtu: Dict of month -> MMBtu consumed
        year: Year
        plant_name: Plant name
        params: Optional allowance parameters
        
    Returns:
        Dictionary with annual totals
    """
    total_nox_tons = Decimal("0")
    total_co2_tons = Decimal("0")
    total_nox_cost = Decimal("0")
    total_co2_cost = Decimal("0")
    
    for month, mmbtu in monthly_mmbtu.items():
        result = calculate_emissions(mmbtu, year, month, plant_name, params)
        total_nox_tons += result.nox_tons
        total_co2_tons += result.co2_tons
        total_nox_cost += result.nox_allowance_cost
        total_co2_cost += result.co2_tax_cost
    
    return {
        "plant": plant_name,
        "year": year,
        "total_nox_tons": float(total_nox_tons),
        "total_co2_tons": float(total_co2_tons),
        "total_nox_allowance_cost": float(total_nox_cost),
        "total_co2_tax_cost": float(total_co2_cost),
        "total_allowance_cost": float(total_nox_cost + total_co2_cost),
    }

