"""Quick test of the new other fuel cost calculations."""

from src.engine.fuel_model import FuelModelInputs, calculate_fuel_costs
from src.engine.generation import create_kyger_params, create_clifty_params
from src.db.postgres import get_session

print("Testing Other Fuel Cost Calculations")
print("=" * 50)

# Test with default parameters
inputs = FuelModelInputs(plant_params=create_kyger_params())

with get_session() as db:
    result = calculate_fuel_costs(db, 1, 2025, 1, inputs)
    
    print(f"\nKyger Creek - January 2025")
    print("-" * 30)
    print(f"Net Delivered MWh: {float(result.net_delivered_mwh):,.0f}")
    print(f"Coal Cost: ${float(result.coal_cost):,.0f}")
    print(f"Urea Cost: ${float(result.urea_cost):,.0f}")
    print(f"Limestone Cost: ${float(result.limestone_cost):,.0f}")
    print(f"Hydrated Lime Cost: ${float(result.hydrated_lime_cost):,.0f}")
    print(f"Bioreactor Cost: ${float(result.bioreactor_cost):,.0f}")
    print(f"WWTP Reagent Cost: ${float(result.wwtp_reagent_cost):,.0f}")
    print(f"Misc Reagent Cost: ${float(result.misc_reagent_cost):,.0f}")
    print(f"Fuel Oil Cost: ${float(result.fuel_oil_cost):,.0f}")
    print(f"Labor & Handling Cost: ${float(result.labor_handling_cost):,.0f}")
    print(f"Temp Coal Storage Cost: ${float(result.temp_coal_storage_cost):,.0f}")
    print(f"NOx Allowance Cost: ${float(result.allowance_cost):,.0f}")
    print(f"CO2 Tax: ${float(result.co2_tax):,.0f}")
    print(f"Byproduct Net: ${float(result.byproduct_net_cost):,.0f}")
    print(f"TOTAL FUEL COST: ${float(result.total_fuel_cost):,.0f}")
    print(f"Cost per MWh: ${float(result.fuel_cost_per_mwh):.2f}")

print("\n" + "=" * 50)
print("Test Complete!")

