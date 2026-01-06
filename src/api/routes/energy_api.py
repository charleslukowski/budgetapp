"""
Energy model API endpoints.

Exposes the energy calculation engine for:
- Generation (MWh, capacity factors)
- Fuel costs (coal, consumables, byproducts)
- Coal supply and inventory
- System summaries
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from decimal import Decimal
from pydantic import BaseModel

from src.db.postgres import get_session
from src.engine.generation import (
    create_kyger_params,
    create_clifty_params,
    calculate_generation,
    calculate_annual_generation,
    summarize_annual_generation,
    get_system_generation,
    PlantParams,
    UnitParams,
)
from src.engine.coal_burn import (
    calculate_coal_burn,
    calculate_annual_coal_burn,
    summarize_annual_coal_burn,
    create_napp_coal,
    create_ilb_coal,
    HeatRateParams,
    CoalQuality,
)
from src.engine.fuel_model import (
    calculate_fuel_costs,
    calculate_annual_fuel_costs,
    summarize_annual_fuel_costs,
    calculate_system_fuel_costs,
    FuelModelInputs,
)
from src.engine.coal_supply import (
    calculate_coal_supply,
    get_contract_deliveries,
    get_uncommitted_coal,
)

router = APIRouter(prefix="/api/energy", tags=["Energy"])


def get_plant_params(plant_code: str) -> PlantParams:
    """Get plant parameters by code."""
    if plant_code.upper() == "KC":
        return create_kyger_params()
    elif plant_code.upper() == "CC":
        return create_clifty_params()
    else:
        raise HTTPException(status_code=404, detail=f"Unknown plant code: {plant_code}")


def get_plant_id(plant_code: str) -> int:
    """Get plant ID by code."""
    if plant_code.upper() == "KC":
        return 1
    elif plant_code.upper() == "CC":
        return 2
    else:
        raise HTTPException(status_code=404, detail=f"Unknown plant code: {plant_code}")


# ============================================================
# Generation Endpoints
# ============================================================

@router.get("/generation/{plant_code}/{year}")
async def get_generation(
    plant_code: str,
    year: int,
    use_factor: float = 0.85,
):
    """Get annual generation forecast for a plant."""
    plant = get_plant_params(plant_code)
    
    # Create monthly use factors (default for now)
    monthly_use_factors = {m: Decimal(str(use_factor)) for m in range(1, 13)}
    
    results = calculate_annual_generation(plant, year, monthly_use_factors)
    annual_summary = summarize_annual_generation(results)
    
    return {
        "plant": plant_code.upper(),
        "year": year,
        "use_factor": use_factor,
        "monthly": [r.to_dict() for r in results],
        "annual": annual_summary,
    }


@router.get("/generation/{plant_code}/{year}/{month}")
async def get_monthly_generation(
    plant_code: str,
    year: int,
    month: int,
    use_factor: float = 0.85,
):
    """Get generation for a specific month."""
    plant = get_plant_params(plant_code)
    result = calculate_generation(plant, year, month, Decimal(str(use_factor)))
    return result.to_dict()


@router.get("/generation/system/{year}")
async def get_system_generation_summary(year: int):
    """Get combined generation for both plants."""
    result = get_system_generation(year)
    return result


# ============================================================
# Fuel Cost Endpoints
# ============================================================

@router.get("/fuel-costs/{plant_code}/{year}")
async def get_fuel_costs(
    plant_code: str,
    year: int,
    use_factor: float = 0.85,
    coal_price: float = 55.0,
    barge_price: float = 6.0,
):
    """Get annual fuel cost forecast for a plant."""
    plant = get_plant_params(plant_code)
    plant_id = get_plant_id(plant_code)
    
    inputs = FuelModelInputs(
        plant_params=plant,
        use_factor=Decimal(str(use_factor)),
        coal_price_per_ton=Decimal(str(coal_price)),
        barge_price_per_ton=Decimal(str(barge_price)),
    )
    
    with get_session() as db:
        monthly_results = calculate_annual_fuel_costs(db, plant_id, year, inputs)
        annual_summary = summarize_annual_fuel_costs(monthly_results)
    
    return {
        "plant": plant_code.upper(),
        "year": year,
        "inputs": {
            "use_factor": use_factor,
            "coal_price_per_ton": coal_price,
            "barge_price_per_ton": barge_price,
        },
        "monthly": [r.to_dict() for r in monthly_results],
        "annual": annual_summary,
    }


@router.get("/fuel-costs/{plant_code}/{year}/{month}")
async def get_monthly_fuel_costs(
    plant_code: str,
    year: int,
    month: int,
    use_factor: float = 0.85,
):
    """Get fuel costs for a specific month."""
    plant = get_plant_params(plant_code)
    plant_id = get_plant_id(plant_code)
    
    inputs = FuelModelInputs(
        plant_params=plant,
        use_factor=Decimal(str(use_factor)),
    )
    
    with get_session() as db:
        result = calculate_fuel_costs(db, plant_id, year, month, inputs)
    
    return result.to_dict()


@router.get("/fuel-costs/system/{year}")
async def get_system_fuel_costs(year: int):
    """Get combined fuel costs for both plants."""
    with get_session() as db:
        result = calculate_system_fuel_costs(db, year)
    return result


# ============================================================
# Coal Supply Endpoints
# ============================================================

@router.get("/coal-supply/{plant_code}/{year}")
async def get_coal_supply(plant_code: str, year: int):
    """Get annual coal supply summary for a plant."""
    plant_id = get_plant_id(plant_code)
    
    monthly_data = []
    with get_session() as db:
        for month in range(1, 13):
            # Estimate consumption (will be refined with actual generation)
            consumption = Decimal("80000")  # Default estimate
            
            result = calculate_coal_supply(db, plant_id, year, month, consumption)
            monthly_data.append(result.to_dict())
    
    # Calculate annual totals
    total_tons = sum(m["total_tons"] for m in monthly_data)
    total_cost = sum(m["total_cost"] for m in monthly_data)
    avg_cost_per_ton = total_cost / total_tons if total_tons > 0 else 0
    
    return {
        "plant": plant_code.upper(),
        "year": year,
        "monthly": monthly_data,
        "annual": {
            "total_tons": total_tons,
            "total_cost": total_cost,
            "avg_cost_per_ton": avg_cost_per_ton,
        }
    }


@router.get("/coal-supply/{plant_code}/{year}/{month}")
async def get_monthly_coal_supply(plant_code: str, year: int, month: int):
    """Get coal supply for a specific month."""
    plant_id = get_plant_id(plant_code)
    
    with get_session() as db:
        # Get contract deliveries
        period_yyyymm = f"{year}{month:02d}"
        contracts = get_contract_deliveries(db, plant_id, period_yyyymm)
        uncommitted = get_uncommitted_coal(db, plant_id, period_yyyymm)
        
        # Calculate supply
        result = calculate_coal_supply(db, plant_id, year, month, Decimal("80000"))
    
    return {
        **result.to_dict(),
        "contracts": [
            {
                "source_id": s.source_id,
                "supplier": s.supplier,
                "tons": float(s.tons),
                "delivered_cost": float(s.delivered_cost),
            }
            for s in contracts
        ],
        "uncommitted": [
            {
                "source_id": s.source_id,
                "supplier": s.supplier,
                "tons": float(s.tons),
                "delivered_cost": float(s.delivered_cost),
            }
            for s in uncommitted
        ],
    }


# ============================================================
# System Summary Endpoint
# ============================================================

@router.get("/system-summary/{year}")
async def get_system_summary(year: int):
    """Get complete system summary for a year."""
    # Generation
    generation = get_system_generation(year)
    
    # Fuel costs
    with get_session() as db:
        fuel_costs = calculate_system_fuel_costs(db, year)
    
    # Combine into summary
    system_mwh = generation["system"]["net_delivered_mwh"]
    system_fuel_cost = fuel_costs["system"]["total_fuel_cost"]
    
    return {
        "year": year,
        "generation": generation,
        "fuel_costs": fuel_costs,
        "summary": {
            "total_mwh": system_mwh,
            "total_fuel_cost": system_fuel_cost,
            "avg_fuel_cost_per_mwh": system_fuel_cost / system_mwh if system_mwh > 0 else 0,
            "kyger_pct": generation["kyger"]["net_delivered_mwh"] / system_mwh * 100 if system_mwh > 0 else 0,
            "clifty_pct": generation["clifty"]["net_delivered_mwh"] / system_mwh * 100 if system_mwh > 0 else 0,
        }
    }


# ============================================================
# Energy Inputs Endpoint (for saving forecast scenarios)
# ============================================================

class MonthlyUseFactors(BaseModel):
    """Monthly use factors for a year."""
    jan: float = 0.85
    feb: float = 0.85
    mar: float = 0.85
    apr: float = 0.85
    may: float = 0.85
    jun: float = 0.85
    jul: float = 0.85
    aug: float = 0.85
    sep: float = 0.85
    oct: float = 0.85
    nov: float = 0.85
    dec: float = 0.85


class EnergyInputs(BaseModel):
    """Energy forecast input parameters."""
    use_factors: MonthlyUseFactors = MonthlyUseFactors()
    heat_rate_baseline: float = 9850
    heat_rate_suf_correction: float = 0
    coal_price_per_ton: float = 55
    barge_price_per_ton: float = 6
    prb_blend_pct: float = 0
    notes: str = ""


@router.post("/inputs/{plant_code}/{year}")
async def save_energy_inputs(
    plant_code: str,
    year: int,
    inputs: EnergyInputs,
):
    """Save energy forecast inputs and return calculated results."""
    plant = get_plant_params(plant_code)
    plant_id = get_plant_id(plant_code)
    
    # Convert use factors to dict
    use_factors_dict = {
        1: Decimal(str(inputs.use_factors.jan)),
        2: Decimal(str(inputs.use_factors.feb)),
        3: Decimal(str(inputs.use_factors.mar)),
        4: Decimal(str(inputs.use_factors.apr)),
        5: Decimal(str(inputs.use_factors.may)),
        6: Decimal(str(inputs.use_factors.jun)),
        7: Decimal(str(inputs.use_factors.jul)),
        8: Decimal(str(inputs.use_factors.aug)),
        9: Decimal(str(inputs.use_factors.sep)),
        10: Decimal(str(inputs.use_factors.oct)),
        11: Decimal(str(inputs.use_factors.nov)),
        12: Decimal(str(inputs.use_factors.dec)),
    }
    
    # Calculate generation with these inputs
    generation_results = calculate_annual_generation(plant, year, use_factors_dict)
    
    # Create fuel model inputs
    fuel_inputs = FuelModelInputs(
        plant_params=plant,
        heat_rate_params=HeatRateParams(
            baseline_heat_rate=Decimal(str(inputs.heat_rate_baseline)),
            suf_correction=Decimal(str(inputs.heat_rate_suf_correction)),
            prb_blend_pct=Decimal(str(inputs.prb_blend_pct)),
        ),
        coal_price_per_ton=Decimal(str(inputs.coal_price_per_ton)),
        barge_price_per_ton=Decimal(str(inputs.barge_price_per_ton)),
    )
    
    # Calculate fuel costs
    with get_session() as db:
        fuel_results = []
        for month in range(1, 13):
            fuel_inputs.use_factor = use_factors_dict[month]
            result = calculate_fuel_costs(db, plant_id, year, month, fuel_inputs)
            fuel_results.append(result)
    
    annual_summary = summarize_annual_fuel_costs(fuel_results)
    
    return {
        "plant": plant_code.upper(),
        "year": year,
        "inputs_saved": inputs.dict(),
        "generation": summarize_annual_generation(generation_results),
        "fuel_costs": annual_summary,
        "monthly": [r.to_dict() for r in fuel_results],
    }

