"""Test all cost calculations for a full year to see ozone season impact."""

from src.engine.fuel_model import FuelModelInputs, calculate_annual_fuel_costs, summarize_annual_fuel_costs
from src.engine.generation import create_kyger_params
from src.db.postgres import get_session

print("Annual Fuel Cost Summary - Kyger Creek 2025")
print("=" * 70)

inputs = FuelModelInputs(plant_params=create_kyger_params())

with get_session() as db:
    results = calculate_annual_fuel_costs(db, 1, 2025, inputs)
    summary = summarize_annual_fuel_costs(results)

# Print monthly details
print(f"\n{'Month':<10} {'MWh':>12} {'Coal':>12} {'Allow':>10} {'Other':>10} {'Total':>12}")
print("-" * 70)

for r in results:
    month_name = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][r.period_month - 1]
    print(f"{month_name:<10} {float(r.net_delivered_mwh):>12,.0f} ${float(r.coal_cost):>10,.0f} ${float(r.allowance_cost):>8,.0f} ${float(r.bioreactor_cost + r.fuel_oil_cost + r.labor_handling_cost):>8,.0f} ${float(r.total_fuel_cost):>10,.0f}")

print("-" * 70)
print(f"{'ANNUAL':<10} {summary['total_mwh']:>12,.0f} ${summary['total_coal_cost']:>10,.0f} ${summary['total_allowance_cost']:>8,.0f}                ${summary['total_fuel_cost']:>10,.0f}")

print(f"\n\nCost Category Breakdown:")
print("-" * 40)
print(f"Coal Cost:              ${summary['total_coal_cost']:>12,.0f}")
print(f"Urea:                   ${summary['total_urea_cost']:>12,.0f}")
print(f"Limestone:              ${summary['total_limestone_cost']:>12,.0f}")
print(f"Hydrated Lime:          ${summary['total_hydrated_lime_cost']:>12,.0f}")
print(f"Bioreactor:             ${summary['total_bioreactor_cost']:>12,.0f}")
print(f"WWTP Reagent:           ${summary['total_wwtp_reagent_cost']:>12,.0f}")
print(f"Misc Reagent:           ${summary['total_misc_reagent_cost']:>12,.0f}")
print(f"Fuel Oil:               ${summary['total_fuel_oil_cost']:>12,.0f}")
print(f"Labor & Handling:       ${summary['total_labor_handling_cost']:>12,.0f}")
print(f"Temp Coal Storage:      ${summary['total_temp_coal_storage_cost']:>12,.0f}")
print(f"NOx Allowance:          ${summary['total_allowance_cost']:>12,.0f}")
print(f"CO2 Tax:                ${summary['total_co2_tax']:>12,.0f}")
print(f"Byproduct Net:          ${summary['total_byproduct_net']:>12,.0f}")
print("-" * 40)
print(f"TOTAL FUEL COST:        ${summary['total_fuel_cost']:>12,.0f}")
print(f"Avg $/MWh:              ${summary['avg_fuel_cost_per_mwh']:>12.2f}")

