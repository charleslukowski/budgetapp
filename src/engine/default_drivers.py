"""Default OVEC driver definitions.

Defines all core drivers for the OVEC fuel cost forecasting model:
- Coal prices (Eastern, ILB, PRB)
- Transportation rates
- Heat rate parameters
- Generation and use factors
- Inventory management
- Escalation factors
"""

from decimal import Decimal
from typing import Dict, Optional

from src.engine.drivers import (
    Driver,
    DriverType,
    DriverCategory,
    FuelModel,
    create_calculation,
)


# =============================================================================
# Coal Price Drivers (6 drivers)
# DEPRECATED: Coal pricing is now stored in coal_contract_pricing and 
# uncommitted_coal_prices tables. These drivers are kept for backward 
# compatibility. New code should use load_inputs_from_db() from src.engine.fuel_model.
# =============================================================================

def _calc_coal_price_blended(model: FuelModel, year: int, month: int, plant_id: Optional[int] = None) -> Decimal:
    """Calculate blended coal price based on regional prices and blend percentages.
    
    DEPRECATED: Use coal_contract_pricing / uncommitted_coal_prices tables instead.
    """
    eastern_price = model.get_driver_value("coal_price_eastern", year, month, plant_id)
    ilb_price = model.get_driver_value("coal_price_ilb", year, month, plant_id)
    prb_price = model.get_driver_value("coal_price_prb", year, month, plant_id)
    
    eastern_pct = model.get_driver_value("coal_blend_eastern_pct", year, month, plant_id) / Decimal("100")
    ilb_pct = model.get_driver_value("coal_blend_ilb_pct", year, month, plant_id) / Decimal("100")
    prb_pct = model.get_driver_value("coal_blend_prb_pct", year, month, plant_id) / Decimal("100")
    
    # Normalize percentages to sum to 1
    total_pct = eastern_pct + ilb_pct + prb_pct
    if total_pct > 0:
        return (eastern_price * eastern_pct + ilb_price * ilb_pct + prb_price * prb_pct) / total_pct
    return eastern_price  # Default to eastern if no blend specified


def _calc_coal_mmbtu_eastern(model: FuelModel, year: int, month: int, plant_id: Optional[int] = None) -> Decimal:
    """Calculate $/MMBtu for Eastern coal.
    
    DEPRECATED: Use coal_contract_pricing tables instead.
    """
    price_per_ton = model.get_driver_value("coal_price_eastern", year, month, plant_id)
    btu_per_lb = model.get_driver_value("coal_btu_eastern", year, month, plant_id)
    # Convert: $/ton / (BTU/lb * 2000 lb/ton / 1,000,000) = $/MMBtu
    mmbtu_per_ton = btu_per_lb * Decimal("2000") / Decimal("1000000")
    if mmbtu_per_ton > 0:
        return price_per_ton / mmbtu_per_ton
    return Decimal("0")


def _calc_coal_mmbtu_ilb(model: FuelModel, year: int, month: int, plant_id: Optional[int] = None) -> Decimal:
    """Calculate $/MMBtu for Illinois Basin coal.
    
    DEPRECATED: Use coal_contract_pricing tables instead.
    """
    price_per_ton = model.get_driver_value("coal_price_ilb", year, month, plant_id)
    btu_per_lb = model.get_driver_value("coal_btu_ilb", year, month, plant_id)
    mmbtu_per_ton = btu_per_lb * Decimal("2000") / Decimal("1000000")
    if mmbtu_per_ton > 0:
        return price_per_ton / mmbtu_per_ton
    return Decimal("0")


# DEPRECATED: Use coal_contract_pricing / uncommitted_coal_prices tables instead
COAL_PRICE_DRIVERS = [
    Driver(
        name="coal_price_eastern",
        driver_type=DriverType.PRICE_INDEX,
        unit="$/ton",
        default_value=Decimal("55.00"),
        category=DriverCategory.COAL_PRICE,
        description="[DEPRECATED] Use coal_contract_pricing table instead",
        display_order=1,
        min_value=Decimal("0"),
        max_value=Decimal("200"),
        step=Decimal("0.50"),
    ),
    Driver(
        name="coal_price_ilb",
        driver_type=DriverType.PRICE_INDEX,
        unit="$/ton",
        default_value=Decimal("45.00"),
        category=DriverCategory.COAL_PRICE,
        description="[DEPRECATED] Use coal_contract_pricing table instead",
        display_order=2,
        min_value=Decimal("0"),
        max_value=Decimal("200"),
        step=Decimal("0.50"),
    ),
    Driver(
        name="coal_price_prb",
        driver_type=DriverType.PRICE_INDEX,
        unit="$/ton",
        default_value=Decimal("15.00"),
        category=DriverCategory.COAL_PRICE,
        description="[DEPRECATED] Use coal_contract_pricing table instead",
        display_order=3,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        step=Decimal("0.25"),
    ),
    Driver(
        name="coal_btu_eastern",
        driver_type=DriverType.RATE,
        unit="BTU/lb",
        default_value=Decimal("12600"),
        category=DriverCategory.COAL_PRICE,
        description="Heat content for Eastern coal (keep for quality specs)",
        display_order=4,
        min_value=Decimal("10000"),
        max_value=Decimal("15000"),
        step=Decimal("50"),
    ),
    Driver(
        name="coal_btu_ilb",
        driver_type=DriverType.RATE,
        unit="BTU/lb",
        default_value=Decimal("11400"),
        category=DriverCategory.COAL_PRICE,
        description="Heat content for Illinois Basin coal (keep for quality specs)",
        display_order=5,
        min_value=Decimal("10000"),
        max_value=Decimal("13000"),
        step=Decimal("50"),
    ),
    Driver(
        name="coal_blend_eastern_pct",
        driver_type=DriverType.PERCENTAGE,
        unit="%",
        default_value=Decimal("100"),
        category=DriverCategory.COAL_PRICE,
        description="Percentage of Eastern coal in blend",
        display_order=6,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        step=Decimal("5"),
    ),
    Driver(
        name="coal_blend_ilb_pct",
        driver_type=DriverType.PERCENTAGE,
        unit="%",
        default_value=Decimal("0"),
        category=DriverCategory.COAL_PRICE,
        description="Percentage of Illinois Basin coal in blend",
        display_order=7,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        step=Decimal("5"),
    ),
    Driver(
        name="coal_blend_prb_pct",
        driver_type=DriverType.PERCENTAGE,
        unit="%",
        default_value=Decimal("0"),
        category=DriverCategory.COAL_PRICE,
        description="Percentage of PRB coal in blend",
        display_order=8,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        step=Decimal("5"),
    ),
    Driver(
        name="coal_price_blended",
        driver_type=DriverType.CALCULATED,
        unit="$/ton",
        default_value=Decimal("55.00"),
        category=DriverCategory.COAL_PRICE,
        description="Weighted average coal price based on blend",
        display_order=9,
        depends_on=["coal_price_eastern", "coal_price_ilb", "coal_price_prb", 
                    "coal_blend_eastern_pct", "coal_blend_ilb_pct", "coal_blend_prb_pct"],
        calculation=_calc_coal_price_blended,
    ),
    Driver(
        name="coal_mmbtu_eastern",
        driver_type=DriverType.CALCULATED,
        unit="$/MMBtu",
        default_value=Decimal("2.20"),
        category=DriverCategory.COAL_PRICE,
        description="Eastern coal cost per MMBtu",
        display_order=10,
        depends_on=["coal_price_eastern", "coal_btu_eastern"],
        calculation=_calc_coal_mmbtu_eastern,
    ),
    Driver(
        name="coal_mmbtu_ilb",
        driver_type=DriverType.CALCULATED,
        unit="$/MMBtu",
        default_value=Decimal("1.97"),
        category=DriverCategory.COAL_PRICE,
        description="Illinois Basin coal cost per MMBtu",
        display_order=11,
        depends_on=["coal_price_ilb", "coal_btu_ilb"],
        calculation=_calc_coal_mmbtu_ilb,
    ),
]


# =============================================================================
# Transportation Drivers (4 drivers)
# =============================================================================

def _calc_delivered_cost(model: FuelModel, year: int, month: int, plant_id: Optional[int] = None) -> Decimal:
    """Calculate total delivered coal cost (coal + barge)."""
    coal_price = model.get_driver_value("coal_price_blended", year, month, plant_id)
    barge_rate = model.get_driver_value("barge_rate_ohio", year, month, plant_id)
    return coal_price + barge_rate


TRANSPORTATION_DRIVERS = [
    Driver(
        name="barge_rate_ohio",
        driver_type=DriverType.RATE,
        unit="$/ton",
        default_value=Decimal("6.00"),
        category=DriverCategory.TRANSPORTATION,
        description="Ohio River barge transportation rate",
        display_order=1,
        min_value=Decimal("0"),
        max_value=Decimal("20"),
        step=Decimal("0.25"),
    ),
    Driver(
        name="barge_rate_upper_ohio",
        driver_type=DriverType.RATE,
        unit="$/ton",
        default_value=Decimal("7.50"),
        category=DriverCategory.TRANSPORTATION,
        description="Upper Ohio River barge transportation rate",
        display_order=2,
        min_value=Decimal("0"),
        max_value=Decimal("25"),
        step=Decimal("0.25"),
    ),
    Driver(
        name="rail_rate_prb",
        driver_type=DriverType.RATE,
        unit="$/ton",
        default_value=Decimal("30.00"),
        category=DriverCategory.TRANSPORTATION,
        description="Rail transportation rate for PRB coal",
        display_order=3,
        min_value=Decimal("0"),
        max_value=Decimal("60"),
        step=Decimal("1.00"),
    ),
    Driver(
        name="delivered_cost",
        driver_type=DriverType.CALCULATED,
        unit="$/ton",
        default_value=Decimal("61.00"),
        category=DriverCategory.TRANSPORTATION,
        description="Total delivered coal cost (coal + transport)",
        display_order=4,
        depends_on=["coal_price_blended", "barge_rate_ohio"],
        calculation=_calc_delivered_cost,
    ),
]


# =============================================================================
# Heat Rate Drivers (6 drivers)
# DEPRECATED: Heat rates are now stored in heat_rate_inputs table.
# These drivers are kept for backward compatibility with older code.
# New code should use load_inputs_from_db() from src.engine.fuel_model.
# =============================================================================

def _calc_heat_rate_effective(model: FuelModel, year: int, month: int, plant_id: Optional[int] = None) -> Decimal:
    """Calculate effective heat rate with all adjustments.
    
    DEPRECATED: Use heat_rate_inputs table instead.
    """
    baseline = model.get_driver_value("heat_rate_baseline", year, month, plant_id)
    suf_correction = model.get_driver_value("heat_rate_suf_correction", year, month, plant_id)
    prb_pct = model.get_driver_value("coal_blend_prb_pct", year, month, plant_id) / Decimal("100")
    prb_penalty = model.get_driver_value("heat_rate_prb_penalty", year, month, plant_id)
    
    return baseline + suf_correction + (prb_pct * prb_penalty)


# DEPRECATED: Use heat_rate_inputs table instead
HEAT_RATE_DRIVERS = [
    Driver(
        name="heat_rate_baseline",
        driver_type=DriverType.RATE,
        unit="BTU/kWh",
        default_value=Decimal("9850"),
        category=DriverCategory.HEAT_RATE,
        description="[DEPRECATED] Baseline heat rate - use heat_rate_inputs table",
        display_order=1,
        min_value=Decimal("8500"),
        max_value=Decimal("12000"),
        step=Decimal("10"),
        is_plant_specific=True,
    ),
    Driver(
        name="heat_rate_baseline_kc",
        driver_type=DriverType.RATE,
        unit="BTU/kWh",
        default_value=Decimal("9850"),
        category=DriverCategory.HEAT_RATE,
        description="[DEPRECATED] Kyger Creek baseline - use heat_rate_inputs table",
        display_order=2,
        min_value=Decimal("8500"),
        max_value=Decimal("12000"),
        step=Decimal("10"),
    ),
    Driver(
        name="heat_rate_baseline_cc",
        driver_type=DriverType.RATE,
        unit="BTU/kWh",
        default_value=Decimal("9900"),
        category=DriverCategory.HEAT_RATE,
        description="[DEPRECATED] Clifty Creek baseline - use heat_rate_inputs table",
        display_order=3,
        min_value=Decimal("8500"),
        max_value=Decimal("12000"),
        step=Decimal("10"),
    ),
    Driver(
        name="heat_rate_suf_correction",
        driver_type=DriverType.RATE,
        unit="BTU/kWh",
        default_value=Decimal("0"),
        category=DriverCategory.HEAT_RATE,
        description="[DEPRECATED] SUF correction - use heat_rate_inputs table",
        display_order=4,
        min_value=Decimal("-500"),
        max_value=Decimal("500"),
        step=Decimal("10"),
    ),
    Driver(
        name="heat_rate_prb_penalty",
        driver_type=DriverType.RATE,
        unit="BTU/kWh per %PRB",
        default_value=Decimal("100"),
        category=DriverCategory.HEAT_RATE,
        description="[DEPRECATED] PRB penalty - use heat_rate_inputs table",
        display_order=5,
        min_value=Decimal("0"),
        max_value=Decimal("300"),
        step=Decimal("10"),
    ),
    Driver(
        name="heat_rate_effective",
        driver_type=DriverType.CALCULATED,
        unit="BTU/kWh",
        default_value=Decimal("9850"),
        category=DriverCategory.HEAT_RATE,
        description="[DEPRECATED] Effective heat rate - use load_inputs_from_db()",
        display_order=6,
        depends_on=["heat_rate_baseline", "heat_rate_suf_correction", 
                    "coal_blend_prb_pct", "heat_rate_prb_penalty"],
        calculation=_calc_heat_rate_effective,
    ),
]


# =============================================================================
# Generation Drivers (8 drivers)
# =============================================================================

def _calc_generation_mwh(model: FuelModel, year: int, month: int, plant_id: Optional[int] = None) -> Decimal:
    """Calculate gross generation MWh."""
    from calendar import monthrange
    
    capacity_mw = model.get_driver_value("capacity_mw", year, month, plant_id)
    use_factor = model.get_driver_value("use_factor", year, month, plant_id) / Decimal("100")
    
    # Hours in month
    days = monthrange(year, month)[1]
    hours = days * 24
    
    return capacity_mw * Decimal(str(hours)) * use_factor


def _calc_net_delivered_mwh(model: FuelModel, year: int, month: int, plant_id: Optional[int] = None) -> Decimal:
    """Calculate net delivered MWh after losses."""
    from calendar import monthrange
    
    generation = model.get_driver_value("generation_mwh", year, month, plant_id)
    
    # Deductions
    fgd_aux_pct = model.get_driver_value("fgd_aux_pct", year, month, plant_id) / Decimal("100")
    gsu_loss_pct = model.get_driver_value("gsu_loss_pct", year, month, plant_id) / Decimal("100")
    
    # Calculate hours for reserve
    days = monthrange(year, month)[1]
    hours = days * 24
    reserve_mw = model.get_driver_value("reserve_mw", year, month, plant_id)
    reserve_mwh = reserve_mw * Decimal(str(hours))
    
    net = generation * (Decimal("1") - fgd_aux_pct) * (Decimal("1") - gsu_loss_pct) - reserve_mwh
    return max(Decimal("0"), net)


# Note: use_factor and outage_days_* are DEPRECATED. Use the specialized input tables:
# - use_factor_inputs for monthly use factors
# - unit_outage_inputs for unit-level outage tracking
# These drivers are kept for backward compatibility only.
GENERATION_DRIVERS = [
    Driver(
        name="capacity_mw",
        driver_type=DriverType.VOLUME,
        unit="MW",
        default_value=Decimal("1025"),
        category=DriverCategory.GENERATION,
        description="Available plant capacity",
        display_order=1,
        min_value=Decimal("0"),
        max_value=Decimal("2000"),
        step=Decimal("5"),
        is_plant_specific=True,
    ),
    Driver(
        name="use_factor",
        driver_type=DriverType.PERCENTAGE,
        unit="%",
        default_value=Decimal("85"),
        category=DriverCategory.GENERATION,
        description="[DEPRECATED] Use use_factor_inputs table instead",
        display_order=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        step=Decimal("1"),
    ),
    Driver(
        name="capacity_factor_target",
        driver_type=DriverType.PERCENTAGE,
        unit="%",
        default_value=Decimal("70"),
        category=DriverCategory.GENERATION,
        description="Target capacity factor for planning",
        display_order=3,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        step=Decimal("1"),
    ),
    Driver(
        name="outage_days_planned",
        driver_type=DriverType.VOLUME,
        unit="days",
        default_value=Decimal("0"),
        category=DriverCategory.GENERATION,
        description="[DEPRECATED] Use unit_outage_inputs table instead",
        display_order=4,
        min_value=Decimal("0"),
        max_value=Decimal("31"),
        step=Decimal("1"),
    ),
    Driver(
        name="outage_days_forced",
        driver_type=DriverType.VOLUME,
        unit="days",
        default_value=Decimal("0"),
        category=DriverCategory.GENERATION,
        description="[DEPRECATED] Use unit_outage_inputs table instead",
        display_order=5,
        min_value=Decimal("0"),
        max_value=Decimal("31"),
        step=Decimal("1"),
    ),
    Driver(
        name="fgd_aux_pct",
        driver_type=DriverType.PERCENTAGE,
        unit="%",
        default_value=Decimal("2.5"),
        category=DriverCategory.GENERATION,
        description="FGD auxiliary load as % of generation",
        display_order=6,
        min_value=Decimal("0"),
        max_value=Decimal("10"),
        step=Decimal("0.1"),
    ),
    Driver(
        name="gsu_loss_pct",
        driver_type=DriverType.PERCENTAGE,
        unit="%",
        default_value=Decimal("0.5545"),
        category=DriverCategory.GENERATION,
        description="GSU transformer losses as % of generation",
        display_order=7,
        min_value=Decimal("0"),
        max_value=Decimal("2"),
        step=Decimal("0.01"),
    ),
    Driver(
        name="reserve_mw",
        driver_type=DriverType.VOLUME,
        unit="MW",
        default_value=Decimal("10"),
        category=DriverCategory.GENERATION,
        description="System regulating reserve",
        display_order=8,
        min_value=Decimal("0"),
        max_value=Decimal("50"),
        step=Decimal("1"),
    ),
    Driver(
        name="generation_mwh",
        driver_type=DriverType.CALCULATED,
        unit="MWh",
        default_value=Decimal("0"),
        category=DriverCategory.GENERATION,
        description="Gross generation MWh for the period",
        display_order=9,
        depends_on=["capacity_mw", "use_factor"],
        calculation=_calc_generation_mwh,
    ),
    Driver(
        name="net_delivered_mwh",
        driver_type=DriverType.CALCULATED,
        unit="MWh",
        default_value=Decimal("0"),
        category=DriverCategory.GENERATION,
        description="Net delivered MWh after losses",
        display_order=10,
        depends_on=["generation_mwh", "fgd_aux_pct", "gsu_loss_pct", "reserve_mw"],
        calculation=_calc_net_delivered_mwh,
    ),
]


# =============================================================================
# Inventory Drivers (4 drivers)
# =============================================================================

def _calc_inventory_ending(model: FuelModel, year: int, month: int, plant_id: Optional[int] = None) -> Decimal:
    """Calculate ending inventory based on deliveries and consumption."""
    beginning = model.get_driver_value("inventory_beginning_tons", year, month, plant_id)
    deliveries = model.get_driver_value("coal_deliveries_tons", year, month, plant_id)
    consumption = model.get_driver_value("coal_consumption_tons", year, month, plant_id)
    
    return beginning + deliveries - consumption


def _calc_uncommitted_needed(model: FuelModel, year: int, month: int, plant_id: Optional[int] = None) -> Decimal:
    """Calculate uncommitted coal needed to meet inventory target."""
    from calendar import monthrange
    
    target_days = model.get_driver_value("inventory_target_days", year, month, plant_id)
    consumption = model.get_driver_value("coal_consumption_tons", year, month, plant_id)
    beginning = model.get_driver_value("inventory_beginning_tons", year, month, plant_id)
    contracted = model.get_driver_value("contracted_deliveries_tons", year, month, plant_id)
    
    days = monthrange(year, month)[1]
    daily_consumption = consumption / Decimal(str(days)) if days > 0 else Decimal("0")
    target_inventory = target_days * daily_consumption
    
    # Expected inventory after contracted deliveries
    expected = beginning + contracted - consumption
    
    gap = target_inventory - expected
    return max(Decimal("0"), gap)


INVENTORY_DRIVERS = [
    Driver(
        name="inventory_target_days",
        driver_type=DriverType.VOLUME,
        unit="days",
        default_value=Decimal("50"),
        category=DriverCategory.INVENTORY,
        description="Target coal inventory in days of supply",
        display_order=1,
        min_value=Decimal("0"),
        max_value=Decimal("120"),
        step=Decimal("5"),
    ),
    Driver(
        name="inventory_beginning_tons",
        driver_type=DriverType.VOLUME,
        unit="tons",
        default_value=Decimal("150000"),
        category=DriverCategory.INVENTORY,
        description="Beginning coal inventory",
        display_order=2,
        min_value=Decimal("0"),
        step=Decimal("1000"),
        is_plant_specific=True,
    ),
    Driver(
        name="coal_deliveries_tons",
        driver_type=DriverType.VOLUME,
        unit="tons",
        default_value=Decimal("80000"),
        category=DriverCategory.INVENTORY,
        description="Total coal deliveries for the period",
        display_order=3,
        min_value=Decimal("0"),
        step=Decimal("1000"),
    ),
    Driver(
        name="contracted_deliveries_tons",
        driver_type=DriverType.VOLUME,
        unit="tons",
        default_value=Decimal("75000"),
        category=DriverCategory.INVENTORY,
        description="Contracted coal deliveries for the period",
        display_order=4,
        min_value=Decimal("0"),
        step=Decimal("1000"),
    ),
    Driver(
        name="coal_consumption_tons",
        driver_type=DriverType.VOLUME,
        unit="tons",
        default_value=Decimal("80000"),
        category=DriverCategory.INVENTORY,
        description="Coal consumption for the period",
        display_order=5,
        min_value=Decimal("0"),
        step=Decimal("1000"),
    ),
    Driver(
        name="inventory_ending_tons",
        driver_type=DriverType.CALCULATED,
        unit="tons",
        default_value=Decimal("150000"),
        category=DriverCategory.INVENTORY,
        description="Ending coal inventory",
        display_order=6,
        depends_on=["inventory_beginning_tons", "coal_deliveries_tons", "coal_consumption_tons"],
        calculation=_calc_inventory_ending,
    ),
    Driver(
        name="uncommitted_tons_needed",
        driver_type=DriverType.CALCULATED,
        unit="tons",
        default_value=Decimal("0"),
        category=DriverCategory.INVENTORY,
        description="Uncommitted coal needed to meet inventory target",
        display_order=7,
        depends_on=["inventory_target_days", "coal_consumption_tons", 
                    "inventory_beginning_tons", "contracted_deliveries_tons"],
        calculation=_calc_uncommitted_needed,
    ),
]


# =============================================================================
# Escalation Drivers (3 drivers)
# =============================================================================

ESCALATION_DRIVERS = [
    Driver(
        name="escalation_coal_annual",
        driver_type=DriverType.PERCENTAGE,
        unit="%",
        default_value=Decimal("2.0"),
        category=DriverCategory.ESCALATION,
        description="Annual coal price escalation rate",
        display_order=1,
        min_value=Decimal("-10"),
        max_value=Decimal("20"),
        step=Decimal("0.5"),
    ),
    Driver(
        name="escalation_transport_annual",
        driver_type=DriverType.PERCENTAGE,
        unit="%",
        default_value=Decimal("2.5"),
        category=DriverCategory.ESCALATION,
        description="Annual transportation cost escalation rate",
        display_order=2,
        min_value=Decimal("-10"),
        max_value=Decimal("20"),
        step=Decimal("0.5"),
    ),
    Driver(
        name="escalation_reagent_annual",
        driver_type=DriverType.PERCENTAGE,
        unit="%",
        default_value=Decimal("2.0"),
        category=DriverCategory.ESCALATION,
        description="Annual reagent/consumables cost escalation rate",
        display_order=3,
        min_value=Decimal("-10"),
        max_value=Decimal("20"),
        step=Decimal("0.5"),
    ),
]


# =============================================================================
# All Drivers Combined
# =============================================================================

ALL_DRIVERS = (
    COAL_PRICE_DRIVERS +
    TRANSPORTATION_DRIVERS +
    HEAT_RATE_DRIVERS +
    GENERATION_DRIVERS +
    INVENTORY_DRIVERS +
    ESCALATION_DRIVERS
)


def create_default_fuel_model() -> FuelModel:
    """Create a FuelModel instance with all OVEC default drivers.
    
    Returns:
        FuelModel configured with all default drivers
    """
    model = FuelModel()
    model.register_drivers(ALL_DRIVERS)
    return model


def get_driver_by_name(name: str) -> Driver:
    """Get a specific driver by name.
    
    Args:
        name: Driver name
        
    Returns:
        Driver instance
        
    Raises:
        ValueError: If driver not found
    """
    for driver in ALL_DRIVERS:
        if driver.name == name:
            return driver
    raise ValueError(f"Unknown driver: {name}")


def get_drivers_by_category(category: DriverCategory) -> list:
    """Get all drivers in a category.
    
    Args:
        category: Category to filter by
        
    Returns:
        List of drivers
    """
    return [d for d in ALL_DRIVERS if d.category == category]

