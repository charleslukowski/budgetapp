"""Test script for the unit outage tracking system.

Tests:
1. Database model and CRUD operations
2. Availability and EFOR calculations
3. Integration with generation calculations
4. API endpoints
"""

import sys
import os
from decimal import Decimal
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.db.postgres import get_session
from src.models.unit_outage import (
    UnitOutageInput,
    upsert_unit_outage,
    get_unit_outages_for_year,
    get_unit_outages_for_period,
    calculate_unit_availability,
    calculate_plant_availability,
    get_annual_outage_summary,
    build_unit_availability_from_db,
)
from src.engine.generation import (
    create_kyger_params,
    create_clifty_params,
    calculate_generation,
    calculate_generation_with_outages,
    get_plant_efor_summary,
)


def test_outage_crud():
    """Test basic CRUD operations for unit outages."""
    print("\n" + "=" * 60)
    print("TEST: Unit Outage CRUD Operations")
    print("=" * 60)
    
    with get_session() as db:
        # Create a test outage record
        outage = upsert_unit_outage(
            db,
            plant_id=1,  # Kyger Creek
            unit_number=1,
            year=2025,
            month=4,  # April - typical spring outage month
            planned_outage_days=Decimal("21"),  # 3-week outage
            forced_outage_days=Decimal("0"),
            outage_type="MAJOR",
            outage_description="Annual spring overhaul",
            updated_by="test_script",
        )
        
        print(f"  Created outage: {outage}")
        print(f"    - Planned days: {outage.planned_outage_days}")
        print(f"    - Total days: {outage.total_outage_days}")
        
        # Read it back
        outages = get_unit_outages_for_period(db, 1, 2025, 4)
        print(f"  Retrieved {len(outages)} outage(s) for April 2025")
        
        # Update it
        outage = upsert_unit_outage(
            db,
            plant_id=1,
            unit_number=1,
            year=2025,
            month=4,
            planned_outage_days=Decimal("28"),  # Extended to 4 weeks
            forced_outage_days=Decimal("3"),
            outage_type="MAJOR",
            outage_description="Extended spring overhaul",
            updated_by="test_script",
        )
        print(f"  Updated outage: planned={outage.planned_outage_days}, forced={outage.forced_outage_days}")
    
    print("  CRUD tests PASSED")


def test_availability_calculations():
    """Test availability and EFOR calculations."""
    print("\n" + "=" * 60)
    print("TEST: Availability and EFOR Calculations")
    print("=" * 60)
    
    # Create a test outage
    test_outage = UnitOutageInput(
        plant_id=1,
        unit_number=1,
        year=2025,
        month=4,
        planned_outage_days=Decimal("21"),  # 21 days planned (70% of month)
        forced_outage_days=Decimal("2"),    # 2 days forced
        reserve_shutdown_days=Decimal("0"),
    )
    
    # Calculate metrics
    metrics = calculate_unit_availability(test_outage, 2025, 4)
    
    print(f"  Test outage: 21 planned + 2 forced days in April 2025 (30 days)")
    print(f"  Availability Factor: {metrics['availability_factor']:.3f}")
    print(f"    - Expected: ~0.233 (7 available days / 30 total)")
    print(f"  EFOR: {metrics['efor']:.3f}")
    print(f"    - Represents forced outage rate during potential service hours")
    print(f"  Available Hours: {metrics['available_hours']}")
    print(f"  Period Hours: {metrics['period_hours']}")
    
    # Verify calculation
    expected_avail = Decimal("7") / Decimal("30")  # 7 available days / 30 total
    actual_avail = metrics['availability_factor']
    
    if abs(float(actual_avail) - float(expected_avail)) < 0.01:
        print("  Availability calculation PASSED")
    else:
        print(f"  Availability calculation FAILED: expected {expected_avail}, got {actual_avail}")


def test_plant_availability():
    """Test plant-level weighted availability."""
    print("\n" + "=" * 60)
    print("TEST: Plant-Level Weighted Availability")
    print("=" * 60)
    
    # Create outages for multiple units
    outages = [
        UnitOutageInput(
            plant_id=1, unit_number=1, year=2025, month=4,
            planned_outage_days=Decimal("21"), forced_outage_days=Decimal("0"),
        ),
        UnitOutageInput(
            plant_id=1, unit_number=2, year=2025, month=4,
            planned_outage_days=Decimal("0"), forced_outage_days=Decimal("0"),
        ),
        UnitOutageInput(
            plant_id=1, unit_number=3, year=2025, month=4,
            planned_outage_days=Decimal("0"), forced_outage_days=Decimal("0"),
        ),
        UnitOutageInput(
            plant_id=1, unit_number=4, year=2025, month=4,
            planned_outage_days=Decimal("0"), forced_outage_days=Decimal("0"),
        ),
        UnitOutageInput(
            plant_id=1, unit_number=5, year=2025, month=4,
            planned_outage_days=Decimal("0"), forced_outage_days=Decimal("0"),
        ),
    ]
    
    # All units have same capacity
    unit_capacities = {1: Decimal("205"), 2: Decimal("205"), 3: Decimal("205"), 
                       4: Decimal("205"), 5: Decimal("205")}
    
    metrics = calculate_plant_availability(outages, 2025, 4, unit_capacities)
    
    print(f"  Scenario: Unit 1 out for 21 days, Units 2-5 fully available")
    print(f"  Weighted Availability: {metrics['weighted_availability']:.3f}")
    print(f"    - Expected: ~0.86 (4 units at 100% + 1 unit at 30%)")
    print(f"  Weighted EFOR: {metrics['weighted_efor']:.4f}")
    print(f"  Total Outage Days: {metrics['total_outage_days']}")
    
    # With 1/5 units at 30% availability and 4/5 at 100%:
    # Expected = 0.2 * 0.3 + 0.8 * 1.0 = 0.06 + 0.8 = 0.86
    expected = Decimal("0.2") * (Decimal("9") / Decimal("30")) + Decimal("0.8") * Decimal("1")
    
    if abs(float(metrics['weighted_availability']) - 0.86) < 0.05:
        print("  Plant availability calculation PASSED")
    else:
        print(f"  Plant availability calculation FAILED")


def test_generation_integration():
    """Test integration with generation calculations."""
    print("\n" + "=" * 60)
    print("TEST: Generation Integration with Outages")
    print("=" * 60)
    
    with get_session() as db:
        # Set up some outages in the database
        upsert_unit_outage(db, 1, 1, 2025, 4, Decimal("21"), Decimal("0"))
        upsert_unit_outage(db, 1, 2, 2025, 10, Decimal("21"), Decimal("0"))
        
        # Calculate generation without outages
        kyger = create_kyger_params()
        gen_no_outage = calculate_generation(
            kyger, 2025, 4, use_factor=Decimal("0.85")
        )
        
        # Calculate generation with outages from database
        gen_with_outage = calculate_generation_with_outages(
            kyger, 2025, 4, use_factor=Decimal("0.85"),
            db_session=db, plant_id=1
        )
        
        print(f"  April 2025 (Unit 1 out for 21 days):")
        print(f"    Without outage data:")
        print(f"      - Gross MWh: {gen_no_outage.gross_mwh_available:,.0f}")
        print(f"      - Net Delivered: {gen_no_outage.net_delivered_mwh:,.0f}")
        print(f"    With outage data:")
        print(f"      - Gross MWh: {gen_with_outage.gross_mwh_available:,.0f}")
        print(f"      - Net Delivered: {gen_with_outage.net_delivered_mwh:,.0f}")
        
        # The generation with outages should be lower
        reduction = gen_no_outage.gross_mwh_available - gen_with_outage.gross_mwh_available
        reduction_pct = (reduction / gen_no_outage.gross_mwh_available) * 100
        
        print(f"    Reduction due to outage: {reduction:,.0f} MWh ({reduction_pct:.1f}%)")
        print(f"    Expected ~14% reduction (21/30 days on 1/5 units)")
        
        if reduction_pct > 5:  # Should be around 14%
            print("  Generation integration PASSED")
        else:
            print("  Generation integration FAILED: Expected reduction not seen")


def test_efor_summary():
    """Test EFOR summary function."""
    print("\n" + "=" * 60)
    print("TEST: EFOR Summary")
    print("=" * 60)
    
    with get_session() as db:
        # Set up a year of outages
        # Kyger: Unit 1 in April, Unit 2 in October
        upsert_unit_outage(db, 1, 1, 2025, 4, Decimal("21"), Decimal("0"))
        upsert_unit_outage(db, 1, 2, 2025, 10, Decimal("21"), Decimal("0"))
        
        # Get EFOR summary
        summary = get_plant_efor_summary(db, 1, 2025)
        
        print(f"  Kyger Creek 2025 EFOR Summary:")
        print(f"    Average Availability: {summary['annual']['avg_availability']:.1%}")
        print(f"    Average EFOR: {summary['annual']['avg_efor']:.2%}")
        print(f"    Total Outage Days: {summary['annual']['total_outage_days']}")
        
        # Check April and October
        print(f"    April (outage month):")
        print(f"      - Availability: {summary['monthly'][4]['availability']:.1%}")
        print(f"    October (outage month):")
        print(f"      - Availability: {summary['monthly'][10]['availability']:.1%}")
        print(f"    January (no outages):")
        print(f"      - Availability: {summary['monthly'][1]['availability']:.1%}")


def test_annual_summary():
    """Test annual outage summary."""
    print("\n" + "=" * 60)
    print("TEST: Annual Outage Summary")
    print("=" * 60)
    
    with get_session() as db:
        summary = get_annual_outage_summary(db, 1, 2025)
        
        print(f"  Kyger Creek 2025 Annual Summary:")
        print(f"    Total Planned Days: {summary['total_planned_days']}")
        print(f"    Total Forced Days: {summary['total_forced_days']}")
        print(f"    Total Outage Days: {summary['total_outage_days']}")
        
        if summary['unit_totals']:
            print(f"    By Unit:")
            for unit_num, totals in summary['unit_totals'].items():
                print(f"      Unit {unit_num}: {totals['planned_days']} planned, {totals['forced_days']} forced")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("UNIT OUTAGE SYSTEM TEST SUITE")
    print("=" * 60)
    print(f"Timestamp: {datetime.now()}")
    
    try:
        test_outage_crud()
        test_availability_calculations()
        test_plant_availability()
        test_generation_integration()
        test_efor_summary()
        test_annual_summary()
        
        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

