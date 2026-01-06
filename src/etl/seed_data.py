"""Seed data for OVEC Budget System."""

from datetime import datetime
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.models import Plant, Period, CostCategory, Scenario
from src.models.period import Granularity
from src.models.cost_category import CostSection
from src.models.scenario import ScenarioType, ScenarioStatus


def seed_plants(db: Session) -> dict:
    """Create Kyger Creek and Clifty Creek plants."""
    plants = {}
    
    # Check if plants already exist
    existing = db.query(Plant).first()
    if existing:
        print("Plants already exist, skipping...")
        plants = {p.short_name: p for p in db.query(Plant).all()}
        return plants
    
    kyger = Plant(
        name="Kyger Creek",
        short_name="Kyger",
        capacity_mw=1000,      # 5 x 200 MW
        unit_count=5,
        unit_capacity_mw=200,
        is_active=True,
    )
    
    clifty = Plant(
        name="Clifty Creek",
        short_name="Clifty",
        capacity_mw=1200,      # 6 x 200 MW
        unit_count=6,
        unit_capacity_mw=200,
        is_active=True,
    )
    
    db.add(kyger)
    db.add(clifty)
    db.commit()
    
    plants["Kyger"] = kyger
    plants["Clifty"] = clifty
    
    print(f"Created plants: Kyger Creek (1000 MW), Clifty Creek (1200 MW)")
    return plants


def seed_periods(db: Session, start_year: int = 2025, end_year: int = 2040) -> None:
    """Create periods from start_year to end_year."""
    # Check if periods already exist
    existing = db.query(Period).filter(Period.year == start_year).first()
    if existing:
        print("Periods already exist, skipping...")
        return
    
    periods_created = 0
    
    # Years 1-2: Monthly granularity
    for year in range(start_year, start_year + 2):
        for month in range(1, 13):
            period = Period(
                year=year,
                month=month,
                quarter=None,
                granularity=Granularity.MONTHLY,
            )
            db.add(period)
            periods_created += 1
    
    # Years 3-16: Annual granularity
    for year in range(start_year + 2, end_year + 1):
        period = Period(
            year=year,
            month=None,
            quarter=None,
            granularity=Granularity.ANNUAL,
        )
        db.add(period)
        periods_created += 1
    
    db.commit()
    print(f"Created {periods_created} periods ({start_year} to {end_year})")


def seed_cost_categories(db: Session) -> dict:
    """Create the cost category hierarchy."""
    # Check if categories already exist
    existing = db.query(CostCategory).first()
    if existing:
        print("Cost categories already exist, skipping...")
        return {c.short_name: c for c in db.query(CostCategory).all()}
    
    categories = {}
    
    # FUEL COSTS
    fuel_cats = [
        ("Coal Procurement - Eastern", "Coal East", 1),
        ("Coal Procurement - ILB", "Coal ILB", 2),
        ("Coal Transportation", "Coal Transport", 3),
        ("Coal Handling", "Coal Handling", 4),
        ("Fuel Oil/Gas", "Fuel Oil", 5),
        ("Emissions Allowances", "Emissions", 6),
        ("Environmental Compliance", "Environmental", 7),
    ]
    
    for name, short, order in fuel_cats:
        cat = CostCategory(
            name=name,
            short_name=short,
            section=CostSection.FUEL,
            sort_order=order,
            is_subtotal=False,
            is_active=True,
        )
        db.add(cat)
        categories[short] = cat
    
    # OPERATING COSTS
    op_cats = [
        ("Plant Labor", "Labor", 1),
        ("Plant Maintenance", "Maintenance", 2),
        ("Materials & Supplies", "Materials", 3),
        ("Major Maintenance", "Major Maint", 4),
        ("Asset Health Items", "Asset Health", 5),
        ("Transmission Costs", "Transmission", 6),
        ("Water & Wastewater", "Water", 7),
        ("Other Operating", "Other Op", 8),
    ]
    
    for name, short, order in op_cats:
        cat = CostCategory(
            name=name,
            short_name=short,
            section=CostSection.OPERATING,
            sort_order=order,
            is_subtotal=False,
            is_active=True,
        )
        db.add(cat)
        categories[short] = cat
    
    # NON-OPERATING COSTS
    nonop_cats = [
        ("Administrative & General", "A&G", 1),
        ("Insurance", "Insurance", 2),
        ("Property Taxes", "Prop Tax", 3),
        ("Regulatory Fees", "Regulatory", 4),
        ("Professional Services", "Prof Services", 5),
        ("Other Non-Operating", "Other Non-Op", 6),
    ]
    
    for name, short, order in nonop_cats:
        cat = CostCategory(
            name=name,
            short_name=short,
            section=CostSection.NON_OPERATING,
            sort_order=order,
            is_subtotal=False,
            is_active=True,
        )
        db.add(cat)
        categories[short] = cat
    
    # CAPITAL COSTS
    cap_cats = [
        ("Depreciation - Existing Assets", "Depr Existing", 1),
        ("Depreciation - New Projects", "Depr New", 2),
        ("Return on Investment", "ROI", 3),
        ("Capital Project Billing", "Cap Projects", 4),
    ]
    
    for name, short, order in cap_cats:
        cat = CostCategory(
            name=name,
            short_name=short,
            section=CostSection.CAPITAL,
            sort_order=order,
            is_subtotal=False,
            is_active=True,
        )
        db.add(cat)
        categories[short] = cat
    
    db.commit()
    print(f"Created {len(categories)} cost categories")
    return categories


def seed_default_scenarios(db: Session) -> dict:
    """Create the three default scenario types."""
    # Check if scenarios already exist
    existing = db.query(Scenario).first()
    if existing:
        print("Scenarios already exist, skipping...")
        return {s.scenario_type.value: s for s in db.query(Scenario).all()}
    
    scenarios = {}
    
    budget = Scenario(
        name="2025 Budget",
        description="Official 2025 budget approved by sponsors",
        scenario_type=ScenarioType.BUDGET,
        status=ScenarioStatus.DRAFT,
        version=1,
        created_by="System",
    )
    db.add(budget)
    scenarios["budget"] = budget
    
    internal = Scenario(
        name="2025 Internal Forecast",
        description="Internal working forecast for management",
        scenario_type=ScenarioType.INTERNAL_FORECAST,
        status=ScenarioStatus.DRAFT,
        version=1,
        created_by="System",
    )
    db.add(internal)
    scenarios["internal_forecast"] = internal
    
    external = Scenario(
        name="2025 External Forecast",
        description="Forecast shared with sponsors",
        scenario_type=ScenarioType.EXTERNAL_FORECAST,
        status=ScenarioStatus.DRAFT,
        version=1,
        created_by="System",
    )
    db.add(external)
    scenarios["external_forecast"] = external
    
    db.commit()
    print("Created 3 default scenarios: Budget, Internal Forecast, External Forecast")
    return scenarios


def run_all_seeds():
    """Run all seed functions."""
    print("=" * 50)
    print("OVEC Budget System - Database Seeding")
    print("=" * 50)
    
    db = SessionLocal()
    try:
        plants = seed_plants(db)
        seed_periods(db)
        categories = seed_cost_categories(db)
        scenarios = seed_default_scenarios(db)
        
        print("=" * 50)
        print("Seeding complete!")
        print(f"  Plants: {len(plants)}")
        print(f"  Categories: {len(categories)}")
        print(f"  Scenarios: {len(scenarios)}")
        print("=" * 50)
        
    finally:
        db.close()


if __name__ == "__main__":
    run_all_seeds()

