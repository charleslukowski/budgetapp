"""Multi-year projection engine with escalation.

Calculates fuel costs across multiple years by applying escalation factors
to price-based drivers from a base year.

Supports:
- Annual escalation rates for different driver categories
- Monthly granularity for near-term (Years 1-2), annual for long-term
- Sponsor reporting format matching OVEC requirements
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from sqlalchemy.orm import Session

from src.engine.drivers import FuelModel
from src.engine.default_drivers import create_default_fuel_model
from src.engine.fuel_model import (
    FuelCostSummary,
    calculate_fuel_costs_from_drivers,
    summarize_annual_fuel_costs,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Escalation Configuration
# =============================================================================

@dataclass
class EscalationConfig:
    """Configuration for price escalation."""
    
    # Escalation driver name -> list of drivers it applies to
    ESCALATION_MAPPINGS: Dict[str, List[str]] = field(default_factory=lambda: {
        "escalation_coal_annual": [
            "coal_price_eastern",
            "coal_price_ilb",
            "coal_price_prb",
        ],
        "escalation_transport_annual": [
            "barge_rate_ohio",
            "barge_rate_upper_ohio",
            "rail_rate_prb",
        ],
        "escalation_reagent_annual": [
            # Future reagent price drivers would go here
        ],
    })


def apply_escalation(
    base_value: Decimal,
    base_year: int,
    target_year: int,
    annual_rate_pct: Decimal,
) -> Decimal:
    """Apply compound annual escalation to a base value.
    
    Args:
        base_value: Starting value
        base_year: Year of the base value
        target_year: Year to escalate to
        annual_rate_pct: Annual escalation rate as percentage (e.g., 2.5 for 2.5%)
        
    Returns:
        Escalated value
    """
    years = target_year - base_year
    if years <= 0:
        return base_value
    
    # Convert percentage to decimal rate
    rate = annual_rate_pct / Decimal("100")
    
    # Compound: value * (1 + rate)^years
    escalated = base_value * (Decimal("1") + rate) ** years
    
    return escalated.quantize(Decimal("0.01"))


def create_escalated_model(
    base_model: FuelModel,
    base_year: int,
    target_year: int,
    plant_id: Optional[int] = None,
) -> FuelModel:
    """Create a FuelModel with escalated values for a target year.
    
    Args:
        base_model: Model with base year values
        base_year: Base year for values
        target_year: Target year to escalate to
        plant_id: Optional specific plant
        
    Returns:
        New FuelModel with escalated values
    """
    if target_year <= base_year:
        return base_model
    
    # Create a new model
    escalated_model = create_default_fuel_model()
    
    # Get escalation rates from base model
    escalation_config = EscalationConfig()
    
    # Apply escalation for each mapping
    for escalation_driver, target_drivers in escalation_config.ESCALATION_MAPPINGS.items():
        # Get the escalation rate
        try:
            rate = base_model.get_driver_value(escalation_driver, base_year, 1, plant_id)
        except ValueError:
            rate = Decimal("0")
        
        # Apply to each target driver
        for target_driver in target_drivers:
            try:
                base_value = base_model.get_driver_value(target_driver, base_year, 1, plant_id)
                escalated_value = apply_escalation(base_value, base_year, target_year, rate)
                
                # Set as annual value for target year
                escalated_model.set_driver_value(target_driver, target_year, None, escalated_value, plant_id)
            except ValueError:
                # Driver not found, skip
                pass
    
    # Copy non-escalated drivers from base year
    non_escalated_drivers = [
        "heat_rate_baseline",
        "heat_rate_suf_correction",
        "heat_rate_prb_penalty",
        "use_factor",
        "capacity_mw",
        "reserve_mw",
        "fgd_aux_pct",
        "gsu_loss_pct",
        "inventory_target_days",
        "coal_blend_eastern_pct",
        "coal_blend_ilb_pct",
        "coal_blend_prb_pct",
        "coal_btu_eastern",
        "coal_btu_ilb",
    ]
    
    for driver_name in non_escalated_drivers:
        try:
            # Try to get annual value first
            base_value = base_model.get_driver_value(driver_name, base_year, 1, plant_id)
            escalated_model.set_driver_value(driver_name, target_year, None, base_value, plant_id)
        except ValueError:
            pass
    
    # Also carry forward escalation rates themselves
    for escalation_driver in escalation_config.ESCALATION_MAPPINGS.keys():
        try:
            rate = base_model.get_driver_value(escalation_driver, base_year, 1, plant_id)
            escalated_model.set_driver_value(escalation_driver, target_year, None, rate, plant_id)
        except ValueError:
            pass
    
    return escalated_model


# =============================================================================
# Multi-Year Projection
# =============================================================================

@dataclass
class AnnualProjection:
    """Projection results for a single year."""
    year: int
    plant_name: str
    plant_id: Optional[int]
    
    # Generation
    total_mwh: float = 0
    avg_capacity_factor: float = 0
    
    # Fuel costs
    total_coal_tons: float = 0
    total_coal_cost: float = 0
    total_consumables_cost: float = 0
    total_byproduct_net: float = 0
    total_fuel_cost: float = 0
    avg_fuel_cost_per_mwh: float = 0
    
    # Input assumptions (escalated)
    coal_price_eastern: float = 0
    barge_rate: float = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "year": self.year,
            "plant": self.plant_name,
            "plant_id": self.plant_id,
            "total_mwh": self.total_mwh,
            "avg_capacity_factor": self.avg_capacity_factor,
            "total_coal_tons": self.total_coal_tons,
            "total_coal_cost": self.total_coal_cost,
            "total_consumables_cost": self.total_consumables_cost,
            "total_byproduct_net": self.total_byproduct_net,
            "total_fuel_cost": self.total_fuel_cost,
            "avg_fuel_cost_per_mwh": self.avg_fuel_cost_per_mwh,
            "assumptions": {
                "coal_price_eastern": self.coal_price_eastern,
                "barge_rate": self.barge_rate,
            }
        }


@dataclass
class MultiYearProjection:
    """Complete multi-year projection results."""
    base_year: int
    end_year: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Projections by year and plant
    kyger_projections: List[AnnualProjection] = field(default_factory=list)
    clifty_projections: List[AnnualProjection] = field(default_factory=list)
    system_projections: List[AnnualProjection] = field(default_factory=list)
    
    # Monthly detail for near-term years
    near_term_monthly: Dict[int, Dict[int, List[Dict]]] = field(default_factory=dict)
    # Structure: {year: {plant_id: [monthly_dicts]}}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "base_year": self.base_year,
            "end_year": self.end_year,
            "created_at": self.created_at.isoformat(),
            "kyger": [p.to_dict() for p in self.kyger_projections],
            "clifty": [p.to_dict() for p in self.clifty_projections],
            "system": [p.to_dict() for p in self.system_projections],
            "near_term_monthly": self.near_term_monthly,
        }


def project_single_year(
    db: Session,
    base_model: FuelModel,
    base_year: int,
    target_year: int,
    plant_id: int,
) -> Tuple[AnnualProjection, List[FuelCostSummary]]:
    """Project fuel costs for a single year and plant.
    
    Args:
        db: Database session
        base_model: Model with base year driver values
        base_year: Base year
        target_year: Target year to project
        plant_id: Plant ID (1=Kyger, 2=Clifty)
        
    Returns:
        Tuple of (AnnualProjection, list of monthly summaries)
    """
    # Create escalated model for target year
    if target_year > base_year:
        model = create_escalated_model(base_model, base_year, target_year, plant_id)
    else:
        model = base_model
    
    # Calculate monthly fuel costs
    monthly_results = []
    for month in range(1, 13):
        summary = calculate_fuel_costs_from_drivers(db, model, plant_id, target_year, month)
        monthly_results.append(summary)
    
    # Summarize annual
    annual = summarize_annual_fuel_costs(monthly_results)
    
    # Create projection object
    projection = AnnualProjection(
        year=target_year,
        plant_name=annual.get("plant", ""),
        plant_id=plant_id,
        total_mwh=annual.get("total_mwh", 0),
        avg_capacity_factor=annual.get("avg_capacity_factor", 0),
        total_coal_tons=annual.get("total_coal_tons", 0),
        total_coal_cost=annual.get("total_coal_cost", 0),
        total_consumables_cost=annual.get("total_consumables_cost", 0),
        total_byproduct_net=annual.get("total_byproduct_net", 0),
        total_fuel_cost=annual.get("total_fuel_cost", 0),
        avg_fuel_cost_per_mwh=annual.get("avg_fuel_cost_per_mwh", 0),
    )
    
    # Get key assumptions
    try:
        projection.coal_price_eastern = float(model.get_driver_value("coal_price_eastern", target_year, 1, plant_id))
    except ValueError:
        pass
    try:
        projection.barge_rate = float(model.get_driver_value("barge_rate_ohio", target_year, 1, plant_id))
    except ValueError:
        pass
    
    return projection, monthly_results


def project_multi_year(
    db: Session,
    base_model: FuelModel,
    base_year: int,
    end_year: int = 2040,
    near_term_years: int = 2,
) -> MultiYearProjection:
    """Calculate multi-year fuel cost projections.
    
    Args:
        db: Database session
        base_model: Model with base year driver values
        base_year: Starting year
        end_year: Ending year (default 2040 per OVEC contract)
        near_term_years: Number of years to include monthly detail (default 2)
        
    Returns:
        MultiYearProjection with all results
    """
    result = MultiYearProjection(
        base_year=base_year,
        end_year=end_year,
    )
    
    for year in range(base_year, end_year + 1):
        is_near_term = year < base_year + near_term_years
        
        # Project for each plant
        kc_proj, kc_monthly = project_single_year(db, base_model, base_year, year, 1)
        cc_proj, cc_monthly = project_single_year(db, base_model, base_year, year, 2)
        
        result.kyger_projections.append(kc_proj)
        result.clifty_projections.append(cc_proj)
        
        # Create system projection
        system_proj = AnnualProjection(
            year=year,
            plant_name="System",
            plant_id=None,
            total_mwh=kc_proj.total_mwh + cc_proj.total_mwh,
            avg_capacity_factor=(kc_proj.avg_capacity_factor + cc_proj.avg_capacity_factor) / 2,
            total_coal_tons=kc_proj.total_coal_tons + cc_proj.total_coal_tons,
            total_coal_cost=kc_proj.total_coal_cost + cc_proj.total_coal_cost,
            total_consumables_cost=kc_proj.total_consumables_cost + cc_proj.total_consumables_cost,
            total_byproduct_net=kc_proj.total_byproduct_net + cc_proj.total_byproduct_net,
            total_fuel_cost=kc_proj.total_fuel_cost + cc_proj.total_fuel_cost,
        )
        
        if system_proj.total_mwh > 0:
            system_proj.avg_fuel_cost_per_mwh = system_proj.total_fuel_cost / system_proj.total_mwh
        
        result.system_projections.append(system_proj)
        
        # Store monthly detail for near-term years
        if is_near_term:
            result.near_term_monthly[year] = {
                1: [m.to_dict() for m in kc_monthly],
                2: [m.to_dict() for m in cc_monthly],
            }
    
    return result


# =============================================================================
# Sponsor Projection Format
# =============================================================================

@dataclass
class SponsorProjection:
    """Projection formatted for sponsor reporting.
    
    Years 1-2: Monthly detail
    Years 3+: Annual summary
    """
    start_year: int
    end_year: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Monthly detail for years 1-2
    monthly_detail: Dict[int, List[Dict]] = field(default_factory=dict)
    # Structure: {year: [monthly_dicts for all months]}
    
    # Annual summary for years 3+
    annual_summary: List[Dict] = field(default_factory=list)
    
    # Total across projection period
    total_mwh: float = 0
    total_fuel_cost: float = 0
    avg_fuel_cost_per_mwh: float = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "start_year": self.start_year,
            "end_year": self.end_year,
            "created_at": self.created_at.isoformat(),
            "monthly_detail": self.monthly_detail,
            "annual_summary": self.annual_summary,
            "totals": {
                "total_mwh": self.total_mwh,
                "total_fuel_cost": self.total_fuel_cost,
                "avg_fuel_cost_per_mwh": self.avg_fuel_cost_per_mwh,
            }
        }


def create_sponsor_projection(
    db: Session,
    base_model: FuelModel,
    start_year: int,
    end_year: int = 2040,
) -> SponsorProjection:
    """Create a projection in sponsor reporting format.
    
    Args:
        db: Database session
        base_model: Model with base year driver values
        start_year: Starting year
        end_year: Ending year
        
    Returns:
        SponsorProjection
    """
    result = SponsorProjection(
        start_year=start_year,
        end_year=end_year,
    )
    
    total_mwh = 0
    total_fuel_cost = 0
    
    for year in range(start_year, end_year + 1):
        is_near_term = year < start_year + 2  # First 2 years
        
        # Get system projection
        kc_proj, kc_monthly = project_single_year(db, base_model, start_year, year, 1)
        cc_proj, cc_monthly = project_single_year(db, base_model, start_year, year, 2)
        
        year_mwh = kc_proj.total_mwh + cc_proj.total_mwh
        year_cost = kc_proj.total_fuel_cost + cc_proj.total_fuel_cost
        
        total_mwh += year_mwh
        total_fuel_cost += year_cost
        
        if is_near_term:
            # Monthly detail - combine both plants
            monthly_combined = []
            for i in range(12):
                month = i + 1
                combined = {
                    "month": month,
                    "kyger_mwh": kc_monthly[i].net_delivered_mwh,
                    "clifty_mwh": cc_monthly[i].net_delivered_mwh,
                    "system_mwh": float(kc_monthly[i].net_delivered_mwh + cc_monthly[i].net_delivered_mwh),
                    "kyger_fuel_cost": float(kc_monthly[i].total_fuel_cost),
                    "clifty_fuel_cost": float(cc_monthly[i].total_fuel_cost),
                    "system_fuel_cost": float(kc_monthly[i].total_fuel_cost + cc_monthly[i].total_fuel_cost),
                }
                monthly_combined.append(combined)
            result.monthly_detail[year] = monthly_combined
        else:
            # Annual summary
            result.annual_summary.append({
                "year": year,
                "system_mwh": year_mwh,
                "system_fuel_cost": year_cost,
                "system_fuel_cost_per_mwh": year_cost / year_mwh if year_mwh > 0 else 0,
                "kyger_mwh": kc_proj.total_mwh,
                "clifty_mwh": cc_proj.total_mwh,
            })
    
    result.total_mwh = total_mwh
    result.total_fuel_cost = total_fuel_cost
    result.avg_fuel_cost_per_mwh = total_fuel_cost / total_mwh if total_mwh > 0 else 0
    
    return result



