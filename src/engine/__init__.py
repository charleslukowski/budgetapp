# Forecast calculation engine

from src.engine.generation import (
    GenerationResult,
    PlantParams,
    UnitParams,
    calculate_generation,
    calculate_annual_generation,
    get_system_generation,
    create_kyger_params,
    create_clifty_params,
)

from src.engine.coal_burn import (
    CoalBurnResult,
    CoalQuality,
    HeatRateParams,
    calculate_coal_burn,
    calculate_annual_coal_burn,
    create_napp_coal,
    create_ilb_coal,
    create_prb_coal,
)

from src.engine.consumables import (
    ConsumablesResult,
    UreaParams,
    LimestoneParams,
    calculate_all_consumables,
)

from src.engine.byproducts import (
    ByproductsResult,
    AshParams,
    GypsumParams,
    calculate_all_byproducts,
)

from src.engine.fuel_model import (
    FuelCostSummary,
    FuelModelInputs,
    calculate_fuel_costs,
    calculate_annual_fuel_costs,
    calculate_system_fuel_costs,
)

__all__ = [
    # Generation
    "GenerationResult",
    "PlantParams",
    "UnitParams",
    "calculate_generation",
    "calculate_annual_generation",
    "get_system_generation",
    "create_kyger_params",
    "create_clifty_params",
    # Coal burn
    "CoalBurnResult",
    "CoalQuality",
    "HeatRateParams",
    "calculate_coal_burn",
    "calculate_annual_coal_burn",
    "create_napp_coal",
    "create_ilb_coal",
    "create_prb_coal",
    # Consumables
    "ConsumablesResult",
    "UreaParams",
    "LimestoneParams",
    "calculate_all_consumables",
    # Byproducts
    "ByproductsResult",
    "AshParams",
    "GypsumParams",
    "calculate_all_byproducts",
    # Fuel model
    "FuelCostSummary",
    "FuelModelInputs",
    "calculate_fuel_costs",
    "calculate_annual_fuel_costs",
    "calculate_system_fuel_costs",
]
