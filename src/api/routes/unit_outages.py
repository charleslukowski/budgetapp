"""API routes for unit outage management.

Provides CRUD operations for unit-level outage tracking:
- Monthly planned/forced outage days per unit
- Availability and EFOR calculations
- Bulk operations for annual planning
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field
from datetime import datetime

from src.db.postgres import get_session
from src.models.unit_outage import (
    UnitOutageInput,
    get_unit_outages_for_period,
    get_unit_outages_for_year,
    get_unit_outage,
    upsert_unit_outage,
    calculate_unit_availability,
    calculate_plant_availability,
    get_annual_outage_summary,
    build_unit_availability_from_db,
)
from src.models.plant import Plant


router = APIRouter(prefix="/api/unit-outages", tags=["Unit Outages"])


# =============================================================================
# Pydantic Models
# =============================================================================

class UnitOutageResponse(BaseModel):
    """Response model for a unit outage record."""
    id: int
    plant_id: int
    unit_number: int
    year: int
    month: int
    planned_outage_days: float
    forced_outage_days: float
    reserve_shutdown_days: float
    outage_type: Optional[str]
    outage_description: Optional[str]
    notes: Optional[str]
    updated_at: Optional[datetime]
    
    # Calculated fields
    total_outage_days: float
    availability_factor: float
    efor: float

    class Config:
        from_attributes = True


class UnitOutageUpdateRequest(BaseModel):
    """Request model for updating a unit outage."""
    planned_outage_days: float = Field(ge=0, le=31, default=0)
    forced_outage_days: float = Field(ge=0, le=31, default=0)
    reserve_shutdown_days: float = Field(ge=0, le=31, default=0)
    outage_type: Optional[str] = None
    outage_description: Optional[str] = None
    notes: Optional[str] = None


class MonthlyUnitOutageItem(BaseModel):
    """A single monthly outage entry."""
    unit_number: int = Field(ge=1, le=6)
    month: int = Field(ge=1, le=12)
    planned_outage_days: float = Field(ge=0, le=31, default=0)
    forced_outage_days: float = Field(ge=0, le=31, default=0)
    reserve_shutdown_days: float = Field(ge=0, le=31, default=0)
    outage_type: Optional[str] = None
    outage_description: Optional[str] = None
    notes: Optional[str] = None


class BulkOutageRequest(BaseModel):
    """Request model for bulk updating outages."""
    values: List[MonthlyUnitOutageItem]
    updated_by: Optional[str] = None


class PlantAvailabilityResponse(BaseModel):
    """Response with plant-level availability metrics."""
    plant_id: int
    plant_name: str
    year: int
    month: int
    weighted_availability: float
    weighted_efor: float
    total_outage_days: float
    unit_details: Dict[int, dict]


class AnnualOutageSummaryResponse(BaseModel):
    """Response with annual outage summary."""
    plant_id: int
    plant_name: str
    year: int
    total_planned_days: float
    total_forced_days: float
    total_reserve_days: float
    total_outage_days: float
    unit_totals: Dict[int, dict]
    monthly_summary: Dict[int, dict]


# =============================================================================
# Helper Functions
# =============================================================================

def _to_outage_response(outage: UnitOutageInput) -> UnitOutageResponse:
    """Convert database record to response model with calculated fields."""
    metrics = calculate_unit_availability(outage, outage.year, outage.month)
    
    return UnitOutageResponse(
        id=outage.id,
        plant_id=outage.plant_id,
        unit_number=outage.unit_number,
        year=outage.year,
        month=outage.month,
        planned_outage_days=float(outage.planned_outage_days or 0),
        forced_outage_days=float(outage.forced_outage_days or 0),
        reserve_shutdown_days=float(outage.reserve_shutdown_days or 0),
        outage_type=outage.outage_type,
        outage_description=outage.outage_description,
        notes=outage.notes,
        updated_at=outage.updated_at,
        total_outage_days=float(outage.total_outage_days),
        availability_factor=float(metrics["availability_factor"]),
        efor=float(metrics["efor"]),
    )


# =============================================================================
# Unit Outage Endpoints
# =============================================================================

@router.get("/{plant_id}/{year}", response_model=List[UnitOutageResponse])
async def get_annual_unit_outages(
    plant_id: int,
    year: int,
    unit_number: Optional[int] = None,
):
    """Get all unit outages for a plant and year.
    
    Optionally filter by unit number.
    Returns list of outage records with calculated availability metrics.
    """
    with get_session() as db:
        # Verify plant exists
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail=f"Plant not found: {plant_id}")
        
        outages = get_unit_outages_for_year(db, plant_id, year, unit_number)
        return [_to_outage_response(o) for o in outages]


@router.get("/{plant_id}/{year}/{month}", response_model=List[UnitOutageResponse])
async def get_monthly_unit_outages(
    plant_id: int,
    year: int,
    month: int,
):
    """Get all unit outages for a plant/month.
    
    Returns outage records for each unit in the plant.
    """
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be 1-12")
    
    with get_session() as db:
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail=f"Plant not found: {plant_id}")
        
        outages = get_unit_outages_for_period(db, plant_id, year, month)
        return [_to_outage_response(o) for o in outages]


@router.get("/{plant_id}/{year}/{month}/unit/{unit_number}", response_model=UnitOutageResponse)
async def get_unit_outage_detail(
    plant_id: int,
    year: int,
    month: int,
    unit_number: int,
):
    """Get outage details for a specific unit/month.
    
    Returns the outage record with calculated availability metrics.
    Creates a default (zero outage) response if no record exists.
    """
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be 1-12")
    
    with get_session() as db:
        outage = get_unit_outage(db, plant_id, unit_number, year, month)
        
        if outage:
            return _to_outage_response(outage)
        
        # Return default response for non-existent record
        from src.models.unit_outage import calculate_unit_availability as calc_avail
        
        # Create a dummy outage for calculation
        dummy = UnitOutageInput(
            plant_id=plant_id,
            unit_number=unit_number,
            year=year,
            month=month,
            planned_outage_days=Decimal("0"),
            forced_outage_days=Decimal("0"),
            reserve_shutdown_days=Decimal("0"),
        )
        metrics = calc_avail(dummy, year, month)
        
        return UnitOutageResponse(
            id=0,
            plant_id=plant_id,
            unit_number=unit_number,
            year=year,
            month=month,
            planned_outage_days=0,
            forced_outage_days=0,
            reserve_shutdown_days=0,
            outage_type=None,
            outage_description=None,
            notes=None,
            updated_at=None,
            total_outage_days=0,
            availability_factor=float(metrics["availability_factor"]),
            efor=float(metrics["efor"]),
        )


@router.put("/{plant_id}/{year}/{month}/unit/{unit_number}", response_model=UnitOutageResponse)
async def update_unit_outage(
    plant_id: int,
    year: int,
    month: int,
    unit_number: int,
    request: UnitOutageUpdateRequest,
    updated_by: Optional[str] = None,
):
    """Update outage record for a specific unit/month.
    
    Creates a new record if one doesn't exist.
    """
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be 1-12")
    
    with get_session() as db:
        # Verify plant exists
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail=f"Plant not found: {plant_id}")
        
        result = upsert_unit_outage(
            db,
            plant_id=plant_id,
            unit_number=unit_number,
            year=year,
            month=month,
            planned_outage_days=Decimal(str(request.planned_outage_days)),
            forced_outage_days=Decimal(str(request.forced_outage_days)),
            reserve_shutdown_days=Decimal(str(request.reserve_shutdown_days)),
            outage_type=request.outage_type,
            outage_description=request.outage_description,
            notes=request.notes,
            updated_by=updated_by,
        )
        
        return _to_outage_response(result)


@router.post("/bulk/{plant_id}/{year}")
async def bulk_update_unit_outages(
    plant_id: int,
    year: int,
    request: BulkOutageRequest,
):
    """Bulk update outages for multiple units/months.
    
    Accepts an array of unit-month outage values.
    Creates or updates records as needed.
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
            
            result = upsert_unit_outage(
                db,
                plant_id=plant_id,
                unit_number=item.unit_number,
                year=year,
                month=item.month,
                planned_outage_days=Decimal(str(item.planned_outage_days)),
                forced_outage_days=Decimal(str(item.forced_outage_days)),
                reserve_shutdown_days=Decimal(str(item.reserve_shutdown_days)),
                outage_type=item.outage_type,
                outage_description=item.outage_description,
                notes=item.notes,
                updated_by=request.updated_by,
            )
            
            results.append({
                "unit_number": item.unit_number,
                "month": item.month,
                "planned_days": float(result.planned_outage_days),
                "forced_days": float(result.forced_outage_days),
                "status": "updated",
            })
        
        return {
            "plant_id": plant_id,
            "year": year,
            "updated_count": len(results),
            "results": results,
        }


@router.post("/copy/{plant_id}/{source_year}/{target_year}")
async def copy_unit_outages(
    plant_id: int,
    source_year: int,
    target_year: int,
    updated_by: Optional[str] = None,
):
    """Copy outages from one year to another.
    
    Copies all unit outage records from source_year to target_year.
    Existing records in target_year will be overwritten.
    """
    with get_session() as db:
        # Verify plant exists
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail=f"Plant not found: {plant_id}")
        
        # Get source year records
        source_outages = get_unit_outages_for_year(db, plant_id, source_year)
        
        copied = 0
        for outage in source_outages:
            upsert_unit_outage(
                db,
                plant_id=plant_id,
                unit_number=outage.unit_number,
                year=target_year,
                month=outage.month,
                planned_outage_days=outage.planned_outage_days,
                forced_outage_days=outage.forced_outage_days,
                reserve_shutdown_days=outage.reserve_shutdown_days,
                outage_type=outage.outage_type,
                outage_description=outage.outage_description,
                notes=f"Copied from {source_year}",
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


@router.delete("/{plant_id}/{year}/{month}/unit/{unit_number}")
async def delete_unit_outage(
    plant_id: int,
    year: int,
    month: int,
    unit_number: int,
):
    """Delete an outage record.
    
    After deletion, the unit will be considered fully available.
    """
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be 1-12")
    
    with get_session() as db:
        existing = get_unit_outage(db, plant_id, unit_number, year, month)
        
        if not existing:
            raise HTTPException(status_code=404, detail="Outage record not found")
        
        db.delete(existing)
        db.commit()
        
        return {
            "status": "deleted",
            "plant_id": plant_id,
            "unit_number": unit_number,
            "year": year,
            "month": month,
        }


@router.delete("/{plant_id}/{year}")
async def delete_year_outages(
    plant_id: int,
    year: int,
    unit_number: Optional[int] = None,
):
    """Delete all outage records for a year.
    
    Optionally filter by unit number.
    After deletion, units will be considered fully available.
    """
    with get_session() as db:
        query = db.query(UnitOutageInput).filter(
            UnitOutageInput.plant_id == plant_id,
            UnitOutageInput.year == year,
        )
        
        if unit_number is not None:
            query = query.filter(UnitOutageInput.unit_number == unit_number)
        
        deleted = query.delete()
        db.commit()
        
        return {
            "status": "deleted",
            "plant_id": plant_id,
            "year": year,
            "unit_number": unit_number,
            "records_deleted": deleted,
        }


# =============================================================================
# Availability/EFOR Summary Endpoints
# =============================================================================

@router.get("/{plant_id}/{year}/{month}/availability", response_model=PlantAvailabilityResponse)
async def get_plant_availability(
    plant_id: int,
    year: int,
    month: int,
):
    """Get plant-level availability metrics for a month.
    
    Returns capacity-weighted availability and EFOR based on unit outages.
    """
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be 1-12")
    
    with get_session() as db:
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail=f"Plant not found: {plant_id}")
        
        # Get unit capacities - using standard OVEC unit sizes
        # Kyger: 5 units x 205 MW, Clifty: 6 units x 205 MW
        if plant_id == 1:  # Kyger Creek
            num_units = 5
        else:  # Clifty Creek
            num_units = 6
        
        unit_capacities = {i: Decimal("205") for i in range(1, num_units + 1)}
        
        # Get outages
        outages = get_unit_outages_for_period(db, plant_id, year, month)
        
        # Calculate plant availability
        plant_metrics = calculate_plant_availability(outages, year, month, unit_capacities)
        
        # Get unit-level details
        unit_details = {}
        outage_by_unit = {o.unit_number: o for o in outages}
        
        for unit_num in range(1, num_units + 1):
            outage = outage_by_unit.get(unit_num)
            if outage:
                metrics = calculate_unit_availability(outage, year, month)
                unit_details[unit_num] = {
                    "planned_days": float(outage.planned_outage_days or 0),
                    "forced_days": float(outage.forced_outage_days or 0),
                    "reserve_days": float(outage.reserve_shutdown_days or 0),
                    "availability": float(metrics["availability_factor"]),
                    "efor": float(metrics["efor"]),
                }
            else:
                unit_details[unit_num] = {
                    "planned_days": 0,
                    "forced_days": 0,
                    "reserve_days": 0,
                    "availability": 1.0,
                    "efor": 0.0,
                }
        
        return PlantAvailabilityResponse(
            plant_id=plant_id,
            plant_name=plant.name,
            year=year,
            month=month,
            weighted_availability=float(plant_metrics["weighted_availability"]),
            weighted_efor=float(plant_metrics["weighted_efor"]),
            total_outage_days=float(plant_metrics["total_outage_days"]),
            unit_details=unit_details,
        )


@router.get("/{plant_id}/{year}/summary", response_model=AnnualOutageSummaryResponse)
async def get_annual_summary(
    plant_id: int,
    year: int,
):
    """Get annual outage summary for a plant.
    
    Returns aggregated outage statistics and unit-level totals.
    """
    with get_session() as db:
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail=f"Plant not found: {plant_id}")
        
        summary = get_annual_outage_summary(db, plant_id, year)
        
        # Build monthly summary
        outages = get_unit_outages_for_year(db, plant_id, year)
        monthly_summary = {}
        
        for month in range(1, 13):
            month_outages = [o for o in outages if o.month == month]
            planned = sum(float(o.planned_outage_days or 0) for o in month_outages)
            forced = sum(float(o.forced_outage_days or 0) for o in month_outages)
            reserve = sum(float(o.reserve_shutdown_days or 0) for o in month_outages)
            
            monthly_summary[month] = {
                "planned_days": planned,
                "forced_days": forced,
                "reserve_days": reserve,
                "total_days": planned + forced,
            }
        
        # Convert unit totals
        unit_totals = {}
        for unit_num, totals in summary["unit_totals"].items():
            unit_totals[unit_num] = {
                "planned_days": float(totals["planned_days"]),
                "forced_days": float(totals["forced_days"]),
                "reserve_days": float(totals["reserve_days"]),
            }
        
        return AnnualOutageSummaryResponse(
            plant_id=plant_id,
            plant_name=plant.name,
            year=year,
            total_planned_days=float(summary["total_planned_days"]),
            total_forced_days=float(summary["total_forced_days"]),
            total_reserve_days=float(summary["total_reserve_days"]),
            total_outage_days=float(summary["total_outage_days"]),
            unit_totals=unit_totals,
            monthly_summary=monthly_summary,
        )


# =============================================================================
# Matrix Endpoint for UI
# =============================================================================

@router.get("/{plant_id}/{year}/matrix")
async def get_outage_matrix(
    plant_id: int,
    year: int,
):
    """Get outage data as a matrix for the UI.
    
    Returns a 2D structure: units (rows) x months (columns)
    Suitable for rendering in a grid input form.
    """
    with get_session() as db:
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail=f"Plant not found: {plant_id}")
        
        # Get unit count
        num_units = 5 if plant_id == 1 else 6  # Kyger: 5, Clifty: 6
        
        # Get all outages for the year
        outages = get_unit_outages_for_year(db, plant_id, year)
        
        # Build matrix: dict of unit -> dict of month -> data
        matrix = {}
        for unit_num in range(1, num_units + 1):
            matrix[unit_num] = {}
            for month in range(1, 13):
                matrix[unit_num][month] = {
                    "planned_days": 0,
                    "forced_days": 0,
                    "reserve_days": 0,
                    "outage_type": None,
                    "has_outage": False,
                }
        
        # Fill in actual data
        for outage in outages:
            matrix[outage.unit_number][outage.month] = {
                "planned_days": float(outage.planned_outage_days or 0),
                "forced_days": float(outage.forced_outage_days or 0),
                "reserve_days": float(outage.reserve_shutdown_days or 0),
                "outage_type": outage.outage_type,
                "has_outage": (outage.planned_outage_days or 0) > 0 or (outage.forced_outage_days or 0) > 0,
            }
        
        return {
            "plant_id": plant_id,
            "plant_name": plant.name,
            "year": year,
            "num_units": num_units,
            "matrix": matrix,
            "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        }

