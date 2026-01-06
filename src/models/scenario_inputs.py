"""Scenario Inputs model - snapshots of fuel model inputs for saved scenarios.

When a scenario is saved, this captures all the key input parameters:
- Use factors by plant/month
- Heat rates by plant/month
- Coal pricing
- Outage schedule
- Other cost parameters

This allows scenarios to be re-calculated or compared later.
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Numeric, ForeignKey, DateTime, JSON, Text
)
from sqlalchemy.orm import relationship, Session
from typing import Dict, List, Optional, Any

from src.database import Base


class ScenarioInputSnapshot(Base):
    """Snapshot of all fuel model inputs for a saved scenario.
    
    Stores the full state of all input tables at the time
    the scenario was created, enabling comparison and re-calculation.
    """
    
    __tablename__ = "scenario_input_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Link to scenario
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False, unique=True, index=True)
    
    # Year this snapshot covers
    year = Column(Integer, nullable=False)
    
    # Use factors snapshot (JSON: {plant_id: {month: {base, ozone_non_scr}}})
    use_factors = Column(JSON, nullable=True)
    
    # Heat rates snapshot (JSON: {plant_id: {month: {baseline, suf, prb}}})
    heat_rates = Column(JSON, nullable=True)
    
    # Coal pricing snapshot (JSON: {plant_id: {month: {coal_price, barge_price, btu}}})
    coal_pricing = Column(JSON, nullable=True)
    
    # Outage schedule snapshot (JSON: {plant_id: {unit: {month: {planned, forced, reserve}}}})
    outages = Column(JSON, nullable=True)
    
    # Other cost parameters (JSON: various scalars)
    other_params = Column(JSON, nullable=True)
    
    # Summary metadata (quick-access values without parsing JSON)
    avg_use_factor_kc = Column(Numeric(5, 4), nullable=True)
    avg_use_factor_cc = Column(Numeric(5, 4), nullable=True)
    avg_heat_rate_kc = Column(Numeric(10, 2), nullable=True)
    avg_heat_rate_cc = Column(Numeric(10, 2), nullable=True)
    total_outage_days_kc = Column(Numeric(6, 1), nullable=True)
    total_outage_days_cc = Column(Numeric(6, 1), nullable=True)
    avg_coal_price = Column(Numeric(10, 2), nullable=True)
    
    # Notes about what changed from prior scenario
    change_summary = Column(Text, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100), nullable=True)
    
    # Relationships
    scenario = relationship("Scenario")
    
    def __repr__(self):
        return f"<ScenarioInputSnapshot(scenario_id={self.scenario_id}, year={self.year})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "scenario_id": self.scenario_id,
            "year": self.year,
            "use_factors": self.use_factors,
            "heat_rates": self.heat_rates,
            "coal_pricing": self.coal_pricing,
            "outages": self.outages,
            "other_params": self.other_params,
            "summary": {
                "avg_use_factor_kc": float(self.avg_use_factor_kc) if self.avg_use_factor_kc else None,
                "avg_use_factor_cc": float(self.avg_use_factor_cc) if self.avg_use_factor_cc else None,
                "avg_heat_rate_kc": float(self.avg_heat_rate_kc) if self.avg_heat_rate_kc else None,
                "avg_heat_rate_cc": float(self.avg_heat_rate_cc) if self.avg_heat_rate_cc else None,
                "total_outage_days_kc": float(self.total_outage_days_kc) if self.total_outage_days_kc else None,
                "total_outage_days_cc": float(self.total_outage_days_cc) if self.total_outage_days_cc else None,
                "avg_coal_price": float(self.avg_coal_price) if self.avg_coal_price else None,
            },
            "change_summary": self.change_summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
        }


# =============================================================================
# Helper Functions
# =============================================================================

def convert_decimals(obj):
    """Recursively convert Decimal values to float for JSON serialization."""
    from decimal import Decimal

    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    else:
        return obj


def capture_current_inputs(db: Session, year: int) -> Dict[str, Any]:
    """Capture current state of all fuel model inputs for a year.
    
    Reads from use_factor_inputs, heat_rate_inputs, unit_outage_inputs,
    and coal pricing tables to create a snapshot.
    
    Args:
        db: Database session
        year: The forecast year to capture
        
    Returns:
        Dictionary containing all input values
    """
    from src.models.use_factor import get_use_factors_for_year
    from src.models.heat_rate import get_heat_rates_for_year
    from src.models.unit_outage import get_unit_outages_for_year
    from src.models.coal_contract import UncommittedCoalPrice
    
    snapshot = {
        "year": year,
        "use_factors": {},
        "heat_rates": {},
        "coal_pricing": {},
        "outages": {},
        "other_params": {},
    }
    
    # Capture use factors for both plants
    for plant_id in [1, 2]:
        uf = get_use_factors_for_year(db, plant_id, year)
        if uf:
            snapshot["use_factors"][str(plant_id)] = uf
    
    # Capture heat rates for both plants
    for plant_id in [1, 2]:
        hr = get_heat_rates_for_year(db, plant_id, year)
        if hr:
            snapshot["heat_rates"][str(plant_id)] = {
                str(m): {
                    "baseline_heat_rate": float(v["plant"]["baseline_heat_rate"]) if "plant" in v else float(v.get("baseline_heat_rate", 9850)),
                    "min_load_heat_rate": float(v["plant"]["min_load_heat_rate"]) if "plant" in v and v["plant"].get("min_load_heat_rate") else None,
                    "suf_correction": float(v["plant"]["suf_correction"]) if "plant" in v else float(v.get("suf_correction", 0)),
                    "prb_blend_adjustment": float(v["plant"]["prb_blend_adjustment"]) if "plant" in v else float(v.get("prb_blend_adjustment", 0)),
                } for m, v in hr.items()
            }
    
    # Capture outages for both plants
    for plant_id in [1, 2]:
        outages = get_unit_outages_for_year(db, plant_id, year)
        plant_outages = {}
        for o in outages:
            unit_key = str(o.unit_number)
            if unit_key not in plant_outages:
                plant_outages[unit_key] = {}
            plant_outages[unit_key][str(o.month)] = {
                "planned_days": float(o.planned_outage_days or 0),
                "forced_days": float(o.forced_outage_days or 0),
                "reserve_days": float(o.reserve_shutdown_days or 0),
            }
        if plant_outages:
            snapshot["outages"][str(plant_id)] = plant_outages
    
    # Capture coal pricing
    for plant_id in [1, 2]:
        pricing = db.query(UncommittedCoalPrice).filter(
            UncommittedCoalPrice.plant_id == plant_id,
            UncommittedCoalPrice.year == year,
        ).all()

        plant_pricing = {}
        for p in pricing:
            plant_pricing[str(p.month)] = {
                "price_per_ton": float(p.price_per_ton) if p.price_per_ton else 0.0,
                "barge_per_ton": float(p.barge_per_ton or 0),
                "btu_per_lb": float(p.btu_per_lb) if p.btu_per_lb else 0.0,
            }
        if plant_pricing:
            snapshot["coal_pricing"][str(plant_id)] = plant_pricing

    # Ensure all Decimal values are converted to float
    return convert_decimals(snapshot)


def calculate_summary_metrics(snapshot: Dict[str, Any]) -> Dict[str, Decimal]:
    """Calculate summary metrics from a snapshot for quick comparison.
    
    Args:
        snapshot: The full input snapshot
        
    Returns:
        Dict with summary metrics
    """
    metrics = {
        "avg_use_factor_kc": None,
        "avg_use_factor_cc": None,
        "avg_heat_rate_kc": None,
        "avg_heat_rate_cc": None,
        "total_outage_days_kc": None,
        "total_outage_days_cc": None,
        "avg_coal_price": None,
    }
    
    # Use factors
    uf = snapshot.get("use_factors", {})
    if "1" in uf and uf["1"]:
        vals = [v.get("base", 0.85) for v in uf["1"].values()]
        if vals:
            metrics["avg_use_factor_kc"] = Decimal(str(sum(vals) / len(vals)))
    if "2" in uf and uf["2"]:
        vals = [v.get("base", 0.85) for v in uf["2"].values()]
        if vals:
            metrics["avg_use_factor_cc"] = Decimal(str(sum(vals) / len(vals)))
    
    # Heat rates
    hr = snapshot.get("heat_rates", {})
    if "1" in hr and hr["1"]:
        vals = []
        for v in hr["1"].values():
            if isinstance(v, dict):
                if "plant" in v:
                    vals.append(v["plant"].get("baseline_heat_rate", 9850))
                else:
                    vals.append(v.get("baseline_heat_rate", 9850))
        if vals:
            metrics["avg_heat_rate_kc"] = Decimal(str(sum(vals) / len(vals)))
    if "2" in hr and hr["2"]:
        vals = []
        for v in hr["2"].values():
            if isinstance(v, dict):
                if "plant" in v:
                    vals.append(v["plant"].get("baseline_heat_rate", 9900))
                else:
                    vals.append(v.get("baseline_heat_rate", 9900))
        if vals:
            metrics["avg_heat_rate_cc"] = Decimal(str(sum(vals) / len(vals)))
    
    # Outage days
    outages = snapshot.get("outages", {})
    if "1" in outages:
        total = 0
        for unit_data in outages["1"].values():
            for month_data in unit_data.values():
                total += month_data.get("planned_days", 0) + month_data.get("forced_days", 0)
        metrics["total_outage_days_kc"] = Decimal(str(total))
    if "2" in outages:
        total = 0
        for unit_data in outages["2"].values():
            for month_data in unit_data.values():
                total += month_data.get("planned_days", 0) + month_data.get("forced_days", 0)
        metrics["total_outage_days_cc"] = Decimal(str(total))
    
    # Coal price
    pricing = snapshot.get("coal_pricing", {})
    all_prices = []
    for plant_pricing in pricing.values():
        for month_data in plant_pricing.values():
            all_prices.append(month_data.get("price_per_ton", 55) + month_data.get("barge_per_ton", 6))
    if all_prices:
        metrics["avg_coal_price"] = Decimal(str(sum(all_prices) / len(all_prices)))
    
    return metrics


def save_scenario_snapshot(
    db: Session,
    scenario_id: int,
    year: int,
    change_summary: Optional[str] = None,
    created_by: Optional[str] = None,
) -> ScenarioInputSnapshot:
    """Save a snapshot of current inputs for a scenario.
    
    Args:
        db: Database session
        scenario_id: The scenario to link to
        year: The forecast year
        change_summary: Optional notes about changes
        created_by: User who created the snapshot
        
    Returns:
        The created ScenarioInputSnapshot
    """
    # Check for existing snapshot
    existing = db.query(ScenarioInputSnapshot).filter(
        ScenarioInputSnapshot.scenario_id == scenario_id
    ).first()
    
    if existing:
        db.delete(existing)
    
    # Capture current state
    snapshot_data = capture_current_inputs(db, year)

    # Calculate summary metrics
    metrics = calculate_summary_metrics(snapshot_data)

    # Convert all Decimal values to float for JSON storage
    snapshot_data = convert_decimals(snapshot_data)
    metrics = convert_decimals(metrics)

    # Create snapshot
    snapshot = ScenarioInputSnapshot(
        scenario_id=scenario_id,
        year=year,
        use_factors=snapshot_data["use_factors"],
        heat_rates=snapshot_data["heat_rates"],
        coal_pricing=snapshot_data["coal_pricing"],
        outages=snapshot_data["outages"],
        other_params=snapshot_data["other_params"],
        avg_use_factor_kc=metrics["avg_use_factor_kc"],
        avg_use_factor_cc=metrics["avg_use_factor_cc"],
        avg_heat_rate_kc=metrics["avg_heat_rate_kc"],
        avg_heat_rate_cc=metrics["avg_heat_rate_cc"],
        total_outage_days_kc=metrics["total_outage_days_kc"],
        total_outage_days_cc=metrics["total_outage_days_cc"],
        avg_coal_price=metrics["avg_coal_price"],
        change_summary=change_summary,
        created_by=created_by,
    )
    
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    
    return snapshot


def get_scenario_snapshot(db: Session, scenario_id: int) -> Optional[ScenarioInputSnapshot]:
    """Get the input snapshot for a scenario."""
    return db.query(ScenarioInputSnapshot).filter(
        ScenarioInputSnapshot.scenario_id == scenario_id
    ).first()


def compare_snapshots(
    snapshot_a: ScenarioInputSnapshot,
    snapshot_b: ScenarioInputSnapshot,
) -> Dict[str, Any]:
    """Compare two scenario snapshots and return differences.
    
    Args:
        snapshot_a: First snapshot (usually base/prior)
        snapshot_b: Second snapshot (usually current/comparison)
        
    Returns:
        Dict with differences by category
    """
    differences = {
        "use_factors": {},
        "heat_rates": {},
        "coal_pricing": {},
        "outages": {},
        "summary": {},
    }
    
    # Compare summary metrics
    for key in ["avg_use_factor_kc", "avg_use_factor_cc", 
                "avg_heat_rate_kc", "avg_heat_rate_cc",
                "total_outage_days_kc", "total_outage_days_cc",
                "avg_coal_price"]:
        val_a = getattr(snapshot_a, key)
        val_b = getattr(snapshot_b, key)
        if val_a != val_b:
            differences["summary"][key] = {
                "before": float(val_a) if val_a else None,
                "after": float(val_b) if val_b else None,
                "delta": float(val_b - val_a) if val_a and val_b else None,
            }
    
    return differences

