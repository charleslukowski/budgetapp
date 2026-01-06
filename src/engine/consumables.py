"""Consumables calculation module.

Calculates reagent consumption and costs:
- Urea (for SCR NOx control)
- Limestone (for FGD SO2 control)
- Hydrated lime
- Mercury control reagents
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List
import logging

from src.engine.coal_burn import CoalBurnResult

logger = logging.getLogger(__name__)


@dataclass
class UreaParams:
    """Parameters for urea consumption calculation.
    
    Excel values for Q4 2025:
    - NOx removed: 0.46-0.54 lb/mmbtu (varies by month, avg ~0.50)
    - lb urea/lb NOx: 0.685
    - Urea $/ton: $458-460
    """
    nox_removed_lb_per_mmbtu: Decimal = Decimal("0.50")  # lb NOx removed per MMBtu (avg of Excel 0.46-0.54)
    lb_urea_per_lb_nox: Decimal = Decimal("0.685")  # lb urea per lb NOx removed (Excel: 0.685)
    urea_price_per_ton: Decimal = Decimal("459")  # $/ton (Excel Q4 2025: $458-460)


@dataclass
class LimestoneParams:
    """Parameters for limestone consumption calculation."""
    fgd_removal_efficiency: Decimal = Decimal("0.975")  # 97.5% SO2 removal
    lb_limestone_per_lb_so2: Decimal = Decimal("1.45")  # Stoichiometric ratio
    caco3_content_pct: Decimal = Decimal("0.905")  # CaCO3 purity
    moisture_pct: Decimal = Decimal("0.05")  # Moisture content
    limestone_price_per_ton: Decimal = Decimal("25")  # $/ton delivered


@dataclass
class HydratedLimeParams:
    """Parameters for hydrated lime calculation."""
    usage_rate_lb_per_mmbtu: Decimal = Decimal("0.1")  # lb per MMBtu (varies)
    price_per_ton: Decimal = Decimal("150")  # $/ton


@dataclass
class MercuryControlParams:
    """Parameters for mercury control reagents."""
    activated_carbon_lb_per_mmbtu: Decimal = Decimal("0.5")  # PAC injection rate
    activated_carbon_price_per_lb: Decimal = Decimal("0.75")
    bromide_lb_per_mmbtu: Decimal = Decimal("0.01")  # Calcium bromide
    bromide_price_per_lb: Decimal = Decimal("2.50")


@dataclass
class OtherFuelCostParams:
    """Parameters for other fuel-related costs (fixed monthly inputs).
    
    These are typically fixed monthly costs from the Excel Forecast Inputs:
    - Bioreactor: Fixed $/month for reagent + support
    - WWTP: Fixed $/month for wastewater treatment
    - Misc Reagents: Annual $/month amount
    - Fuel Oil: $/day rate
    - Labor & Handling: $/day rate with escalation
    - Temp Coal Storage: Monthly specific amounts
    """
    # Bioreactor costs ($/month)
    bioreactor_reagent_per_month: Decimal = Decimal("15000")  # Monthly reagent cost
    bioreactor_support_per_month: Decimal = Decimal("25000")  # Monthly support cost
    
    # WWTP Reagent ($/month)
    wwtp_reagent_per_month: Decimal = Decimal("8000")
    
    # Misc Reagents ($/month) - includes mercury, trona, other chemicals
    misc_reagent_per_month: Decimal = Decimal("5000")
    
    # Fuel Oil ($/day)
    fuel_oil_per_day: Decimal = Decimal("500")
    
    # Labor & Handling ($/day base rate)
    labor_handling_per_day: Decimal = Decimal("2500")
    labor_handling_escalation_pct: Decimal = Decimal("0.02")  # 2% annual
    
    # Temp Coal Storage ($/month) - typically 0 unless actively using storage
    temp_coal_storage_per_month: Decimal = Decimal("0")


@dataclass
class ConsumablesResult:
    """Result of consumables calculation."""
    period_year: int
    period_month: int
    plant_name: str
    
    # Basis
    mmbtu_consumed: Decimal = Decimal("0")
    so2_lbs_produced: Decimal = Decimal("0")
    
    # Urea
    urea_tons: Decimal = Decimal("0")
    urea_cost: Decimal = Decimal("0")
    
    # Limestone
    limestone_tons: Decimal = Decimal("0")
    limestone_cost: Decimal = Decimal("0")
    so2_removed_lbs: Decimal = Decimal("0")
    
    # Hydrated lime
    hydrated_lime_tons: Decimal = Decimal("0")
    hydrated_lime_cost: Decimal = Decimal("0")
    
    # Mercury control
    mercury_reagent_lbs: Decimal = Decimal("0")
    mercury_reagent_cost: Decimal = Decimal("0")
    
    # Total
    total_cost: Decimal = Decimal("0")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "period": f"{self.period_year}-{self.period_month:02d}",
            "plant": self.plant_name,
            "mmbtu_consumed": float(self.mmbtu_consumed),
            "urea_tons": float(self.urea_tons),
            "urea_cost": float(self.urea_cost),
            "limestone_tons": float(self.limestone_tons),
            "limestone_cost": float(self.limestone_cost),
            "hydrated_lime_tons": float(self.hydrated_lime_tons),
            "hydrated_lime_cost": float(self.hydrated_lime_cost),
            "mercury_reagent_lbs": float(self.mercury_reagent_lbs),
            "mercury_reagent_cost": float(self.mercury_reagent_cost),
            "total_cost": float(self.total_cost),
        }


LBS_PER_TON = Decimal("2000")


def calculate_urea(
    mmbtu: Decimal,
    params: UreaParams,
) -> Dict:
    """Calculate urea consumption and cost.
    
    Args:
        mmbtu: MMBtu of fuel consumed
        params: Urea parameters
        
    Returns:
        Dictionary with tons and cost
    """
    # lb NOx removed = MMBtu * lb NOx/MMBtu
    nox_removed_lbs = mmbtu * params.nox_removed_lb_per_mmbtu
    
    # lb urea = lb NOx * lb urea/lb NOx
    urea_lbs = nox_removed_lbs * params.lb_urea_per_lb_nox
    
    # tons urea
    urea_tons = urea_lbs / LBS_PER_TON
    
    # cost
    urea_cost = urea_tons * params.urea_price_per_ton
    
    return {
        "tons": urea_tons,
        "cost": urea_cost,
    }


def calculate_unit_urea(
    mmbtu: Decimal,
    has_scr: bool,
    params: UreaParams,
    nox_lb_per_mmbtu_uncontrolled: Decimal = None,
    scr_removal_efficiency: Decimal = None,
) -> Dict:
    """Calculate urea consumption for a single unit based on SCR status.
    
    Key difference from plant-level: Non-SCR units use NO urea.
    SCR units consume urea proportional to NOx removed.
    
    Args:
        mmbtu: MMBtu of fuel consumed by this unit
        has_scr: Whether the unit has SCR installed
        params: Urea parameters for pricing
        nox_lb_per_mmbtu_uncontrolled: Uncontrolled NOx rate (default 0.60)
        scr_removal_efficiency: SCR removal efficiency (default 0.90)
        
    Returns:
        Dictionary with tons, cost, and nox_removed_lbs
    """
    if not has_scr:
        # Non-SCR units use no urea
        return {
            "tons": Decimal("0"),
            "cost": Decimal("0"),
            "nox_removed_lbs": Decimal("0"),
        }
    
    # Default rates
    nox_rate = nox_lb_per_mmbtu_uncontrolled or Decimal("0.60")
    scr_eff = scr_removal_efficiency or Decimal("0.90")
    
    # Calculate NOx removed by SCR
    nox_uncontrolled_lbs = mmbtu * nox_rate
    nox_removed_lbs = nox_uncontrolled_lbs * scr_eff
    
    # lb urea = lb NOx removed * lb urea/lb NOx
    urea_lbs = nox_removed_lbs * params.lb_urea_per_lb_nox
    
    # tons urea
    urea_tons = urea_lbs / LBS_PER_TON
    
    # cost
    urea_cost = urea_tons * params.urea_price_per_ton
    
    return {
        "tons": urea_tons,
        "cost": urea_cost,
        "nox_removed_lbs": nox_removed_lbs,
    }


def calculate_plant_urea_by_unit(
    unit_mmbtu: Dict[int, Decimal],
    unit_scr_status: Dict[int, bool],
    params: UreaParams,
    unit_nox_rates: Dict[int, Decimal] = None,
    unit_scr_efficiencies: Dict[int, Decimal] = None,
) -> Dict:
    """Calculate total urea for a plant by summing unit contributions.
    
    Properly handles mixed SCR/non-SCR plants like Clifty Creek.
    
    Args:
        unit_mmbtu: Dict of unit_number -> MMBtu consumed
        unit_scr_status: Dict of unit_number -> has_scr
        params: Urea parameters for pricing
        unit_nox_rates: Optional dict of unit-specific NOx rates
        unit_scr_efficiencies: Optional dict of unit-specific SCR efficiencies
        
    Returns:
        Dictionary with totals and unit breakdown
    """
    total_tons = Decimal("0")
    total_cost = Decimal("0")
    total_nox_removed = Decimal("0")
    unit_results = {}
    
    for unit_num, mmbtu in unit_mmbtu.items():
        has_scr = unit_scr_status.get(unit_num, True)
        nox_rate = unit_nox_rates.get(unit_num) if unit_nox_rates else None
        scr_eff = unit_scr_efficiencies.get(unit_num) if unit_scr_efficiencies else None
        
        unit_urea = calculate_unit_urea(mmbtu, has_scr, params, nox_rate, scr_eff)
        
        total_tons += unit_urea["tons"]
        total_cost += unit_urea["cost"]
        total_nox_removed += unit_urea["nox_removed_lbs"]
        
        unit_results[unit_num] = unit_urea
    
    return {
        "total_tons": total_tons,
        "total_cost": total_cost,
        "total_nox_removed_lbs": total_nox_removed,
        "by_unit": unit_results,
    }


def calculate_limestone(
    so2_lbs_produced: Decimal,
    params: LimestoneParams,
) -> Dict:
    """Calculate limestone consumption and cost.
    
    Args:
        so2_lbs_produced: SO2 produced from coal burn (before removal)
        params: Limestone parameters
        
    Returns:
        Dictionary with tons, cost, and SO2 removed
    """
    # SO2 removed = SO2 produced * removal efficiency
    so2_removed = so2_lbs_produced * params.fgd_removal_efficiency
    
    # Limestone required (stoichiometric)
    # Adjusted for CaCO3 content and moisture
    limestone_lbs_pure = so2_removed * params.lb_limestone_per_lb_so2
    limestone_lbs_actual = limestone_lbs_pure / params.caco3_content_pct / (Decimal("1") - params.moisture_pct)
    
    limestone_tons = limestone_lbs_actual / LBS_PER_TON
    limestone_cost = limestone_tons * params.limestone_price_per_ton
    
    return {
        "tons": limestone_tons,
        "cost": limestone_cost,
        "so2_removed_lbs": so2_removed,
    }


def calculate_hydrated_lime(
    mmbtu: Decimal,
    params: HydratedLimeParams,
) -> Dict:
    """Calculate hydrated lime consumption and cost.
    
    Args:
        mmbtu: MMBtu consumed
        params: Hydrated lime parameters
        
    Returns:
        Dictionary with tons and cost
    """
    lime_lbs = mmbtu * params.usage_rate_lb_per_mmbtu
    lime_tons = lime_lbs / LBS_PER_TON
    lime_cost = lime_tons * params.price_per_ton
    
    return {
        "tons": lime_tons,
        "cost": lime_cost,
    }


def calculate_mercury_control(
    mmbtu: Decimal,
    params: MercuryControlParams,
) -> Dict:
    """Calculate mercury control reagent consumption and cost.
    
    Args:
        mmbtu: MMBtu consumed
        params: Mercury control parameters
        
    Returns:
        Dictionary with lbs and cost
    """
    # Activated carbon
    pac_lbs = mmbtu * params.activated_carbon_lb_per_mmbtu
    pac_cost = pac_lbs * params.activated_carbon_price_per_lb
    
    # Bromide
    bromide_lbs = mmbtu * params.bromide_lb_per_mmbtu
    bromide_cost = bromide_lbs * params.bromide_price_per_lb
    
    return {
        "total_lbs": pac_lbs + bromide_lbs,
        "total_cost": pac_cost + bromide_cost,
    }


def calculate_all_consumables(
    coal_burn: CoalBurnResult,
    urea_params: UreaParams = None,
    limestone_params: LimestoneParams = None,
    lime_params: HydratedLimeParams = None,
    mercury_params: MercuryControlParams = None,
) -> ConsumablesResult:
    """Calculate all consumables for a period.
    
    Args:
        coal_burn: Coal burn result with MMBtu and SO2
        urea_params: Optional urea parameters (defaults used if None)
        limestone_params: Optional limestone parameters
        lime_params: Optional hydrated lime parameters
        mercury_params: Optional mercury control parameters
        
    Returns:
        ConsumablesResult with all calculations
    """
    # Use defaults if not provided
    urea_params = urea_params or UreaParams()
    limestone_params = limestone_params or LimestoneParams()
    lime_params = lime_params or HydratedLimeParams()
    mercury_params = mercury_params or MercuryControlParams()
    
    result = ConsumablesResult(
        period_year=coal_burn.period_year,
        period_month=coal_burn.period_month,
        plant_name=coal_burn.plant_name,
        mmbtu_consumed=coal_burn.mmbtu_consumed,
        so2_lbs_produced=coal_burn.so2_lbs_produced,
    )
    
    # Calculate urea
    urea = calculate_urea(coal_burn.mmbtu_consumed, urea_params)
    result.urea_tons = urea["tons"]
    result.urea_cost = urea["cost"]
    
    # Calculate limestone
    limestone = calculate_limestone(coal_burn.so2_lbs_produced, limestone_params)
    result.limestone_tons = limestone["tons"]
    result.limestone_cost = limestone["cost"]
    result.so2_removed_lbs = limestone["so2_removed_lbs"]
    
    # Calculate hydrated lime
    lime = calculate_hydrated_lime(coal_burn.mmbtu_consumed, lime_params)
    result.hydrated_lime_tons = lime["tons"]
    result.hydrated_lime_cost = lime["cost"]
    
    # Calculate mercury control
    mercury = calculate_mercury_control(coal_burn.mmbtu_consumed, mercury_params)
    result.mercury_reagent_lbs = mercury["total_lbs"]
    result.mercury_reagent_cost = mercury["total_cost"]
    
    # Total cost
    result.total_cost = (
        result.urea_cost +
        result.limestone_cost +
        result.hydrated_lime_cost +
        result.mercury_reagent_cost
    )
    
    return result


def calculate_other_fuel_costs(
    year: int,
    month: int,
    params: OtherFuelCostParams,
    base_year: int = 2025,
) -> Dict:
    """Calculate other fuel-related costs for a period.
    
    Args:
        year: Year of the period
        month: Month of the period (1-12)
        params: Other fuel cost parameters
        base_year: Base year for escalation calculations
        
    Returns:
        Dictionary with all cost components
    """
    import calendar
    
    # Get days in month
    days_in_month = calendar.monthrange(year, month)[1]
    
    # Bioreactor: fixed monthly costs
    bioreactor_cost = params.bioreactor_reagent_per_month + params.bioreactor_support_per_month
    
    # WWTP Reagent: fixed monthly
    wwtp_cost = params.wwtp_reagent_per_month
    
    # Misc Reagents: fixed monthly
    misc_reagent_cost = params.misc_reagent_per_month
    
    # Fuel Oil: $/day × days
    fuel_oil_cost = params.fuel_oil_per_day * days_in_month
    
    # Labor & Handling: $/day × days with escalation
    years_from_base = year - base_year
    escalation_factor = (Decimal("1") + params.labor_handling_escalation_pct) ** years_from_base
    labor_handling_rate = params.labor_handling_per_day * escalation_factor
    labor_handling_cost = labor_handling_rate * days_in_month
    
    # Temp Coal Storage: fixed monthly (typically manually set)
    temp_storage_cost = params.temp_coal_storage_per_month
    
    return {
        "bioreactor_cost": bioreactor_cost,
        "wwtp_reagent_cost": wwtp_cost,
        "misc_reagent_cost": misc_reagent_cost,
        "fuel_oil_cost": fuel_oil_cost,
        "labor_handling_cost": labor_handling_cost,
        "temp_coal_storage_cost": temp_storage_cost,
        "total_other_fuel_cost": (
            bioreactor_cost + 
            wwtp_cost + 
            misc_reagent_cost + 
            fuel_oil_cost + 
            labor_handling_cost + 
            temp_storage_cost
        ),
    }


def summarize_annual_consumables(results: List[ConsumablesResult]) -> Dict:
    """Summarize annual consumables.
    
    Args:
        results: List of monthly ConsumablesResult
        
    Returns:
        Dictionary with annual totals
    """
    if not results:
        return {}
    
    return {
        "plant": results[0].plant_name,
        "year": results[0].period_year,
        "total_mmbtu": float(sum(r.mmbtu_consumed for r in results)),
        "total_urea_tons": float(sum(r.urea_tons for r in results)),
        "total_urea_cost": float(sum(r.urea_cost for r in results)),
        "total_limestone_tons": float(sum(r.limestone_tons for r in results)),
        "total_limestone_cost": float(sum(r.limestone_cost for r in results)),
        "total_hydrated_lime_tons": float(sum(r.hydrated_lime_tons for r in results)),
        "total_hydrated_lime_cost": float(sum(r.hydrated_lime_cost for r in results)),
        "total_mercury_cost": float(sum(r.mercury_reagent_cost for r in results)),
        "total_cost": float(sum(r.total_cost for r in results)),
    }

