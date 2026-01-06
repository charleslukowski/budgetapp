"""Test Clifty Creek cost calculations."""

from src.engine.fuel_model import FuelModelInputs, calculate_annual_fuel_costs, summarize_annual_fuel_costs
from src.engine.generation import create_clifty_params
from src.db.postgres import get_session

print("Annual Fuel Cost Summary - Clifty Creek 2025")
print("=" * 70)

inputs = FuelModelInputs(plant_params=create_clifty_params())

with get_session() as db:
    results = calculate_annual_fuel_costs(db, 2, 2025, inputs)
    summary = summarize_annual_fuel_costs(results)

# Print January details
r = results[0]  # January
print(f"\nClifty Creek - January 2025")
print("-" * 40)
print(f"Net Delivered MWh: {float(r.net_delivered_mwh):,.0f}")
print(f"Hydrated Lime Cost: ${float(r.hydrated_lime_cost):,.0f}")
print(f"Bioreactor Cost: ${float(r.bioreactor_cost):,.0f}")
print(f"WWTP Reagent Cost: ${float(r.wwtp_reagent_cost):,.0f}")
print(f"Misc Reagent Cost: ${float(r.misc_reagent_cost):,.0f}")
print(f"Fuel Oil Cost: ${float(r.fuel_oil_cost):,.0f}")
print(f"Labor & Handling: ${float(r.labor_handling_cost):,.0f}")
print(f"Allowance Cost: ${float(r.allowance_cost):,.0f}")
print(f"CO2 Tax: ${float(r.co2_tax):,.0f}")

print(f"\n\nAnnual Summary:")
print("-" * 40)
print(f"Total Bioreactor:       ${summary['total_bioreactor_cost']:>12,.0f}")
print(f"Total WWTP:             ${summary['total_wwtp_reagent_cost']:>12,.0f}")
print(f"Total Fuel Oil:         ${summary['total_fuel_oil_cost']:>12,.0f}")
print(f"Total Labor/Handling:   ${summary['total_labor_handling_cost']:>12,.0f}")
print(f"Total Allowance:        ${summary['total_allowance_cost']:>12,.0f}")

