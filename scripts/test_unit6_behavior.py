"""Test script to verify Clifty Creek Unit 6 behavior.

This script tests:
1. Unit 6 generation = 0 during ozone months (May-Sep) due to lack of SCR
2. Unit 6 NOx uses uncontrolled emission rate (higher than SCR units)
3. Unit 6 urea = 0 (no SCR to consume urea)
4. Units 1-5 continue operating normally during ozone season
"""

import sys
import os
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine.generation import (
    create_clifty_params,
    create_kyger_params,
    calculate_generation,
    get_unit_use_factors_for_plant,
    UseFactorParams,
    is_ozone_season,
    OZONE_SEASON_MONTHS,
)
from src.engine.emissions import (
    calculate_unit_emissions,
    AllowanceParams,
)
from src.engine.consumables import (
    calculate_unit_urea,
    UreaParams,
)
from src.engine.fuel_model import (
    FuelModelInputs,
    calculate_fuel_costs,
)
from src.db.postgres import get_session


def test_clifty_unit6_scr_status():
    """Verify Unit 6 is correctly marked as non-SCR."""
    print("\n=== Test 1: Unit 6 SCR Status ===")
    clifty = create_clifty_params()
    
    for unit in clifty.units:
        print(f"  Unit {unit.unit_number}: has_scr={unit.has_scr}")
        if unit.unit_number == 6:
            assert not unit.has_scr, "Unit 6 should NOT have SCR"
        else:
            assert unit.has_scr, f"Unit {unit.unit_number} should have SCR"
    
    print("  [PASS] Unit 6 correctly marked as non-SCR, Units 1-5 have SCR")


def test_unit6_ozone_curtailment():
    """Verify Unit 6 is curtailed during ozone season."""
    print("\n=== Test 2: Unit 6 Ozone Season Curtailment ===")
    clifty = create_clifty_params()
    use_factor_params = UseFactorParams(
        base_use_factor=Decimal("0.85"),
        ozone_use_factor_non_scr=Decimal("0"),  # Unit 6 offline during ozone
    )
    
    for month in range(1, 13):
        # Get unit use factors
        unit_use_factors = {}
        for unit in clifty.units:
            unit_use_factors[unit.unit_number] = use_factor_params.get_use_factor(
                unit.unit_number, month, unit.has_scr
            )
        
        # Calculate generation with unit-specific use factors
        generation = calculate_generation(
            clifty, 2026, month,
            use_factor_params.base_use_factor,
            unit_use_factors=unit_use_factors,
        )
        
        unit6_result = generation.get_unit_result(6)
        unit1_result = generation.get_unit_result(1)
        
        is_ozone = is_ozone_season(month)
        month_name = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][month]
        
        print(f"  {month_name}: Ozone={is_ozone}")
        print(f"    Unit 1 (SCR): {float(unit1_result.net_mwh):,.0f} MWh, UF={float(unit1_result.use_factor):.2f}")
        print(f"    Unit 6 (no SCR): {float(unit6_result.net_mwh):,.0f} MWh, UF={float(unit6_result.use_factor):.2f}, curtailed={unit6_result.is_curtailed}")
        
        if is_ozone:
            assert unit6_result.use_factor == Decimal("0"), f"Unit 6 should have UF=0 during ozone (month {month})"
            assert unit6_result.net_mwh == Decimal("0"), f"Unit 6 should have 0 MWh during ozone (month {month})"
        else:
            assert unit6_result.use_factor == Decimal("0.85"), f"Unit 6 should have UF=0.85 outside ozone (month {month})"
            assert unit6_result.net_mwh > 0, f"Unit 6 should generate during non-ozone (month {month})"
    
    print("  [PASS] Unit 6 correctly curtailed during ozone season (May-Sep)")


def test_unit6_nox_emissions():
    """Verify Unit 6 uses uncontrolled NOx emission rate."""
    print("\n=== Test 3: Unit 6 NOx Emission Rate ===")
    
    mmbtu = Decimal("100000")  # 100,000 MMBtu
    params = AllowanceParams()
    
    # Unit with SCR
    scr_emissions = calculate_unit_emissions(
        unit_number=1,
        has_scr=True,
        mmbtu_consumed=mmbtu,
        year=2026,
        month=6,
        params=params,
    )
    
    # Unit without SCR
    no_scr_emissions = calculate_unit_emissions(
        unit_number=6,
        has_scr=False,
        mmbtu_consumed=mmbtu,
        year=2026,
        month=6,
        params=params,
    )
    
    print(f"  SCR Unit (Unit 1):")
    print(f"    NOx uncontrolled: {float(scr_emissions.nox_uncontrolled_lbs):,.0f} lbs")
    print(f"    NOx removed by SCR: {float(scr_emissions.nox_removed_lbs):,.0f} lbs")
    print(f"    NOx emitted: {float(scr_emissions.nox_emitted_lbs):,.0f} lbs ({float(scr_emissions.nox_tons):.1f} tons)")
    
    print(f"  Non-SCR Unit (Unit 6):")
    print(f"    NOx uncontrolled: {float(no_scr_emissions.nox_uncontrolled_lbs):,.0f} lbs")
    print(f"    NOx removed: {float(no_scr_emissions.nox_removed_lbs):,.0f} lbs")
    print(f"    NOx emitted: {float(no_scr_emissions.nox_emitted_lbs):,.0f} lbs ({float(no_scr_emissions.nox_tons):.1f} tons)")
    
    # Unit 6 should emit 10x more NOx (90% removal efficiency for SCR)
    ratio = no_scr_emissions.nox_emitted_lbs / scr_emissions.nox_emitted_lbs
    print(f"  Emission ratio (no-SCR/SCR): {float(ratio):.1f}x")
    
    assert no_scr_emissions.nox_removed_lbs == 0, "Non-SCR unit should have 0 NOx removed"
    assert ratio >= 9, "Non-SCR should emit ~10x more NOx than SCR"
    
    print("  [PASS] Unit 6 correctly uses uncontrolled emission rate")


def test_unit6_urea_consumption():
    """Verify Unit 6 consumes no urea (no SCR)."""
    print("\n=== Test 4: Unit 6 Urea Consumption ===")
    
    mmbtu = Decimal("100000")
    urea_params = UreaParams()
    
    # SCR unit urea
    scr_urea = calculate_unit_urea(
        mmbtu=mmbtu,
        has_scr=True,
        params=urea_params,
    )
    
    # Non-SCR unit urea
    no_scr_urea = calculate_unit_urea(
        mmbtu=mmbtu,
        has_scr=False,
        params=urea_params,
    )
    
    print(f"  SCR Unit (Unit 1):")
    print(f"    Urea: {float(scr_urea['tons']):.1f} tons, ${float(scr_urea['cost']):,.0f}")
    
    print(f"  Non-SCR Unit (Unit 6):")
    print(f"    Urea: {float(no_scr_urea['tons']):.1f} tons, ${float(no_scr_urea['cost']):,.0f}")
    
    assert no_scr_urea['tons'] == Decimal("0"), "Non-SCR unit should use 0 urea"
    assert no_scr_urea['cost'] == Decimal("0"), "Non-SCR unit should have $0 urea cost"
    assert scr_urea['tons'] > 0, "SCR unit should use urea"
    
    print("  [PASS] Unit 6 correctly uses no urea")


def test_integrated_fuel_costs():
    """Test integrated fuel cost calculation with unit-level breakdown."""
    print("\n=== Test 5: Integrated Fuel Costs ===")
    
    clifty = create_clifty_params()
    inputs = FuelModelInputs(
        plant_params=clifty,
        use_unit_level_calc=True,
        use_factor_params=UseFactorParams(
            base_use_factor=Decimal("0.85"),
            ozone_use_factor_non_scr=Decimal("0"),
        ),
    )
    
    with get_session() as db:
        # Test ozone month (June)
        print("\n  June (Ozone Season):")
        june_costs = calculate_fuel_costs(db, 2, 2026, 6, inputs)
        
        print(f"    Plant net MWh: {float(june_costs.net_delivered_mwh):,.0f}")
        print(f"    Unit-level generation:")
        for unit_num in sorted(june_costs.unit_generation.keys()):
            gen = june_costs.unit_generation[unit_num]
            curtailed = june_costs.unit_curtailed.get(unit_num, False)
            urea = june_costs.unit_urea_cost.get(unit_num, Decimal("0"))
            nox = june_costs.unit_nox_tons.get(unit_num, Decimal("0"))
            print(f"      Unit {unit_num}: {float(gen):,.0f} MWh, curtailed={curtailed}, urea=${float(urea):,.0f}, NOx={float(nox):.1f}t")
        
        # Verify Unit 6 is curtailed in June
        assert june_costs.unit_generation.get(6, Decimal("1")) == Decimal("0"), "Unit 6 should have 0 MWh in June"
        assert june_costs.unit_curtailed.get(6, False), "Unit 6 should be curtailed in June"
        
        # Test non-ozone month (January)
        print("\n  January (Non-Ozone Season):")
        jan_costs = calculate_fuel_costs(db, 2, 2026, 1, inputs)
        
        print(f"    Plant net MWh: {float(jan_costs.net_delivered_mwh):,.0f}")
        print(f"    Unit-level generation:")
        for unit_num in sorted(jan_costs.unit_generation.keys()):
            gen = jan_costs.unit_generation[unit_num]
            curtailed = jan_costs.unit_curtailed.get(unit_num, False)
            urea = jan_costs.unit_urea_cost.get(unit_num, Decimal("0"))
            nox = jan_costs.unit_nox_tons.get(unit_num, Decimal("0"))
            print(f"      Unit {unit_num}: {float(gen):,.0f} MWh, curtailed={curtailed}, urea=${float(urea):,.0f}, NOx={float(nox):.1f}t")
        
        # Verify Unit 6 generates in January
        assert jan_costs.unit_generation.get(6, Decimal("0")) > 0, "Unit 6 should generate in January"
        assert not jan_costs.unit_curtailed.get(6, True), "Unit 6 should NOT be curtailed in January"
    
    print("  [PASS] Integrated fuel costs correctly handle Unit 6")


def test_annual_summary():
    """Test annual summary with Unit 6 behavior."""
    print("\n=== Test 6: Annual Summary ===")
    
    clifty = create_clifty_params()
    inputs = FuelModelInputs(
        plant_params=clifty,
        use_unit_level_calc=True,
        use_factor_params=UseFactorParams(
            base_use_factor=Decimal("0.85"),
            ozone_use_factor_non_scr=Decimal("0"),
        ),
    )
    
    from src.engine.fuel_model import calculate_annual_fuel_costs, summarize_annual_fuel_costs
    
    with get_session() as db:
        monthly_costs = calculate_annual_fuel_costs(db, 2, 2026, inputs)
        annual = summarize_annual_fuel_costs(monthly_costs)
        
        print(f"  Annual MWh: {annual['total_mwh']:,.0f}")
        print(f"  Annual Coal Cost: ${annual['total_coal_cost']:,.0f}")
        print(f"  Annual Urea Cost: ${annual['total_urea_cost']:,.0f}")
        print(f"  Annual Allowance Cost: ${annual['total_allowance_cost']:,.0f}")
        print(f"  Annual Total Fuel Cost: ${annual['total_fuel_cost']:,.0f}")
        print(f"  Avg $/MWh: ${annual['avg_fuel_cost_per_mwh']:.2f}")
        
        # Count ozone months vs non-ozone months Unit 6 curtailed
        ozone_months_curtailed = sum(
            1 for m in monthly_costs 
            if m.unit_curtailed.get(6, False) and is_ozone_season(m.period_month)
        )
        print(f"  Unit 6 curtailed during {ozone_months_curtailed} ozone months")
        assert ozone_months_curtailed == 5, "Unit 6 should be curtailed in all 5 ozone months"
    
    print("  [PASS] Annual summary correctly accounts for Unit 6 curtailment")


def main():
    """Run all tests."""
    print("=" * 60)
    print("CLIFTY CREEK UNIT 6 BEHAVIOR TESTS")
    print("=" * 60)
    print(f"Ozone season months: {sorted(OZONE_SEASON_MONTHS)}")
    
    try:
        test_clifty_unit6_scr_status()
        test_unit6_ozone_curtailment()
        test_unit6_nox_emissions()
        test_unit6_urea_consumption()
        test_integrated_fuel_costs()
        test_annual_summary()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

