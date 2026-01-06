"""
Test script for database-driven fuel cost calculations.

Verifies that the fuel model correctly:
1. Loads use factors from the database
2. Loads heat rates from the database
3. Uses contract pricing for coal costs

Usage:
    python scripts/test_db_driven_calcs.py
"""

import sys
import os
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def print_result(test_name: str, passed: bool, message: str = ""):
    """Print test result."""
    status = "[PASS]" if passed else "[FAIL]"
    print(f"  {status} {test_name}")
    if message:
        print(f"         {message}")


def setup_test_data(db):
    """Set up test data in the database."""
    from src.models.use_factor import upsert_use_factor
    from src.models.heat_rate import upsert_heat_rate
    
    # Insert test use factors for Kyger Creek (plant_id=1)
    for month in range(1, 13):
        base_uf = 0.82 + (month / 100)  # Varies slightly by month
        ozone_uf = 0.0 if month in {5, 6, 7, 8, 9} else base_uf
        
        upsert_use_factor(
            db,
            plant_id=1,
            year=2025,
            month=month,
            use_factor_base=base_uf,
            use_factor_ozone_non_scr=ozone_uf,
        )
    
    # Insert test heat rates for Kyger Creek
    for month in range(1, 13):
        baseline_hr = 9800 + (month * 10)  # Varies by month
        
        upsert_heat_rate(
            db,
            plant_id=1,
            year=2025,
            month=month,
            baseline_heat_rate=baseline_hr,
            suf_correction=50,
            prb_blend_adjustment=0,
        )
    
    print("  Test data inserted for plant 1 (Kyger Creek)")
    return True


def cleanup_test_data(db):
    """Remove test data."""
    from src.models.use_factor import UseFactorInput
    from src.models.heat_rate import HeatRateInput
    
    # Delete test data for 2025
    db.query(UseFactorInput).filter(
        UseFactorInput.plant_id == 1,
        UseFactorInput.year == 2025
    ).delete()
    
    db.query(HeatRateInput).filter(
        HeatRateInput.plant_id == 1,
        HeatRateInput.year == 2025
    ).delete()
    
    db.commit()
    print("  Test data cleaned up")


def test_load_inputs_from_db():
    """Test that load_inputs_from_db correctly loads from database."""
    print("\n" + "=" * 60)
    print("Testing load_inputs_from_db()")
    print("=" * 60)
    
    from src.db.postgres import get_session
    from src.engine.fuel_model import load_inputs_from_db
    
    passed = 0
    failed = 0
    
    with get_session() as db:
        # Setup
        setup_test_data(db)
        
        try:
            # Test 1: Load inputs for June (ozone season)
            inputs = load_inputs_from_db(db, plant_id=1, year=2025, month=6)
            
            if inputs is not None:
                print_result("load_inputs_from_db returns inputs", True)
                passed += 1
            else:
                print_result("load_inputs_from_db returns inputs", False, "Returned None")
                failed += 1
                return passed, failed
            
            # Test 2: Check use factor is loaded from DB
            expected_uf = Decimal("0.88")  # 0.82 + 6/100
            actual_uf = inputs.use_factor
            if abs(actual_uf - expected_uf) < Decimal("0.01"):
                print_result("Use factor loaded from DB", True, f"UF={float(actual_uf):.3f}")
                passed += 1
            else:
                print_result("Use factor loaded from DB", False, 
                           f"Expected ~{float(expected_uf)}, got {float(actual_uf)}")
                failed += 1
            
            # Test 3: Check heat rate is loaded from DB
            expected_hr = Decimal("9860")  # 9800 + 6*10
            actual_hr = inputs.heat_rate_params.baseline_heat_rate
            if abs(actual_hr - expected_hr) < Decimal("10"):
                print_result("Heat rate loaded from DB", True, f"HR={float(actual_hr):.0f} BTU/kWh")
                passed += 1
            else:
                print_result("Heat rate loaded from DB", False, 
                           f"Expected ~{float(expected_hr)}, got {float(actual_hr)}")
                failed += 1
            
            # Test 4: Check SUF correction is loaded
            expected_suf = Decimal("50")
            actual_suf = inputs.heat_rate_params.suf_correction
            if actual_suf == expected_suf:
                print_result("SUF correction loaded from DB", True, f"SUF={float(actual_suf)}")
                passed += 1
            else:
                print_result("SUF correction loaded from DB", False, 
                           f"Expected {float(expected_suf)}, got {float(actual_suf)}")
                failed += 1
            
            # Test 5: Check plant params are correct
            if inputs.plant_params.plant_name == "Kyger Creek":
                print_result("Plant params correct", True)
                passed += 1
            else:
                print_result("Plant params correct", False, 
                           f"Expected Kyger Creek, got {inputs.plant_params.plant_name}")
                failed += 1
            
            # Test 6: UseFactorParams has monthly overrides
            if len(inputs.use_factor_params.monthly_unit_overrides) > 0:
                print_result("Monthly unit overrides populated", True, 
                           f"{len(inputs.use_factor_params.monthly_unit_overrides)} overrides")
                passed += 1
            else:
                print_result("Monthly unit overrides populated", False, "No overrides found")
                failed += 1
            
        finally:
            cleanup_test_data(db)
    
    return passed, failed


def test_calculation_uses_db_values():
    """Test that calculate_fuel_costs uses database values when no inputs provided."""
    print("\n" + "=" * 60)
    print("Testing calculate_fuel_costs with DB values")
    print("=" * 60)
    
    from src.db.postgres import get_session
    from src.engine.fuel_model import calculate_fuel_costs, FuelCostSummary
    
    passed = 0
    failed = 0
    
    with get_session() as db:
        # Setup
        setup_test_data(db)
        
        try:
            # Test 1: Calculate without providing inputs (should load from DB)
            result = calculate_fuel_costs(db, plant_id=1, year=2025, month=6)
            
            if isinstance(result, FuelCostSummary):
                print_result("Returns FuelCostSummary", True)
                passed += 1
            else:
                print_result("Returns FuelCostSummary", False, f"Got {type(result)}")
                failed += 1
                return passed, failed
            
            # Test 2: Result has generation calculated
            if result.net_delivered_mwh > 0:
                print_result("Generation calculated", True, 
                           f"{float(result.net_delivered_mwh):,.0f} MWh")
                passed += 1
            else:
                print_result("Generation calculated", False, "Zero generation")
                failed += 1
            
            # Test 3: Result has coal cost calculated
            if result.coal_cost > 0:
                print_result("Coal cost calculated", True, 
                           f"${float(result.coal_cost):,.0f}")
                passed += 1
            else:
                print_result("Coal cost calculated", False, "Zero coal cost")
                failed += 1
            
            # Test 4: Result has total fuel cost
            if result.total_fuel_cost > 0:
                print_result("Total fuel cost calculated", True, 
                           f"${float(result.total_fuel_cost):,.0f}")
                passed += 1
            else:
                print_result("Total fuel cost calculated", False, "Zero total")
                failed += 1
            
            # Test 5: Result has fuel cost per MWh
            if result.fuel_cost_per_mwh > 0:
                print_result("Cost per MWh calculated", True, 
                           f"${float(result.fuel_cost_per_mwh):.2f}/MWh")
                passed += 1
            else:
                print_result("Cost per MWh calculated", False, "Zero cost/MWh")
                failed += 1
            
            # Test 6: Unit-level breakdown populated
            if len(result.unit_generation) > 0:
                print_result("Unit-level breakdown populated", True, 
                           f"{len(result.unit_generation)} units")
                passed += 1
            else:
                print_result("Unit-level breakdown populated", False, "No unit data")
                failed += 1
            
        finally:
            cleanup_test_data(db)
    
    return passed, failed


def test_annual_calculation():
    """Test annual fuel cost calculation with DB values."""
    print("\n" + "=" * 60)
    print("Testing calculate_annual_fuel_costs with DB values")
    print("=" * 60)
    
    from src.db.postgres import get_session
    from src.engine.fuel_model import (
        calculate_annual_fuel_costs, 
        summarize_annual_fuel_costs,
        load_inputs_from_db,
    )
    
    passed = 0
    failed = 0
    
    with get_session() as db:
        # Setup
        setup_test_data(db)
        
        try:
            # Load inputs for base case (will be updated per month)
            base_inputs = load_inputs_from_db(db, plant_id=1, year=2025, month=1)
            
            # Calculate annual costs
            monthly_results = calculate_annual_fuel_costs(
                db, plant_id=1, year=2025, inputs=base_inputs
            )
            
            # Test 1: Get 12 monthly results
            if len(monthly_results) == 12:
                print_result("12 monthly results returned", True)
                passed += 1
            else:
                print_result("12 monthly results returned", False, 
                           f"Got {len(monthly_results)} results")
                failed += 1
            
            # Test 2: All months have positive generation
            all_positive = all(r.net_delivered_mwh > 0 for r in monthly_results)
            if all_positive:
                print_result("All months have generation", True)
                passed += 1
            else:
                zero_months = [r.period_month for r in monthly_results if r.net_delivered_mwh <= 0]
                print_result("All months have generation", False, 
                           f"Zero generation in months: {zero_months}")
                failed += 1
            
            # Test 3: Summarize annual costs
            annual_summary = summarize_annual_fuel_costs(monthly_results)
            
            if annual_summary.get("total_fuel_cost", 0) > 0:
                print_result("Annual summary calculated", True, 
                           f"${annual_summary['total_fuel_cost']:,.0f}")
                passed += 1
            else:
                print_result("Annual summary calculated", False, "Zero annual cost")
                failed += 1
            
            # Test 4: Annual MWh is reasonable (millions for a power plant)
            total_mwh = annual_summary.get("total_mwh", 0)
            if total_mwh > 1_000_000:  # At least 1 million MWh/year
                print_result("Annual MWh reasonable", True, 
                           f"{total_mwh:,.0f} MWh")
                passed += 1
            else:
                print_result("Annual MWh reasonable", False, 
                           f"Only {total_mwh:,.0f} MWh (expected > 1M)")
                failed += 1
            
            # Test 5: Cost per MWh is reasonable ($20-100)
            cost_per_mwh = annual_summary.get("avg_fuel_cost_per_mwh", 0)
            if 20 < cost_per_mwh < 100:
                print_result("Cost per MWh reasonable", True, 
                           f"${cost_per_mwh:.2f}/MWh")
                passed += 1
            else:
                print_result("Cost per MWh reasonable", False, 
                           f"${cost_per_mwh:.2f}/MWh (expected $20-100)")
                failed += 1
            
        finally:
            cleanup_test_data(db)
    
    return passed, failed


def main():
    """Run all database-driven calculation tests."""
    print("\n" + "=" * 60)
    print("DATABASE-DRIVEN CALCULATION TESTS")
    print("=" * 60)
    print("Testing that fuel model calculations use database values")
    print("for use factors, heat rates, and coal pricing.")
    
    total_passed = 0
    total_failed = 0
    
    # Check database connection
    try:
        from src.db.postgres import get_session
        with get_session() as db:
            pass
        print("\nDatabase connection successful.")
    except Exception as e:
        print(f"\n[ERROR] Cannot connect to database: {e}")
        print("Make sure the database is running and configured.")
        return False
    
    # Run tests
    p, f = test_load_inputs_from_db()
    total_passed += p
    total_failed += f
    
    p, f = test_calculation_uses_db_values()
    total_passed += p
    total_failed += f
    
    p, f = test_annual_calculation()
    total_passed += p
    total_failed += f
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_failed}")
    print(f"  Total:  {total_passed + total_failed}")
    
    if total_failed == 0:
        print("\n  All tests passed!")
    else:
        print(f"\n  {total_failed} test(s) failed.")
    
    return total_failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

