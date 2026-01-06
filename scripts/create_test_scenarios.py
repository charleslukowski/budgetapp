"""Create test scenarios for comparison feature testing."""

import sys
sys.path.insert(0, ".")

from datetime import datetime
from decimal import Decimal
from src.db.postgres import get_session
from src.models.scenario import Scenario, ScenarioType, ScenarioStatus
from src.models.scenario_inputs import ScenarioInputSnapshot

def create_test_scenarios(force_recreate=False):
    """Create sample scenarios for testing the comparison feature."""
    
    with get_session() as db:
        # Check if scenarios already exist
        existing = db.query(Scenario).count()
        if existing > 0:
            if force_recreate:
                print(f"Deleting {existing} existing scenarios...")
                db.query(ScenarioInputSnapshot).delete()
                db.query(Scenario).delete()
                db.commit()
            else:
                print(f"Already have {existing} scenarios. Run with --force to recreate.")
                return
        
        # Scenario 1: 2025 Budget (baseline)
        scenario1 = Scenario(
            name="2025 Budget",
            description="Original 2025 budget approved by board",
            scenario_type=ScenarioType.BUDGET,
            status=ScenarioStatus.PUBLISHED,
            version=1,
            is_locked=True,
            created_by="system",
        )
        db.add(scenario1)
        db.commit()
        db.refresh(scenario1)
        
        # Create snapshot for scenario 1
        snapshot1 = ScenarioInputSnapshot(
            scenario_id=scenario1.id,
            year=2025,
            use_factors={
                "1": {str(m): {"base": 0.85, "ozone_non_scr": 0.85} for m in range(1, 13)},
                "2": {str(m): {"base": 0.85, "ozone_non_scr": 0.0 if m in [5,6,7,8,9] else 0.85} for m in range(1, 13)},
            },
            heat_rates={
                "1": {str(m): {"baseline": 9850, "suf": 50, "prb": 0} for m in range(1, 13)},
                "2": {str(m): {"baseline": 9850, "suf": 50, "prb": 0} for m in range(1, 13)},
            },
            coal_pricing={
                "1": {str(m): {"coal_price": 61.00, "barge_price": 6.50, "btu": 11500} for m in range(1, 13)},
                "2": {str(m): {"coal_price": 61.00, "barge_price": 6.50, "btu": 11500} for m in range(1, 13)},
            },
            outages={
                "1": {"1": {str(m): {"planned": 0, "forced": 0, "reserve": 0} for m in range(1, 13)}},
                "2": {"1": {str(m): {"planned": 0, "forced": 0, "reserve": 0} for m in range(1, 13)}},
            },
            other_params={
                "limestone_price": 30.00,
                "urea_price": 410.00,
                "ash_sale_price": 15.00,
                "gypsum_sale_price": 3.00,
            },
            avg_use_factor_kc=Decimal("0.8500"),
            avg_use_factor_cc=Decimal("0.8100"),  # Lower due to ozone
            avg_heat_rate_kc=Decimal("9900"),
            avg_heat_rate_cc=Decimal("9900"),
            total_outage_days_kc=Decimal("0"),
            total_outage_days_cc=Decimal("0"),
            avg_coal_price=Decimal("67.50"),
            change_summary="Original 2025 budget baseline",
            created_by="system",
        )
        db.add(snapshot1)
        
        # Scenario 2: Q4 2025 Reforecast (modified)
        scenario2 = Scenario(
            name="Q4 2025 Reforecast",
            description="Updated forecast based on Q3 actuals",
            scenario_type=ScenarioType.INTERNAL_FORECAST,
            status=ScenarioStatus.DRAFT,
            version=1,
            parent_scenario_id=scenario1.id,
            created_by="system",
        )
        db.add(scenario2)
        db.commit()
        db.refresh(scenario2)
        
        # Create snapshot for scenario 2 (with some changes)
        snapshot2 = ScenarioInputSnapshot(
            scenario_id=scenario2.id,
            year=2025,
            use_factors={
                "1": {str(m): {"base": 0.82, "ozone_non_scr": 0.82} for m in range(1, 13)},  # Lower
                "2": {str(m): {"base": 0.83, "ozone_non_scr": 0.0 if m in [5,6,7,8,9] else 0.83} for m in range(1, 13)},
            },
            heat_rates={
                "1": {str(m): {"baseline": 9900, "suf": 75, "prb": 50} for m in range(1, 13)},  # Higher
                "2": {str(m): {"baseline": 9900, "suf": 75, "prb": 50} for m in range(1, 13)},
            },
            coal_pricing={
                "1": {str(m): {"coal_price": 63.00, "barge_price": 7.00, "btu": 11400} for m in range(1, 13)},  # Higher
                "2": {str(m): {"coal_price": 63.00, "barge_price": 7.00, "btu": 11400} for m in range(1, 13)},
            },
            outages={
                "1": {"1": {"10": {"planned": 14, "forced": 0, "reserve": 0}}},  # Oct outage
                "2": {"1": {str(m): {"planned": 0, "forced": 0, "reserve": 0} for m in range(1, 13)}},
            },
            other_params={
                "limestone_price": 32.00,
                "urea_price": 420.00,
                "ash_sale_price": 14.00,
                "gypsum_sale_price": 3.50,
            },
            avg_use_factor_kc=Decimal("0.8200"),
            avg_use_factor_cc=Decimal("0.7900"),
            avg_heat_rate_kc=Decimal("10025"),
            avg_heat_rate_cc=Decimal("10025"),
            total_outage_days_kc=Decimal("14"),
            total_outage_days_cc=Decimal("0"),
            avg_coal_price=Decimal("70.00"),
            change_summary="Adjusted for actual Q3 performance and coal market",
            created_by="system",
        )
        db.add(snapshot2)
        
        # Scenario 3: Stress Test - High Coal Price
        scenario3 = Scenario(
            name="2025 Stress Test - High Coal",
            description="What-if scenario with $75/ton coal",
            scenario_type=ScenarioType.INTERNAL_FORECAST,
            status=ScenarioStatus.DRAFT,
            version=1,
            parent_scenario_id=scenario1.id,
            created_by="system",
        )
        db.add(scenario3)
        db.commit()
        db.refresh(scenario3)
        
        snapshot3 = ScenarioInputSnapshot(
            scenario_id=scenario3.id,
            year=2025,
            use_factors={
                "1": {str(m): {"base": 0.85, "ozone_non_scr": 0.85} for m in range(1, 13)},
                "2": {str(m): {"base": 0.85, "ozone_non_scr": 0.0 if m in [5,6,7,8,9] else 0.85} for m in range(1, 13)},
            },
            heat_rates={
                "1": {str(m): {"baseline": 9850, "suf": 50, "prb": 0} for m in range(1, 13)},
                "2": {str(m): {"baseline": 9850, "suf": 50, "prb": 0} for m in range(1, 13)},
            },
            coal_pricing={
                "1": {str(m): {"coal_price": 75.00, "barge_price": 8.00, "btu": 11500} for m in range(1, 13)},  # Much higher
                "2": {str(m): {"coal_price": 75.00, "barge_price": 8.00, "btu": 11500} for m in range(1, 13)},
            },
            outages={
                "1": {"1": {str(m): {"planned": 0, "forced": 0, "reserve": 0} for m in range(1, 13)}},
                "2": {"1": {str(m): {"planned": 0, "forced": 0, "reserve": 0} for m in range(1, 13)}},
            },
            other_params={
                "limestone_price": 30.00,
                "urea_price": 410.00,
                "ash_sale_price": 15.00,
                "gypsum_sale_price": 3.00,
            },
            avg_use_factor_kc=Decimal("0.8500"),
            avg_use_factor_cc=Decimal("0.8100"),
            avg_heat_rate_kc=Decimal("9900"),
            avg_heat_rate_cc=Decimal("9900"),
            total_outage_days_kc=Decimal("0"),
            total_outage_days_cc=Decimal("0"),
            avg_coal_price=Decimal("83.00"),
            change_summary="Stress test: coal at $75/ton + $8 barge",
            created_by="system",
        )
        db.add(snapshot3)
        
        db.commit()
        
        print("=" * 60)
        print("CREATED TEST SCENARIOS")
        print("=" * 60)
        print(f"1. {scenario1.name} (ID: {scenario1.id})")
        print(f"2. {scenario2.name} (ID: {scenario2.id})")
        print(f"3. {scenario3.name} (ID: {scenario3.id})")
        print()
        print("Test comparison at:")
        print(f"  http://localhost:8000/scenarios/compare?a={scenario1.id}&b={scenario2.id}")


if __name__ == "__main__":
    force = "--force" in sys.argv
    create_test_scenarios(force_recreate=force)
