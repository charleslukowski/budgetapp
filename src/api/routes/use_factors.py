"""
Use Factor API endpoints.

Provides CRUD operations for use factor inputs, supporting:
- Monthly use factors by plant
- Base use factor (normal operations)
- Ozone season use factor for non-SCR units (like Clifty Unit 6)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field
from datetime import datetime

from src.db.postgres import get_session
from src.models.use_factor import (
    UseFactorInput,
    get_use_factors_for_year,
    upsert_use_factor,
)
from src.models.plant import Plant


router = APIRouter(prefix="/api/use-factors", tags=["Use Factors"])


# =============================================================================
# Pydantic Models
# =============================================================================

class UseFactorResponse(BaseModel):
    """Response model for a use factor input."""
    id: int
    plant_id: int
    year: int
    month: int
    use_factor_base: float
    use_factor_ozone_non_scr: float
    notes: Optional[str]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class UseFactorUpdateRequest(BaseModel):
    """Request model for updating a single use factor."""
    use_factor_base: float = Field(ge=0, le=1, description="Base use factor (0-1)")
    use_factor_ozone_non_scr: float = Field(ge=0, le=1, default=0.0, description="Ozone season use factor for non-SCR units (0-1)")
    notes: Optional[str] = None


class MonthlyUseFactorItem(BaseModel):
    """A single monthly use factor value."""
    month: int = Field(ge=1, le=12)
    use_factor_base: float = Field(ge=0, le=1)
    use_factor_ozone_non_scr: float = Field(ge=0, le=1, default=0.0)
    notes: Optional[str] = None


class BulkUseFactorRequest(BaseModel):
    """Request model for bulk updating use factors."""
    values: List[MonthlyUseFactorItem]
    updated_by: Optional[str] = None


class AnnualUseFactorsResponse(BaseModel):
    """Response with all monthly use factors for a year."""
    plant_id: int
    plant_name: str
    year: int
    months: Dict[int, dict]  # month -> {base, ozone_non_scr}


# =============================================================================
# Use Factor Endpoints
# =============================================================================

@router.get("/{plant_id}/{year}", response_model=AnnualUseFactorsResponse)
async def get_annual_use_factors(
    plant_id: int,
    year: int,
):
    """Get all use factors for a plant and year.
    
    Returns a dictionary with month (1-12) as key, containing:
    - use_factor_base: Base use factor for normal operations
    - use_factor_ozone_non_scr: Use factor for non-SCR units during ozone season
    
    Missing months will have default values (0.85 base, 0.0 ozone).
    """
    with get_session() as db:
        # Get plant info
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail=f"Plant not found: {plant_id}")
        
        # Get use factors
        use_factors = get_use_factors_for_year(db, plant_id, year)
        
        # Convert Decimal values to float for JSON
        months = {}
        for month, values in use_factors.items():
            months[month] = {
                "use_factor_base": float(values["base"]),
                "use_factor_ozone_non_scr": float(values["ozone_non_scr"]),
            }
        
        return AnnualUseFactorsResponse(
            plant_id=plant_id,
            plant_name=plant.name,
            year=year,
            months=months,
        )


@router.get("/{plant_id}/{year}/{month}", response_model=UseFactorResponse)
async def get_monthly_use_factor(
    plant_id: int,
    year: int,
    month: int,
):
    """Get use factor for a specific month.
    
    Returns the stored value or defaults if not set.
    """
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be 1-12")
    
    with get_session() as db:
        # Try to get existing record
        existing = db.query(UseFactorInput).filter(
            UseFactorInput.plant_id == plant_id,
            UseFactorInput.year == year,
            UseFactorInput.month == month,
        ).first()
        
        if existing:
            return UseFactorResponse(
                id=existing.id,
                plant_id=existing.plant_id,
                year=existing.year,
                month=existing.month,
                use_factor_base=float(existing.use_factor_base) if existing.use_factor_base else 0.85,
                use_factor_ozone_non_scr=float(existing.use_factor_ozone_non_scr) if existing.use_factor_ozone_non_scr else 0.0,
                notes=existing.notes,
                updated_at=existing.updated_at,
            )
        
        # Return defaults
        return UseFactorResponse(
            id=0,
            plant_id=plant_id,
            year=year,
            month=month,
            use_factor_base=0.85,
            use_factor_ozone_non_scr=0.0,
            notes=None,
            updated_at=None,
        )


@router.put("/{plant_id}/{year}/{month}", response_model=UseFactorResponse)
async def update_monthly_use_factor(
    plant_id: int,
    year: int,
    month: int,
    request: UseFactorUpdateRequest,
    updated_by: Optional[str] = None,
):
    """Update use factor for a specific month.
    
    Creates a new record if one doesn't exist, otherwise updates the existing record.
    """
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be 1-12")
    
    with get_session() as db:
        # Verify plant exists
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail=f"Plant not found: {plant_id}")
        
        # Upsert the value
        result = upsert_use_factor(
            db,
            plant_id=plant_id,
            year=year,
            month=month,
            use_factor_base=request.use_factor_base,
            use_factor_ozone_non_scr=request.use_factor_ozone_non_scr,
            notes=request.notes,
            updated_by=updated_by,
        )
        
        return UseFactorResponse(
            id=result.id,
            plant_id=result.plant_id,
            year=result.year,
            month=result.month,
            use_factor_base=float(result.use_factor_base) if result.use_factor_base else 0.85,
            use_factor_ozone_non_scr=float(result.use_factor_ozone_non_scr) if result.use_factor_ozone_non_scr else 0.0,
            notes=result.notes,
            updated_at=result.updated_at,
        )


@router.post("/bulk/{plant_id}/{year}")
async def bulk_update_use_factors(
    plant_id: int,
    year: int,
    request: BulkUseFactorRequest,
):
    """Bulk update use factors for a year.
    
    Accepts an array of monthly values. Each month's values will be
    created or updated as needed.
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
            
            result = upsert_use_factor(
                db,
                plant_id=plant_id,
                year=year,
                month=item.month,
                use_factor_base=item.use_factor_base,
                use_factor_ozone_non_scr=item.use_factor_ozone_non_scr,
                notes=item.notes,
                updated_by=request.updated_by,
            )
            
            results.append({
                "month": item.month,
                "use_factor_base": float(result.use_factor_base),
                "use_factor_ozone_non_scr": float(result.use_factor_ozone_non_scr),
                "status": "updated",
            })
        
        return {
            "plant_id": plant_id,
            "year": year,
            "updated_count": len(results),
            "results": results,
        }


@router.post("/copy/{plant_id}/{source_year}/{target_year}")
async def copy_use_factors(
    plant_id: int,
    source_year: int,
    target_year: int,
    updated_by: Optional[str] = None,
):
    """Copy use factors from one year to another.
    
    Copies all 12 months of use factors from source_year to target_year.
    Existing values in target_year will be overwritten.
    """
    with get_session() as db:
        # Verify plant exists
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail=f"Plant not found: {plant_id}")
        
        # Get source year values
        source_factors = get_use_factors_for_year(db, plant_id, source_year)
        
        # Copy to target year
        copied = 0
        for month, values in source_factors.items():
            upsert_use_factor(
                db,
                plant_id=plant_id,
                year=target_year,
                month=month,
                use_factor_base=float(values["base"]),
                use_factor_ozone_non_scr=float(values["ozone_non_scr"]),
                updated_by=updated_by,
            )
            copied += 1
        
        return {
            "status": "success",
            "plant_id": plant_id,
            "source_year": source_year,
            "target_year": target_year,
            "months_copied": copied,
        }


@router.delete("/{plant_id}/{year}/{month}")
async def delete_use_factor(
    plant_id: int,
    year: int,
    month: int,
):
    """Delete a use factor record.
    
    After deletion, the month will use default values.
    """
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be 1-12")
    
    with get_session() as db:
        existing = db.query(UseFactorInput).filter(
            UseFactorInput.plant_id == plant_id,
            UseFactorInput.year == year,
            UseFactorInput.month == month,
        ).first()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Use factor not found")
        
        db.delete(existing)
        db.commit()
        
        return {
            "status": "deleted",
            "plant_id": plant_id,
            "year": year,
            "month": month,
        }


@router.delete("/{plant_id}/{year}")
async def delete_year_use_factors(
    plant_id: int,
    year: int,
):
    """Delete all use factor records for a year.
    
    After deletion, all months will use default values.
    """
    with get_session() as db:
        deleted = db.query(UseFactorInput).filter(
            UseFactorInput.plant_id == plant_id,
            UseFactorInput.year == year,
        ).delete()
        
        db.commit()
        
        return {
            "status": "deleted",
            "plant_id": plant_id,
            "year": year,
            "months_deleted": deleted,
        }

