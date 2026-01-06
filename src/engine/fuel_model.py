"""Fuel model integration module.

Combines all fuel cost components into a complete forecast:
- Generation
- Coal burn
- Coal supply costs
- Consumables (reagents)
- Byproducts (ash, gypsum)
- Total $/MWhr calculation

This module supports both:
1. Legacy FuelModelInputs-based calculation (backward compatible)
2. New driver-based calculation using the FuelModel driver framework
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Dict, Optional, TYPE_CHECKING
import logging

from sqlalchemy.orm import Session

from src.engine.generation import (
    GenerationResult,
    PlantParams,
    UnitGenerationResult,
    UseFactorParams,
    calculate_generation,
    get_unit_use_factors_for_plant,
    create_kyger_params,
    create_clifty_params,
    is_ozone_season,
)
from src.engine.coal_burn import (
    CoalBurnResult,
    CoalQuality,
    HeatRateParams,
    calculate_coal_burn,
    create_napp_coal,
    create_ilb_coal,
)
from src.engine.coal_supply import (
    CoalSupplyResult,
    calculate_coal_supply,
)
from src.engine.consumables import (
    ConsumablesResult,
    UreaParams,
    LimestoneParams,
    OtherFuelCostParams,
    calculate_all_consumables,
    calculate_other_fuel_costs,
    calculate_unit_urea,
    calculate_plant_urea_by_unit,
)
from src.engine.byproducts import (
    ByproductsResult,
    calculate_all_byproducts,
)
from src.engine.emissions import (
    AllowanceParams,
    calculate_emissions,
    calculate_unit_emissions,
    calculate_plant_emissions_by_unit,
)

# Import driver framework - use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from src.engine.drivers import FuelModel as DriverFuelModel

logger = logging.getLogger(__name__)


def load_inputs_from_db(
    db: Session,
    plant_id: int,
    year: int,
    month: int,
) -> "FuelModelInputs":
    """Load fuel model inputs from database.
    
    Loads from the specialized input tables:
    - use_factor_inputs: Use factors by plant/month
    - heat_rate_inputs: Heat rates by plant/unit/month
    - unit_outage_inputs: Outages by plant/unit/month (converted to availability)
    - coal_contract_pricing / uncommitted_coal_prices: Coal pricing
    
    Args:
        db: Database session
        plant_id: Plant ID (1=Kyger, 2=Clifty)
        year: Year
        month: Month (1-12)
        
    Returns:
        FuelModelInputs populated from database values
    """
    from src.models.use_factor import get_use_factors_for_year
    from src.models.heat_rate import get_heat_rate_for_month
    from src.models.unit_outage import build_unit_availability_from_db
    
    # Get plant params
    plant_params = create_kyger_params() if plant_id == 1 else create_clifty_params()
    num_units = len(plant_params.units)
    
    # Load use factors from database (use_factor_inputs table)
    db_use_factors = get_use_factors_for_year(db, plant_id, year)
    
    # Get the monthly use factor (or default)
    if month in db_use_factors:
        base_uf = Decimal(str(db_use_factors[month]["base"]))
        ozone_uf = Decimal(str(db_use_factors[month]["ozone_non_scr"]))
    else:
        base_uf = Decimal("0.85")
        ozone_uf = Decimal("0")  # Default: no generation for non-SCR during ozone
    
    # Build UseFactorParams with monthly overrides
    monthly_unit_overrides = {}
    for m, values in db_use_factors.items():
        # Apply base use factor for all units
        base = Decimal(str(values["base"]))
        ozone = Decimal(str(values["ozone_non_scr"]))
        for unit in plant_params.units:
            # Non-SCR units get ozone factor during ozone season
            if not unit.has_scr and m in {5, 6, 7, 8, 9}:
                monthly_unit_overrides[(m, unit.unit_number)] = ozone
            else:
                monthly_unit_overrides[(m, unit.unit_number)] = base
    
    use_factor_params = UseFactorParams(
        base_use_factor=base_uf,
        ozone_use_factor_non_scr=ozone_uf,
        monthly_unit_overrides=monthly_unit_overrides,
    )
    
    # Load heat rates from database (heat_rate_inputs table)
    hr_data = get_heat_rate_for_month(db, plant_id, year, month)
    
    heat_rate_params = HeatRateParams(
        baseline_heat_rate=Decimal(str(hr_data["baseline_heat_rate"])),
        min_load_heat_rate=Decimal(str(hr_data["min_load_heat_rate"])) if hr_data["min_load_heat_rate"] else None,
        suf_correction=Decimal(str(hr_data["suf_correction"])),
        prb_blend_pct=Decimal("0"),  # PRB blend handled separately if needed
    )
    
    # Load unit availability from outage data (unit_outage_inputs table)
    unit_availability = build_unit_availability_from_db(db, plant_id, year, month, num_units)
    
    # Apply availability to plant params
    for unit in plant_params.units:
        if unit.unit_number in unit_availability:
            unit.availability_factor = unit_availability[unit.unit_number]
    
    # Coal pricing - load from contracts (coal_contract_pricing) with uncommitted fallback
    # This replaces the deprecated coal_price_* drivers
    from src.engine.coal_supply import get_weighted_coal_pricing
    
    coal_pricing = get_weighted_coal_pricing(db, plant_id, year, month)
    coal_price = Decimal(str(coal_pricing["coal_price_per_ton"]))
    barge_price = Decimal(str(coal_pricing["barge_price_per_ton"]))
    
    # Coal quality from weighted contract data (or default)
    coal_btu = Decimal(str(coal_pricing["btu_per_lb"]))
    coal_quality = CoalQuality(
        name="Blended Contract Coal",
        btu_per_lb=coal_btu,
        so2_lb_per_mmbtu=Decimal("5.60"),  # lb SO2/MMBtu (Excel KC Emissions row 14-20)
        ash_pct=Decimal("0.10"),  # 10%
        moisture_pct=Decimal("0.06"),  # 6%
    )
    
    return FuelModelInputs(
        plant_params=plant_params,
        heat_rate_params=heat_rate_params,
        coal_quality=coal_quality,
        urea_params=UreaParams(),
        limestone_params=LimestoneParams(),
        other_fuel_cost_params=OtherFuelCostParams(),
        allowance_params=AllowanceParams(),
        use_factor_params=use_factor_params,
        use_factor=base_uf,
        coal_price_per_ton=coal_price,
        barge_price_per_ton=barge_price,
        use_unit_level_calc=True,
    )


def load_annual_inputs_from_db(
    db: Session,
    plant_id: int,
    year: int,
) -> Dict[int, "FuelModelInputs"]:
    """Load fuel model inputs for all months from database.
    
    Args:
        db: Database session
        plant_id: Plant ID
        year: Year
        
    Returns:
        Dictionary of month -> FuelModelInputs
    """
    inputs_by_month = {}
    for month in range(1, 13):
        inputs_by_month[month] = load_inputs_from_db(db, plant_id, year, month)
    return inputs_by_month


@dataclass
class FuelCostSummary:
    """Complete fuel cost summary for a period."""
    period_year: int
    period_month: int
    plant_name: str
    
    # Generation
    net_delivered_mwh: Decimal = Decimal("0")
    capacity_factor: Decimal = Decimal("0")
    
    # Coal consumption
    coal_tons_consumed: Decimal = Decimal("0")
    coal_mmbtu_consumed: Decimal = Decimal("0")
    heat_rate: Decimal = Decimal("0")
    
    # Coal costs
    coal_cost: Decimal = Decimal("0")
    coal_cost_per_ton: Decimal = Decimal("0")
    coal_cost_per_mmbtu: Decimal = Decimal("0")
    
    # Other fuel costs
    consumables_cost: Decimal = Decimal("0")
    urea_cost: Decimal = Decimal("0")
    limestone_cost: Decimal = Decimal("0")
    other_reagent_cost: Decimal = Decimal("0")
    
    # Additional cost categories (Phase 2)
    allowance_cost: Decimal = Decimal("0")
    co2_tax: Decimal = Decimal("0")
    hydrated_lime_cost: Decimal = Decimal("0")
    bioreactor_cost: Decimal = Decimal("0")
    wwtp_reagent_cost: Decimal = Decimal("0")
    misc_reagent_cost: Decimal = Decimal("0")
    fuel_oil_cost: Decimal = Decimal("0")
    labor_handling_cost: Decimal = Decimal("0")
    temp_coal_storage_cost: Decimal = Decimal("0")
    
    # Byproducts - split by sales vs costs
    byproduct_sales_revenue: Decimal = Decimal("0")  # Negative = credit/income
    byproduct_disposal_costs: Decimal = Decimal("0")  # Positive = expense
    byproduct_misc_expense: Decimal = Decimal("0")  # Fixed monthly expense
    byproduct_net_cost: Decimal = Decimal("0")  # Total net (positive = cost)
    
    # Byproduct detail by type
    ash_net_cost: Decimal = Decimal("0")
    gypsum_net_cost: Decimal = Decimal("0")
    
    # Totals
    total_fuel_cost: Decimal = Decimal("0")
    fuel_cost_per_mwh: Decimal = Decimal("0")
    
    # Unit-level breakdown (populated when use_unit_level_calc=True)
    unit_generation: Dict[int, Decimal] = field(default_factory=dict)  # unit_num -> MWh
    unit_mmbtu: Dict[int, Decimal] = field(default_factory=dict)  # unit_num -> MMBtu
    unit_nox_tons: Dict[int, Decimal] = field(default_factory=dict)  # unit_num -> tons NOx
    unit_urea_cost: Dict[int, Decimal] = field(default_factory=dict)  # unit_num -> $ urea
    unit_curtailed: Dict[int, bool] = field(default_factory=dict)  # unit_num -> is_curtailed
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "period": f"{self.period_year}-{self.period_month:02d}",
            "plant": self.plant_name,
            "net_delivered_mwh": float(self.net_delivered_mwh),
            "capacity_factor": float(self.capacity_factor),
            "coal_tons_consumed": float(self.coal_tons_consumed),
            "coal_mmbtu_consumed": float(self.coal_mmbtu_consumed),
            "heat_rate": float(self.heat_rate),
            "coal_cost": float(self.coal_cost),
            "coal_cost_per_ton": float(self.coal_cost_per_ton),
            "coal_cost_per_mmbtu": float(self.coal_cost_per_mmbtu),
            "consumables_cost": float(self.consumables_cost),
            "urea_cost": float(self.urea_cost),
            "limestone_cost": float(self.limestone_cost),
            "other_reagent_cost": float(self.other_reagent_cost),
            "allowance_cost": float(self.allowance_cost),
            "co2_tax": float(self.co2_tax),
            "hydrated_lime_cost": float(self.hydrated_lime_cost),
            "bioreactor_cost": float(self.bioreactor_cost),
            "wwtp_reagent_cost": float(self.wwtp_reagent_cost),
            "misc_reagent_cost": float(self.misc_reagent_cost),
            "fuel_oil_cost": float(self.fuel_oil_cost),
            "labor_handling_cost": float(self.labor_handling_cost),
            "temp_coal_storage_cost": float(self.temp_coal_storage_cost),
            "byproduct_sales_revenue": float(self.byproduct_sales_revenue),
            "byproduct_disposal_costs": float(self.byproduct_disposal_costs),
            "byproduct_misc_expense": float(self.byproduct_misc_expense),
            "byproduct_net_cost": float(self.byproduct_net_cost),
            "ash_net_cost": float(self.ash_net_cost),
            "gypsum_net_cost": float(self.gypsum_net_cost),
            "total_fuel_cost": float(self.total_fuel_cost),
            "fuel_cost_per_mwh": float(self.fuel_cost_per_mwh),
            # Unit-level breakdowns
            "unit_generation": {k: float(v) for k, v in self.unit_generation.items()},
            "unit_mmbtu": {k: float(v) for k, v in self.unit_mmbtu.items()},
            "unit_nox_tons": {k: float(v) for k, v in self.unit_nox_tons.items()},
            "unit_urea_cost": {k: float(v) for k, v in self.unit_urea_cost.items()},
            "unit_curtailed": self.unit_curtailed,
        }


@dataclass
class FuelModelInputs:
    """Inputs for fuel model calculation."""
    plant_params: PlantParams
    heat_rate_params: HeatRateParams = field(default_factory=HeatRateParams)
    coal_quality: CoalQuality = field(default_factory=create_napp_coal)
    urea_params: UreaParams = field(default_factory=UreaParams)
    limestone_params: LimestoneParams = field(default_factory=LimestoneParams)
    other_fuel_cost_params: OtherFuelCostParams = field(default_factory=OtherFuelCostParams)
    allowance_params: AllowanceParams = field(default_factory=AllowanceParams)
    use_factor_params: UseFactorParams = field(default_factory=UseFactorParams)
    use_factor: Decimal = Decimal("0.85")  # Legacy: base use factor
    coal_price_per_ton: Decimal = Decimal("55")
    barge_price_per_ton: Decimal = Decimal("6")
    
    # Unit-level calculation mode
    use_unit_level_calc: bool = True  # Enable unit-level generation/emissions


def calculate_fuel_costs(
    db: Session,
    plant_id: int,
    year: int,
    month: int,
    inputs: FuelModelInputs = None,
) -> FuelCostSummary:
    """Calculate complete fuel costs for a period.
    
    Supports two modes:
    1. Unit-level (default): Calculates generation/emissions per unit, properly
       handling SCR vs non-SCR units and ozone season curtailment
    2. Legacy: Plant-level calculation with uniform use factor
    
    If inputs are not provided, they will be loaded from the database.
    
    Args:
        db: Database session
        plant_id: Plant ID (1=Kyger, 2=Clifty)
        year: Year
        month: Month (1-12)
        inputs: Fuel model input parameters (optional - loads from DB if None)
        
    Returns:
        FuelCostSummary with all calculations
    """
    # Load inputs from database if not provided
    if inputs is None:
        inputs = load_inputs_from_db(db, plant_id, year, month)
    summary = FuelCostSummary(
        period_year=year,
        period_month=month,
        plant_name=inputs.plant_params.plant_name,
    )
    
    # Step 1: Calculate generation (unit-level or plant-level)
    if inputs.use_unit_level_calc:
        # Get unit-specific use factors based on SCR status and ozone season
        unit_use_factors = {}
        for unit in inputs.plant_params.units:
            unit_use_factors[unit.unit_number] = inputs.use_factor_params.get_use_factor(
                unit.unit_number, month, unit.has_scr
            )
        
        generation = calculate_generation(
            inputs.plant_params,
            year,
            month,
            inputs.use_factor_params.base_use_factor,
            unit_use_factors=unit_use_factors,
        )
    else:
        # Legacy: uniform use factor for all units
        generation = calculate_generation(
            inputs.plant_params,
            year,
            month,
            inputs.use_factor,
        )
    
    summary.net_delivered_mwh = generation.net_delivered_mwh
    summary.capacity_factor = generation.capacity_factor
    
    # Step 2: Calculate coal burn
    coal_burn = calculate_coal_burn(
        generation,
        inputs.heat_rate_params,
        inputs.coal_quality,
    )
    summary.coal_tons_consumed = coal_burn.tons_consumed
    summary.coal_mmbtu_consumed = coal_burn.mmbtu_consumed
    summary.heat_rate = coal_burn.heat_rate_btu_kwh
    
    # Step 3: Calculate coal supply costs
    # Use weighted average pricing from contracts, apply to actual consumption
    try:
        coal_supply = calculate_coal_supply(
            db,
            plant_id,
            year,
            month,
            coal_burn.tons_consumed,
        )
        if coal_supply.weighted_avg_cost_per_ton > 0:
            # Use consumption * weighted avg price (not delivery schedule total)
            summary.coal_cost = coal_burn.tons_consumed * coal_supply.weighted_avg_cost_per_ton
            summary.coal_cost_per_ton = coal_supply.weighted_avg_cost_per_ton
            summary.coal_cost_per_mmbtu = coal_supply.weighted_avg_cost_per_mmbtu
    except Exception:
        pass
    
    # Fallback: simple cost calculation
    if summary.coal_cost == 0:
        delivered_cost = inputs.coal_price_per_ton + inputs.barge_price_per_ton
        summary.coal_cost = coal_burn.tons_consumed * delivered_cost
        summary.coal_cost_per_ton = delivered_cost
        mmbtu_per_ton = inputs.coal_quality.mmbtu_per_ton
        if mmbtu_per_ton > 0:
            summary.coal_cost_per_mmbtu = delivered_cost / mmbtu_per_ton
    
    # Step 4: Calculate consumables (unit-level aware for urea)
    if inputs.use_unit_level_calc and generation.unit_results:
        # Allocate MMBTU to units based on generation proportion
        total_gen = sum(u.net_mwh for u in generation.unit_results)
        unit_mmbtu = {}
        unit_scr_status = {}
        
        for unit_result in generation.unit_results:
            if total_gen > 0:
                unit_proportion = unit_result.net_mwh / total_gen
                unit_mmbtu[unit_result.unit_number] = coal_burn.mmbtu_consumed * unit_proportion
            else:
                unit_mmbtu[unit_result.unit_number] = Decimal("0")
            unit_scr_status[unit_result.unit_number] = unit_result.has_scr
        
        # Calculate urea by unit (only SCR units consume urea)
        urea_result = calculate_plant_urea_by_unit(
            unit_mmbtu, unit_scr_status, inputs.urea_params
        )
        summary.urea_cost = urea_result["total_cost"]
        
        # Calculate other consumables normally
        consumables = calculate_all_consumables(
            coal_burn,
            inputs.urea_params,
            inputs.limestone_params,
        )
        # Override urea with unit-level calculation
        consumables.urea_cost = urea_result["total_cost"]
        consumables.urea_tons = urea_result["total_tons"]
        consumables.total_cost = (
            consumables.urea_cost +
            consumables.limestone_cost +
            consumables.hydrated_lime_cost +
            consumables.mercury_reagent_cost
        )
    else:
        # Legacy: plant-level consumables
        consumables = calculate_all_consumables(
            coal_burn,
            inputs.urea_params,
            inputs.limestone_params,
        )
    
    summary.consumables_cost = consumables.total_cost
    summary.urea_cost = consumables.urea_cost
    summary.limestone_cost = consumables.limestone_cost
    summary.hydrated_lime_cost = consumables.hydrated_lime_cost
    summary.other_reagent_cost = consumables.hydrated_lime_cost + consumables.mercury_reagent_cost
    
    # Step 5: Calculate other fuel costs (fixed monthly costs)
    other_costs = calculate_other_fuel_costs(
        year,
        month,
        inputs.other_fuel_cost_params,
    )
    summary.bioreactor_cost = other_costs["bioreactor_cost"]
    summary.wwtp_reagent_cost = other_costs["wwtp_reagent_cost"]
    summary.misc_reagent_cost = other_costs["misc_reagent_cost"]
    summary.fuel_oil_cost = other_costs["fuel_oil_cost"]
    summary.labor_handling_cost = other_costs["labor_handling_cost"]
    summary.temp_coal_storage_cost = other_costs["temp_coal_storage_cost"]
    
    # Step 6: Calculate byproducts (including misc expense from Excel model)
    # Misc byproduct expense: ~$310,000/month per plant (covers handling, equipment, ops)
    misc_byproduct_expense = Decimal("310000")  # Fixed monthly expense per Excel
    
    byproducts = calculate_all_byproducts(
        coal_burn, consumables,
        misc_expense=misc_byproduct_expense
    )
    # Split byproducts into sales revenue vs costs
    summary.byproduct_sales_revenue = byproducts.total_sales_revenue
    summary.byproduct_disposal_costs = byproducts.total_disposal_costs
    summary.byproduct_misc_expense = byproducts.misc_byproduct_expense
    summary.byproduct_net_cost = byproducts.total_net_cost
    summary.ash_net_cost = byproducts.total_ash_net_cost
    summary.gypsum_net_cost = byproducts.gypsum_net_cost
    
    # Step 7: Calculate emissions and allowance costs (unit-level aware)
    if inputs.use_unit_level_calc and generation.unit_results:
        # Calculate emissions by unit (handles SCR vs non-SCR)
        emissions = calculate_plant_emissions_by_unit(
            unit_mmbtu,
            unit_scr_status,
            year,
            month,
            inputs.plant_params.plant_name,
            inputs.allowance_params,
        )
    else:
        # Legacy: plant-level emissions
        emissions = calculate_emissions(
            coal_burn.mmbtu_consumed,
            year,
            month,
            inputs.plant_params.plant_name,
            inputs.allowance_params,
        )
    summary.allowance_cost = emissions.nox_allowance_cost
    summary.co2_tax = emissions.co2_tax_cost
    
    # Populate unit-level breakdowns
    if inputs.use_unit_level_calc and generation.unit_results:
        for unit_result in generation.unit_results:
            unit_num = unit_result.unit_number
            summary.unit_generation[unit_num] = unit_result.net_mwh
            summary.unit_mmbtu[unit_num] = unit_mmbtu.get(unit_num, Decimal("0"))
            summary.unit_curtailed[unit_num] = unit_result.is_curtailed
            
            # Get unit-level urea cost from the urea calculation
            if "by_unit" in urea_result and unit_num in urea_result["by_unit"]:
                summary.unit_urea_cost[unit_num] = urea_result["by_unit"][unit_num]["cost"]
            else:
                summary.unit_urea_cost[unit_num] = Decimal("0")
        
        # Calculate unit-level NOx using the emissions module
        for unit_num, mmbtu in unit_mmbtu.items():
            has_scr = unit_scr_status.get(unit_num, True)
            unit_emissions = calculate_unit_emissions(
                unit_num, has_scr, mmbtu, year, month, inputs.allowance_params
            )
            summary.unit_nox_tons[unit_num] = unit_emissions.nox_tons
    
    # Step 8: Calculate totals
    summary.total_fuel_cost = (
        summary.coal_cost +
        summary.consumables_cost +
        other_costs["total_other_fuel_cost"] +
        summary.allowance_cost +
        summary.co2_tax +
        summary.byproduct_net_cost
    )
    
    if summary.net_delivered_mwh > 0:
        summary.fuel_cost_per_mwh = summary.total_fuel_cost / summary.net_delivered_mwh
    
    return summary


def calculate_annual_fuel_costs(
    db: Session,
    plant_id: int,
    year: int,
    inputs: FuelModelInputs,
    monthly_use_factors: Dict[int, Decimal] = None,
) -> List[FuelCostSummary]:
    """Calculate fuel costs for all months in a year.
    
    Args:
        db: Database session
        plant_id: Plant ID
        year: Year
        inputs: Fuel model inputs
        monthly_use_factors: Optional dict of month -> use factor
        
    Returns:
        List of monthly FuelCostSummary
    """
    results = []
    
    for month in range(1, 13):
        if monthly_use_factors and month in monthly_use_factors:
            inputs.use_factor = monthly_use_factors[month]
        
        summary = calculate_fuel_costs(db, plant_id, year, month, inputs)
        results.append(summary)
    
    return results


def summarize_annual_fuel_costs(summaries: List[FuelCostSummary]) -> Dict:
    """Summarize annual fuel costs.
    
    Args:
        summaries: List of monthly FuelCostSummary
        
    Returns:
        Dictionary with annual totals and averages
    """
    if not summaries:
        return {}
    
    total_mwh = sum(s.net_delivered_mwh for s in summaries)
    total_fuel_cost = sum(s.total_fuel_cost for s in summaries)
    
    total_coal_mmbtu = sum(s.coal_mmbtu_consumed for s in summaries)
    total_coal_cost = sum(s.coal_cost for s in summaries)
    total_consumables_cost = sum(s.consumables_cost for s in summaries)
    
    # Byproduct totals - split by sales vs costs
    total_byproduct_sales = sum(s.byproduct_sales_revenue for s in summaries)
    total_byproduct_disposal = sum(s.byproduct_disposal_costs for s in summaries)
    total_byproduct_misc = sum(s.byproduct_misc_expense for s in summaries)
    total_byproduct_net = sum(s.byproduct_net_cost for s in summaries)
    non_coal_fuel_cost = total_consumables_cost + total_byproduct_net
    
    return {
        "plant": summaries[0].plant_name,
        "year": summaries[0].period_year,
        "total_mwh": float(total_mwh),
        "total_coal_tons": float(sum(s.coal_tons_consumed for s in summaries)),
        "total_coal_mmbtu": float(total_coal_mmbtu),
        "avg_heat_rate": float(sum(s.heat_rate for s in summaries) / len(summaries)),
        "total_coal_cost": float(total_coal_cost),
        "avg_coal_cost_per_mmbtu": float(total_coal_cost / total_coal_mmbtu) if total_coal_mmbtu > 0 else 0,
        "total_consumables_cost": float(total_consumables_cost),
        "total_urea_cost": float(sum(s.urea_cost for s in summaries)),
        "total_limestone_cost": float(sum(s.limestone_cost for s in summaries)),
        "total_other_reagent_cost": float(sum(s.other_reagent_cost for s in summaries)),
        # New cost categories
        "total_allowance_cost": float(sum(s.allowance_cost for s in summaries)),
        "total_co2_tax": float(sum(s.co2_tax for s in summaries)),
        "total_hydrated_lime_cost": float(sum(s.hydrated_lime_cost for s in summaries)),
        "total_bioreactor_cost": float(sum(s.bioreactor_cost for s in summaries)),
        "total_wwtp_reagent_cost": float(sum(s.wwtp_reagent_cost for s in summaries)),
        "total_misc_reagent_cost": float(sum(s.misc_reagent_cost for s in summaries)),
        "total_fuel_oil_cost": float(sum(s.fuel_oil_cost for s in summaries)),
        "total_labor_handling_cost": float(sum(s.labor_handling_cost for s in summaries)),
        "total_temp_coal_storage_cost": float(sum(s.temp_coal_storage_cost for s in summaries)),
        "total_byproduct_sales_revenue": float(total_byproduct_sales),
        "total_byproduct_disposal_costs": float(total_byproduct_disposal),
        "total_byproduct_misc_expense": float(total_byproduct_misc),
        "total_byproduct_net": float(total_byproduct_net),
        "total_fuel_cost": float(total_fuel_cost),
        "avg_fuel_cost_per_mwh": float(total_fuel_cost / total_mwh) if total_mwh > 0 else 0,
        "non_coal_fuel_cost_per_mwh": float(non_coal_fuel_cost / total_mwh) if total_mwh > 0 else 0,
        "avg_capacity_factor": float(sum(s.capacity_factor for s in summaries) / len(summaries)),
    }


def calculate_system_fuel_costs(
    db: Session,
    year: int,
    kyger_inputs: FuelModelInputs = None,
    clifty_inputs: FuelModelInputs = None,
) -> Dict:
    """Calculate combined system fuel costs.
    
    Args:
        db: Database session
        year: Year
        kyger_inputs: Optional Kyger inputs (defaults used if None)
        clifty_inputs: Optional Clifty inputs (defaults used if None)
        
    Returns:
        Dictionary with system totals
    """
    # Default inputs
    if kyger_inputs is None:
        kyger_inputs = FuelModelInputs(plant_params=create_kyger_params())
    if clifty_inputs is None:
        clifty_inputs = FuelModelInputs(plant_params=create_clifty_params())
    
    # Calculate for each plant
    kyger_monthly = calculate_annual_fuel_costs(db, 1, year, kyger_inputs)
    clifty_monthly = calculate_annual_fuel_costs(db, 2, year, clifty_inputs)
    
    kyger_annual = summarize_annual_fuel_costs(kyger_monthly)
    clifty_annual = summarize_annual_fuel_costs(clifty_monthly)
    
    # Combine system totals
    system_mwh = kyger_annual.get("total_mwh", 0) + clifty_annual.get("total_mwh", 0)
    system_fuel_cost = kyger_annual.get("total_fuel_cost", 0) + clifty_annual.get("total_fuel_cost", 0)
    
    return {
        "year": year,
        "kyger": kyger_annual,
        "clifty": clifty_annual,
        "system": {
            "total_mwh": system_mwh,
            "total_coal_tons": kyger_annual.get("total_coal_tons", 0) + clifty_annual.get("total_coal_tons", 0),
            "total_fuel_cost": system_fuel_cost,
            "avg_fuel_cost_per_mwh": system_fuel_cost / system_mwh if system_mwh > 0 else 0,
        },
    }


def compare_to_budget(
    db: Session,
    year: int,
    plant_id: int,
    calculated_costs: List[FuelCostSummary],
) -> Dict:
    """Compare calculated fuel costs to budget.
    
    Args:
        db: Database session
        year: Year
        plant_id: Plant ID
        calculated_costs: Calculated fuel costs
        
    Returns:
        Dictionary with comparison
    """
    from src.etl.budget_import import get_budget_by_month
    
    budget_by_month = get_budget_by_month(db, year, 
        "Kyger" if plant_id == 1 else "Clifty")
    
    comparison = []
    for summary in calculated_costs:
        month = summary.period_month
        budget_amount = float(budget_by_month.get(month, Decimal("0")))
        calculated_amount = float(summary.total_fuel_cost)
        variance = budget_amount - calculated_amount
        
        comparison.append({
            "month": month,
            "budget": budget_amount,
            "calculated": calculated_amount,
            "variance": variance,
            "variance_pct": (variance / budget_amount * 100) if budget_amount else 0,
        })
    
    return {
        "plant_id": plant_id,
        "year": year,
        "monthly": comparison,
        "total_budget": sum(c["budget"] for c in comparison),
        "total_calculated": sum(c["calculated"] for c in comparison),
        "total_variance": sum(c["variance"] for c in comparison),
    }


# =============================================================================
# Driver-Based Fuel Model Integration
# =============================================================================

def inputs_from_drivers(
    driver_model: 'DriverFuelModel',
    plant_id: int,
    year: int,
    month: int,
) -> FuelModelInputs:
    """Create FuelModelInputs from a driver model.
    
    Bridges the new driver-based system with the legacy FuelModelInputs.
    
    Args:
        driver_model: Driver model with values
        plant_id: Plant ID (1=Kyger, 2=Clifty)
        year: Year
        month: Month
        
    Returns:
        FuelModelInputs populated from drivers
    """
    # Import here to avoid circular imports
    from src.engine.drivers import FuelModel as DriverFuelModel
    
    # Get plant parameters
    plant_params = create_kyger_params() if plant_id == 1 else create_clifty_params()
    
    # Get heat rate from drivers
    try:
        baseline = driver_model.get_driver_value("heat_rate_baseline", year, month, plant_id)
        suf = driver_model.get_driver_value("heat_rate_suf_correction", year, month, plant_id)
        prb_pct = driver_model.get_driver_value("coal_blend_prb_pct", year, month, plant_id)
    except ValueError:
        # Fall back to defaults if drivers not registered
        baseline = Decimal("9850")
        suf = Decimal("0")
        prb_pct = Decimal("0")
    
    heat_rate_params = HeatRateParams(
        baseline_heat_rate=baseline,
        suf_correction=suf,
        prb_blend_pct=prb_pct / Decimal("100") if prb_pct else Decimal("0"),
    )
    
    # Get coal quality based on blend
    try:
        eastern_pct = driver_model.get_driver_value("coal_blend_eastern_pct", year, month, plant_id)
        ilb_pct = driver_model.get_driver_value("coal_blend_ilb_pct", year, month, plant_id)
    except ValueError:
        eastern_pct = Decimal("100")
        ilb_pct = Decimal("0")
    
    # Simple blend: if mostly Eastern, use NAPP; if mostly ILB, use ILB
    if ilb_pct > eastern_pct:
        coal_quality = create_ilb_coal()
    else:
        coal_quality = create_napp_coal()
    
    # Get use factor
    try:
        use_factor = driver_model.get_driver_value("use_factor", year, month, plant_id) / Decimal("100")
    except ValueError:
        use_factor = Decimal("0.85")
    
    # Get coal pricing
    try:
        coal_price = driver_model.get_driver_value("coal_price_blended", year, month, plant_id)
    except ValueError:
        try:
            coal_price = driver_model.get_driver_value("coal_price_eastern", year, month, plant_id)
        except ValueError:
            coal_price = Decimal("55")
    
    try:
        barge_price = driver_model.get_driver_value("barge_rate_ohio", year, month, plant_id)
    except ValueError:
        barge_price = Decimal("6")
    
    return FuelModelInputs(
        plant_params=plant_params,
        heat_rate_params=heat_rate_params,
        coal_quality=coal_quality,
        use_factor=use_factor,
        coal_price_per_ton=coal_price,
        barge_price_per_ton=barge_price,
    )


def calculate_fuel_costs_from_drivers(
    db: Session,
    driver_model: 'DriverFuelModel',
    plant_id: int,
    year: int,
    month: int,
) -> FuelCostSummary:
    """Calculate fuel costs using driver-based inputs.
    
    Args:
        db: Database session
        driver_model: Driver model with values
        plant_id: Plant ID (1=Kyger, 2=Clifty)
        year: Year
        month: Month (1-12)
        
    Returns:
        FuelCostSummary with all calculations
    """
    inputs = inputs_from_drivers(driver_model, plant_id, year, month)
    return calculate_fuel_costs(db, plant_id, year, month, inputs)


def calculate_annual_fuel_costs_from_drivers(
    db: Session,
    driver_model: 'DriverFuelModel',
    plant_id: int,
    year: int,
) -> List[FuelCostSummary]:
    """Calculate annual fuel costs using driver-based inputs.
    
    Args:
        db: Database session
        driver_model: Driver model with values
        plant_id: Plant ID
        year: Year
        
    Returns:
        List of monthly FuelCostSummary
    """
    results = []
    for month in range(1, 13):
        summary = calculate_fuel_costs_from_drivers(db, driver_model, plant_id, year, month)
        results.append(summary)
    return results


def calculate_system_fuel_costs_from_drivers(
    db: Session,
    driver_model: 'DriverFuelModel',
    year: int,
) -> Dict:
    """Calculate combined system fuel costs using driver-based inputs.
    
    Args:
        db: Database session
        driver_model: Driver model with values
        year: Year
        
    Returns:
        Dictionary with system totals
    """
    # Calculate for each plant
    kyger_monthly = calculate_annual_fuel_costs_from_drivers(db, driver_model, 1, year)
    clifty_monthly = calculate_annual_fuel_costs_from_drivers(db, driver_model, 2, year)
    
    kyger_annual = summarize_annual_fuel_costs(kyger_monthly)
    clifty_annual = summarize_annual_fuel_costs(clifty_monthly)
    
    # Combine system totals
    system_mwh = kyger_annual.get("total_mwh", 0) + clifty_annual.get("total_mwh", 0)
    system_fuel_cost = kyger_annual.get("total_fuel_cost", 0) + clifty_annual.get("total_fuel_cost", 0)
    
    return {
        "year": year,
        "kyger": kyger_annual,
        "clifty": clifty_annual,
        "system": {
            "total_mwh": system_mwh,
            "total_coal_tons": kyger_annual.get("total_coal_tons", 0) + clifty_annual.get("total_coal_tons", 0),
            "total_fuel_cost": system_fuel_cost,
            "avg_fuel_cost_per_mwh": system_fuel_cost / system_mwh if system_mwh > 0 else 0,
        },
    }


# Re-export driver framework classes for convenience
# This allows: from src.engine.fuel_model import FuelModel, Driver, DriverType
def _get_driver_exports():
    """Lazy import of driver framework to avoid circular imports."""
    from src.engine.drivers import (
        Driver,
        DriverType,
        DriverCategory,
        FuelModel as DriverFuelModel,
        DriverValueStore,
        create_calculation,
    )
    from src.engine.default_drivers import (
        create_default_fuel_model,
        ALL_DRIVERS,
        COAL_PRICE_DRIVERS,
        TRANSPORTATION_DRIVERS,
        HEAT_RATE_DRIVERS,
        GENERATION_DRIVERS,
        INVENTORY_DRIVERS,
        ESCALATION_DRIVERS,
    )
    return {
        'Driver': Driver,
        'DriverType': DriverType,
        'DriverCategory': DriverCategory,
        'FuelModel': DriverFuelModel,
        'DriverValueStore': DriverValueStore,
        'create_calculation': create_calculation,
        'create_default_fuel_model': create_default_fuel_model,
        'ALL_DRIVERS': ALL_DRIVERS,
        'COAL_PRICE_DRIVERS': COAL_PRICE_DRIVERS,
        'TRANSPORTATION_DRIVERS': TRANSPORTATION_DRIVERS,
        'HEAT_RATE_DRIVERS': HEAT_RATE_DRIVERS,
        'GENERATION_DRIVERS': GENERATION_DRIVERS,
        'INVENTORY_DRIVERS': INVENTORY_DRIVERS,
        'ESCALATION_DRIVERS': ESCALATION_DRIVERS,
    }


# Make driver framework available at module level
def __getattr__(name):
    """Lazy loading of driver framework exports."""
    exports = _get_driver_exports()
    if name in exports:
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
