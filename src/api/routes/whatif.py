"""API routes for what-if analysis.

Provides instant calculation of scenario variations:
- Quick toggles for common what-if questions
- Real-time cost delta preview
- Sensitivity analysis
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict
from decimal import Decimal
from pydantic import BaseModel, Field
from datetime import datetime

from src.db.postgres import get_session
from src.engine.fuel_model import load_inputs_from_db, calculate_fuel_costs
from src.engine.generation import calculate_generation


router = APIRouter(prefix="/api/whatif", tags=["What-If Analysis"])


# =============================================================================
# Pydantic Models
# =============================================================================

class WhatIfRequest(BaseModel):
    """Request for a what-if calculation."""
    year: int
    month: int = 1  # Can analyze a specific month or annual
    
    # Variations to apply
    variations: List[Dict]  # [{type: "outage", unit: 6, month: 6, days: 30}, ...]


class WhatIfVariation(BaseModel):
    """A single what-if variation."""
    variation_type: str  # "outage", "use_factor", "heat_rate", "coal_price"
    plant_id: int
    description: str
    
    # Type-specific parameters
    unit: Optional[int] = None
    month: Optional[int] = None
    value: float


class WhatIfResult(BaseModel):
    """Result of a what-if calculation."""
    base_cost: float
    modified_cost: float
    delta: float
    delta_pct: float
    base_generation_mwh: float
    modified_generation_mwh: float
    generation_delta_mwh: float
    description: str


class QuickWhatIfRequest(BaseModel):
    """Request for a quick what-if scenario."""
    year: int
    scenario_type: str  # "extended_outage", "higher_use_factor", "coal_price_increase", etc.
    
    # Optional parameters
    plant_id: Optional[int] = None
    unit: Optional[int] = None
    month: Optional[int] = None
    value: Optional[float] = None


# =============================================================================
# What-If Calculation
# =============================================================================

def calculate_base_costs(year: int, month: int = None) -> Dict:
    """Calculate base case costs for a year/month."""
    with get_session() as db:
        total_cost = Decimal("0")
        total_mwh = Decimal("0")
        
        months = [month] if month else range(1, 13)
        
        for m in months:
            for plant_id in [1, 2]:
                inputs = load_inputs_from_db(db, plant_id, year, m)
                gen = calculate_generation(inputs.plant_params, inputs.use_factor, m)
                result = calculate_fuel_costs(inputs, gen, m)
                
                total_cost += result.total_fuel_cost
                total_mwh += gen.net_generation
        
        return {
            "total_cost": float(total_cost),
            "total_mwh": float(total_mwh),
            "cost_per_mwh": float(total_cost / total_mwh) if total_mwh > 0 else 0,
        }


def calculate_with_variation(year: int, variation: Dict, month: int = None) -> Dict:
    """Calculate costs with a specific variation applied."""
    from src.models.unit_outage import upsert_unit_outage, get_unit_outage_for_month
    from src.models.use_factor import upsert_use_factor, get_use_factors_for_year
    
    var_type = variation.get("type")
    plant_id = variation.get("plant_id", 2)  # Default to Clifty
    
    with get_session() as db:
        total_cost = Decimal("0")
        total_mwh = Decimal("0")
        
        months_to_calc = [month] if month else range(1, 13)
        
        for m in months_to_calc:
            for pid in [1, 2]:
                inputs = load_inputs_from_db(db, pid, year, m)
                
                # Apply variation if it's for this plant/month
                if pid == plant_id:
                    if var_type == "outage":
                        var_month = variation.get("month", m)
                        var_unit = variation.get("unit", 1)
                        var_days = Decimal(str(variation.get("days", 30)))
                        
                        if m == var_month:
                            # Temporarily modify unit availability
                            for unit in inputs.plant_params.units:
                                if unit.unit_number == var_unit:
                                    # Reduce availability based on outage days
                                    days_in_month = 30  # Approximate
                                    outage_factor = var_days / Decimal(str(days_in_month))
                                    unit.availability_factor = max(Decimal("0"), Decimal("1") - outage_factor)
                    
                    elif var_type == "use_factor":
                        var_value = Decimal(str(variation.get("value", 0.85)))
                        inputs.use_factor = var_value
                    
                    elif var_type == "heat_rate":
                        var_value = Decimal(str(variation.get("value", 9850)))
                        inputs.heat_rate_params.baseline_heat_rate = var_value
                    
                    elif var_type == "coal_price":
                        var_value = Decimal(str(variation.get("value", 60)))
                        inputs.coal_price_per_ton = var_value
                
                gen = calculate_generation(inputs.plant_params, inputs.use_factor, m)
                result = calculate_fuel_costs(inputs, gen, m)
                
                total_cost += result.total_fuel_cost
                total_mwh += gen.net_generation
        
        return {
            "total_cost": float(total_cost),
            "total_mwh": float(total_mwh),
            "cost_per_mwh": float(total_cost / total_mwh) if total_mwh > 0 else 0,
        }


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/calculate", response_model=WhatIfResult)
async def calculate_whatif(request: WhatIfRequest):
    """Calculate the impact of specified variations.
    
    Compares base case to modified case and returns the delta.
    """
    try:
        # Calculate base case
        base = calculate_base_costs(request.year, request.month if request.month != 1 else None)
        
        # Apply each variation and calculate
        modified = base.copy()
        descriptions = []
        
        for var in request.variations:
            modified = calculate_with_variation(
                request.year,
                var,
                request.month if request.month != 1 else None
            )
            descriptions.append(var.get("description", f"{var.get('type')} change"))
        
        delta = modified["total_cost"] - base["total_cost"]
        delta_pct = (delta / base["total_cost"] * 100) if base["total_cost"] > 0 else 0
        
        return WhatIfResult(
            base_cost=base["total_cost"],
            modified_cost=modified["total_cost"],
            delta=delta,
            delta_pct=delta_pct,
            base_generation_mwh=base["total_mwh"],
            modified_generation_mwh=modified["total_mwh"],
            generation_delta_mwh=modified["total_mwh"] - base["total_mwh"],
            description="; ".join(descriptions) if descriptions else "Custom variation",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick/{scenario_type}")
async def quick_whatif(scenario_type: str, request: QuickWhatIfRequest):
    """Quick what-if scenarios for common questions.
    
    Supported scenarios:
    - extended_outage: What if a unit has an extended outage?
    - higher_use_factor: What if use factors increase 5%?
    - lower_use_factor: What if use factors decrease 5%?
    - coal_price_increase: What if coal prices rise $5/ton?
    - coal_price_decrease: What if coal prices fall $5/ton?
    - heat_rate_improvement: What if heat rates improve 100 BTU/kWh?
    - unit6_summer_run: What if Unit 6 runs during ozone season?
    """
    
    # Define quick scenarios
    quick_scenarios = {
        "extended_outage": {
            "type": "outage",
            "plant_id": request.plant_id or 2,
            "unit": request.unit or 6,
            "month": request.month or 6,
            "days": request.value or 30,
            "description": f"Unit {request.unit or 6} extended outage ({request.value or 30} days)",
        },
        "higher_use_factor": {
            "type": "use_factor",
            "plant_id": request.plant_id or 1,
            "value": 0.90,
            "description": "Higher use factor (90%)",
        },
        "lower_use_factor": {
            "type": "use_factor",
            "plant_id": request.plant_id or 1,
            "value": 0.75,
            "description": "Lower use factor (75%)",
        },
        "coal_price_increase": {
            "type": "coal_price",
            "plant_id": request.plant_id or 1,
            "value": (request.value or 66),
            "description": f"Coal price +$5/ton (${request.value or 66}/ton)",
        },
        "coal_price_decrease": {
            "type": "coal_price",
            "plant_id": request.plant_id or 1,
            "value": (request.value or 56),
            "description": f"Coal price -$5/ton (${request.value or 56}/ton)",
        },
        "heat_rate_improvement": {
            "type": "heat_rate",
            "plant_id": request.plant_id or 1,
            "value": 9750,
            "description": "Heat rate improvement (-100 BTU/kWh)",
        },
        "unit6_summer_run": {
            "type": "use_factor",
            "plant_id": 2,
            "value": 0.50,  # Unit 6 running at 50% during summer
            "description": "Clifty Unit 6 runs during ozone season (50% capacity)",
        },
    }
    
    if scenario_type not in quick_scenarios:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario type: {scenario_type}. "
                   f"Available: {', '.join(quick_scenarios.keys())}"
        )
    
    variation = quick_scenarios[scenario_type]
    
    try:
        # Calculate base case
        base = calculate_base_costs(request.year)
        
        # Calculate with variation
        modified = calculate_with_variation(request.year, variation)
        
        delta = modified["total_cost"] - base["total_cost"]
        delta_pct = (delta / base["total_cost"] * 100) if base["total_cost"] > 0 else 0
        
        return {
            "scenario_type": scenario_type,
            "description": variation["description"],
            "year": request.year,
            "base_case": base,
            "modified_case": modified,
            "delta": {
                "cost": delta,
                "cost_pct": delta_pct,
                "mwh": modified["total_mwh"] - base["total_mwh"],
            },
            "impact_summary": f"{'Increases' if delta > 0 else 'Decreases'} annual cost by ${abs(delta):,.0f} ({abs(delta_pct):.1f}%)",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/presets")
async def list_whatif_presets():
    """List available quick what-if presets."""
    return {
        "presets": [
            {
                "id": "extended_outage",
                "name": "Extended Unit Outage",
                "description": "What if a unit has a 30-day extended outage?",
                "parameters": ["plant_id", "unit", "month", "days"],
            },
            {
                "id": "higher_use_factor",
                "name": "Higher Use Factor",
                "description": "What if use factors increase to 90%?",
                "parameters": ["plant_id"],
            },
            {
                "id": "lower_use_factor",
                "name": "Lower Use Factor",
                "description": "What if use factors decrease to 75%?",
                "parameters": ["plant_id"],
            },
            {
                "id": "coal_price_increase",
                "name": "Coal Price Increase",
                "description": "What if coal prices rise $5/ton?",
                "parameters": ["value"],
            },
            {
                "id": "coal_price_decrease",
                "name": "Coal Price Decrease",
                "description": "What if coal prices fall $5/ton?",
                "parameters": ["value"],
            },
            {
                "id": "heat_rate_improvement",
                "name": "Heat Rate Improvement",
                "description": "What if heat rates improve 100 BTU/kWh?",
                "parameters": ["plant_id"],
            },
            {
                "id": "unit6_summer_run",
                "name": "Unit 6 Summer Operation",
                "description": "What if Clifty Unit 6 runs at 50% during ozone season?",
                "parameters": [],
            },
        ]
    }

