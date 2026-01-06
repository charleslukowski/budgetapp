"""
Heat Rate API endpoints.

Provides CRUD operations for heat rate inputs, supporting:
- Plant-level heat rate configuration
- Optional unit-level overrides
- Heat rate curve parameters (min load, SUF correction, PRB adjustment)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field
from datetime import datetime

from src.db.postgres import get_session
from src.models.heat_rate import (
    HeatRateInput,
    get_heat_rate_for_month,
    get_heat_rates_for_year,
    upsert_heat_rate,
)
from src.models.plant import Plant


router = APIRouter(prefix="/api/heat-rates", tags=["Heat Rates"])


# =============================================================================
# Pydantic Models
# =============================================================================

class HeatRateResponse(BaseModel):
    """Response model for a heat rate input."""
    id: int
    plant_id: int
    unit_number: Optional[int]
    year: int
    month: int
    baseline_heat_rate: float
    min_load_heat_rate: Optional[float]
    suf_correction: float
    prb_blend_adjustment: float
    notes: Optional[str]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class HeatRateUpdateRequest(BaseModel):
    """Request model for updating a heat rate."""
    baseline_heat_rate: float = Field(gt=0, description="Baseline heat rate at full load (BTU/kWh)")
    min_load_heat_rate: Optional[float] = Field(None, gt=0, description="Heat rate at min load (BTU/kWh)")
    suf_correction: float = Field(0, description="SUF adjustment factor")
    prb_blend_adjustment: float = Field(0, description="PRB blend adjustment factor")
    notes: Optional[str] = None


class MonthlyHeatRateItem(BaseModel):
    """A single monthly heat rate value."""
    month: int = Field(ge=1, le=12)
    baseline_heat_rate: float = Field(gt=0)
    min_load_heat_rate: Optional[float] = Field(None, gt=0)
    suf_correction: float = 0
    prb_blend_adjustment: float = 0
    unit_number: Optional[int] = None  # None = plant-level
    notes: Optional[str] = None


class BulkHeatRateRequest(BaseModel):
    """Request model for bulk updating heat rates."""
    values: List[MonthlyHeatRateItem]
    updated_by: Optional[str] = None


class MonthHeatRates(BaseModel):
    """Heat rates for a single month (plant + units)."""
    plant: dict
    units: Dict[int, dict]


class AnnualHeatRatesResponse(BaseModel):
    """Response with all monthly heat rates for a year."""
    plant_id: int
    plant_name: str
    year: int
    months: Dict[int, MonthHeatRates]


# =============================================================================
# Heat Rate Endpoints
# =============================================================================

@router.get("/{plant_id}/{year}", response_model=AnnualHeatRatesResponse)
async def get_annual_heat_rates(
    plant_id: int,
    year: int,
):
    """Get all heat rates for a plant and year.
    
    Returns plant-level and unit-level heat rates for each month.
    Missing months/units will have default values (9850 BTU/kWh baseline).
    """
    with get_session() as db:
        # Get plant info
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail=f"Plant not found: {plant_id}")
        
        # Get heat rates
        heat_rates = get_heat_rates_for_year(db, plant_id, year)
        
        # Convert Decimal values to float for JSON
        months = {}
        for month, values in heat_rates.items():
            plant_hr = values["plant"]
            months[month] = MonthHeatRates(
                plant={
                    "baseline_heat_rate": float(plant_hr["baseline_heat_rate"]) if plant_hr["baseline_heat_rate"] else 9850,
                    "min_load_heat_rate": float(plant_hr["min_load_heat_rate"]) if plant_hr["min_load_heat_rate"] else None,
                    "suf_correction": float(plant_hr["suf_correction"]) if plant_hr["suf_correction"] else 0,
                    "prb_blend_adjustment": float(plant_hr["prb_blend_adjustment"]) if plant_hr["prb_blend_adjustment"] else 0,
                },
                units={
                    unit_num: {
                        "baseline_heat_rate": float(unit_hr["baseline_heat_rate"]) if unit_hr["baseline_heat_rate"] else 9850,
                        "min_load_heat_rate": float(unit_hr["min_load_heat_rate"]) if unit_hr["min_load_heat_rate"] else None,
                        "suf_correction": float(unit_hr["suf_correction"]) if unit_hr["suf_correction"] else 0,
                        "prb_blend_adjustment": float(unit_hr["prb_blend_adjustment"]) if unit_hr["prb_blend_adjustment"] else 0,
                    }
                    for unit_num, unit_hr in values["units"].items()
                },
            )
        
        return AnnualHeatRatesResponse(
            plant_id=plant_id,
            plant_name=plant.name,
            year=year,
            months=months,
        )


@router.get("/{plant_id}/{year}/{month}")
async def get_monthly_heat_rate(
    plant_id: int,
    year: int,
    month: int,
    unit_number: Optional[int] = None,
):
    """Get heat rate for a specific month and optionally unit.
    
    Priority:
    1. Unit-specific value (if unit_number provided and exists)
    2. Plant-level value
    3. Default values
    """
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be 1-12")
    
    with get_session() as db:
        result = get_heat_rate_for_month(db, plant_id, year, month, unit_number)
        
        return {
            "plant_id": plant_id,
            "year": year,
            "month": month,
            "unit_number": unit_number,
            "baseline_heat_rate": float(result["baseline_heat_rate"]),
            "min_load_heat_rate": float(result["min_load_heat_rate"]) if result["min_load_heat_rate"] else None,
            "suf_correction": float(result["suf_correction"]),
            "prb_blend_adjustment": float(result["prb_blend_adjustment"]),
            "source": result["source"],
        }


@router.put("/{plant_id}/{year}/{month}", response_model=HeatRateResponse)
async def update_monthly_heat_rate(
    plant_id: int,
    year: int,
    month: int,
    request: HeatRateUpdateRequest,
    unit_number: Optional[int] = None,
    updated_by: Optional[str] = None,
):
    """Update heat rate for a specific month.
    
    Creates a new record if one doesn't exist, otherwise updates.
    Use unit_number to set unit-level overrides.
    """
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be 1-12")
    
    with get_session() as db:
        # Verify plant exists
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail=f"Plant not found: {plant_id}")
        
        # Upsert the value
        result = upsert_heat_rate(
            db,
            plant_id=plant_id,
            year=year,
            month=month,
            baseline_heat_rate=request.baseline_heat_rate,
            min_load_heat_rate=request.min_load_heat_rate,
            suf_correction=request.suf_correction,
            prb_blend_adjustment=request.prb_blend_adjustment,
            unit_number=unit_number,
            notes=request.notes,
            updated_by=updated_by,
        )
        
        return HeatRateResponse(
            id=result.id,
            plant_id=result.plant_id,
            unit_number=result.unit_number,
            year=result.year,
            month=result.month,
            baseline_heat_rate=float(result.baseline_heat_rate) if result.baseline_heat_rate else 9850,
            min_load_heat_rate=float(result.min_load_heat_rate) if result.min_load_heat_rate else None,
            suf_correction=float(result.suf_correction) if result.suf_correction else 0,
            prb_blend_adjustment=float(result.prb_blend_adjustment) if result.prb_blend_adjustment else 0,
            notes=result.notes,
            updated_at=result.updated_at,
        )


@router.post("/bulk/{plant_id}/{year}")
async def bulk_update_heat_rates(
    plant_id: int,
    year: int,
    request: BulkHeatRateRequest,
):
    """Bulk update heat rates for a year.
    
    Accepts an array of monthly values. Can include both plant-level
    and unit-level values.
    """
    with get_session() as db:
        # Verify plant exists
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail=f"Plant not found: {plant_id}")
        
        results = []
        for item in request.values:
            if item.month < 1 or item.month > 12:
                continue
            
            result = upsert_heat_rate(
                db,
                plant_id=plant_id,
                year=year,
                month=item.month,
                baseline_heat_rate=item.baseline_heat_rate,
                min_load_heat_rate=item.min_load_heat_rate,
                suf_correction=item.suf_correction,
                prb_blend_adjustment=item.prb_blend_adjustment,
                unit_number=item.unit_number,
                notes=item.notes,
                updated_by=request.updated_by,
            )
            
            results.append({
                "month": item.month,
                "unit_number": item.unit_number,
                "baseline_heat_rate": float(result.baseline_heat_rate),
                "status": "updated",
            })
        
        return {
            "plant_id": plant_id,
            "year": year,
            "updated_count": len(results),
            "results": results,
        }


@router.post("/copy/{plant_id}/{source_year}/{target_year}")
async def copy_heat_rates(
    plant_id: int,
    source_year: int,
    target_year: int,
    include_unit_level: bool = True,
    updated_by: Optional[str] = None,
):
    """Copy heat rates from one year to another.
    
    Copies all heat rates (plant and optionally unit-level) from source_year to target_year.
    Existing values in target_year will be overwritten.
    """
    with get_session() as db:
        # Verify plant exists
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail=f"Plant not found: {plant_id}")
        
        # Get source year records
        query = db.query(HeatRateInput).filter(
            HeatRateInput.plant_id == plant_id,
            HeatRateInput.year == source_year,
        )
        if not include_unit_level:
            query = query.filter(HeatRateInput.unit_number.is_(None))
        
        source_records = query.all()
        
        # Copy to target year
        copied = 0
        for record in source_records:
            upsert_heat_rate(
                db,
                plant_id=plant_id,
                year=target_year,
                month=record.month,
                baseline_heat_rate=float(record.baseline_heat_rate),
                min_load_heat_rate=float(record.min_load_heat_rate) if record.min_load_heat_rate else None,
                suf_correction=float(record.suf_correction),
                prb_blend_adjustment=float(record.prb_blend_adjustment),
                unit_number=record.unit_number,
                updated_by=updated_by,
            )
            copied += 1
        
        return {
            "status": "success",
            "plant_id": plant_id,
            "source_year": source_year,
            "target_year": target_year,
            "records_copied": copied,
        }


@router.delete("/{plant_id}/{year}/{month}")
async def delete_heat_rate(
    plant_id: int,
    year: int,
    month: int,
    unit_number: Optional[int] = None,
):
    """Delete a heat rate record.
    
    After deletion, the month/unit will use defaults or plant-level values.
    """
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be 1-12")
    
    with get_session() as db:
        query = db.query(HeatRateInput).filter(
            HeatRateInput.plant_id == plant_id,
            HeatRateInput.year == year,
            HeatRateInput.month == month,
        )
        
        if unit_number is not None:
            query = query.filter(HeatRateInput.unit_number == unit_number)
        else:
            query = query.filter(HeatRateInput.unit_number.is_(None))
        
        existing = query.first()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Heat rate not found")
        
        db.delete(existing)
        db.commit()
        
        return {
            "status": "deleted",
            "plant_id": plant_id,
            "year": year,
            "month": month,
            "unit_number": unit_number,
        }


@router.delete("/{plant_id}/{year}")
async def delete_year_heat_rates(
    plant_id: int,
    year: int,
    include_unit_level: bool = True,
):
    """Delete all heat rate records for a year.
    
    After deletion, all months/units will use default values.
    """
    with get_session() as db:
        query = db.query(HeatRateInput).filter(
            HeatRateInput.plant_id == plant_id,
            HeatRateInput.year == year,
        )
        
        if not include_unit_level:
            query = query.filter(HeatRateInput.unit_number.is_(None))
        
        deleted = query.delete()
        db.commit()
        
        return {
            "status": "deleted",
            "plant_id": plant_id,
            "year": year,
            "records_deleted": deleted,
        }

