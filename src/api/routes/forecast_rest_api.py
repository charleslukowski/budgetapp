"""REST API for Fuel Forecasts.

Provides programmatic access to forecast scenarios with CRUD operations,
calculations, projections, and comparisons.

API Version: v1
Base Path: /api/v1/forecasts
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.db.postgres import get_session as get_db_session
from src.models.scenario import Scenario, ScenarioType, ScenarioStatus
from src.engine.scenario_drivers import (
    export_scenario_drivers,
    save_driver_values_to_scenario,
    compare_scenario_drivers,
    ensure_driver_definitions,
)
from src.engine.default_drivers import create_default_fuel_model, ALL_DRIVERS
from src.engine.projections import project_multi_year


router = APIRouter(prefix="/api/v1", tags=["Forecast API"])


# =============================================================================
# Pydantic Models
# =============================================================================

class DriverValue(BaseModel):
    """Single driver value."""
    name: str
    value: Any
    plant_id: Optional[int] = None


class ForecastCreate(BaseModel):
    """Request to create a new forecast."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    year: int = Field(..., ge=2020, le=2050)
    scenario_type: str = Field(default="internal_forecast")
    drivers: Dict[str, Any] = Field(default_factory=dict)


class ForecastUpdate(BaseModel):
    """Request to update a forecast."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = None
    drivers: Optional[Dict[str, Any]] = None


class ForecastSummary(BaseModel):
    """Summary of a forecast scenario."""
    id: int
    name: str
    description: Optional[str]
    scenario_type: str
    status: str
    year: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]
    is_locked: bool


class ForecastDetail(BaseModel):
    """Full forecast details including drivers."""
    id: int
    name: str
    description: Optional[str]
    scenario_type: str
    status: str
    year: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]
    is_locked: bool
    drivers: Dict[str, Any]
    results: Optional[Dict[str, Any]] = None


class CalculationResult(BaseModel):
    """Result of a forecast calculation."""
    scenario_id: int
    year: int
    total_cost: float
    cost_per_mwh: float
    total_mwh: float
    capacity_factor: float
    by_plant: Dict[str, Any]
    monthly: List[Dict[str, Any]]


class ProjectionResult(BaseModel):
    """Multi-year projection result."""
    scenario_id: int
    base_year: int
    end_year: int
    projections: List[Dict[str, Any]]
    summary: Dict[str, Any]


class ComparisonResult(BaseModel):
    """Comparison between two scenarios."""
    scenario_a_id: int
    scenario_b_id: int
    year: int
    differences: List[Dict[str, Any]]
    metrics_comparison: Dict[str, Any]


class DriverDefinition(BaseModel):
    """Definition of a driver."""
    name: str
    label: str
    category: str
    unit: str
    default_value: Any
    is_plant_specific: bool


# =============================================================================
# List Forecasts
# =============================================================================

@router.get("/forecasts", response_model=List[ForecastSummary])
async def list_forecasts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    scenario_type: Optional[str] = None,
    status: Optional[str] = None,
    year: Optional[int] = None,
):
    """List all forecast scenarios with optional filtering."""
    with get_db_session() as db:
        query = db.query(Scenario).filter(Scenario.is_active == True)
        
        if scenario_type:
            try:
                st = ScenarioType(scenario_type)
                query = query.filter(Scenario.scenario_type == st)
            except ValueError:
                pass
        
        if status:
            try:
                s = ScenarioStatus(status)
                query = query.filter(Scenario.status == s)
            except ValueError:
                pass
        
        # Note: year filtering would need to be added to Scenario model or extracted from drivers
        
        scenarios = query.order_by(Scenario.created_at.desc()).offset(offset).limit(limit).all()
        
        return [
            ForecastSummary(
                id=s.id,
                name=s.name,
                description=s.description,
                scenario_type=s.scenario_type.value,
                status=s.status.value,
                year=None,  # Would need to extract from drivers
                created_at=s.created_at,
                updated_at=s.updated_at,
                is_locked=s.is_locked,
            )
            for s in scenarios
        ]


# =============================================================================
# Get Forecast Detail
# =============================================================================

@router.get("/forecasts/{scenario_id}", response_model=ForecastDetail)
async def get_forecast(scenario_id: int, year: int = Query(default=2025)):
    """Get detailed forecast information including driver values."""
    with get_db_session() as db:
        scenario = db.query(Scenario).filter(
            Scenario.id == scenario_id,
            Scenario.is_active == True
        ).first()
        
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        # Get driver values
        driver_set = export_scenario_drivers(db, scenario_id, year)
        
        return ForecastDetail(
            id=scenario.id,
            name=scenario.name,
            description=scenario.description,
            scenario_type=scenario.scenario_type.value,
            status=scenario.status.value,
            year=year,
            created_at=scenario.created_at,
            updated_at=scenario.updated_at,
            is_locked=scenario.is_locked,
            drivers=driver_set.driver_values,
        )


# =============================================================================
# Create Forecast
# =============================================================================

@router.post("/forecasts", response_model=ForecastDetail)
async def create_forecast(request: ForecastCreate):
    """Create a new forecast scenario with driver values."""
    with get_db_session() as db:
        # Map scenario type
        try:
            scenario_type = ScenarioType(request.scenario_type)
        except ValueError:
            scenario_type = ScenarioType.INTERNAL_FORECAST
        
        # Create scenario
        scenario = Scenario(
            name=request.name,
            description=request.description,
            scenario_type=scenario_type,
            status=ScenarioStatus.DRAFT,
            created_by="api",
        )
        db.add(scenario)
        db.flush()
        
        # Save driver values
        if request.drivers:
            model = create_default_fuel_model()
            
            for driver_name, value in request.drivers.items():
                if driver_name in model.drivers:
                    try:
                        model.set_driver_value(driver_name, request.year, None, Decimal(str(value)))
                    except (ValueError, TypeError):
                        pass
            
            ensure_driver_definitions(db)
            save_driver_values_to_scenario(db, model, scenario.id, request.year, "api")
        
        db.commit()
        
        # Return created scenario
        return ForecastDetail(
            id=scenario.id,
            name=scenario.name,
            description=scenario.description,
            scenario_type=scenario.scenario_type.value,
            status=scenario.status.value,
            year=request.year,
            created_at=scenario.created_at,
            updated_at=scenario.updated_at,
            is_locked=scenario.is_locked,
            drivers=request.drivers,
        )


# =============================================================================
# Update Forecast
# =============================================================================

@router.put("/forecasts/{scenario_id}", response_model=ForecastDetail)
async def update_forecast(scenario_id: int, request: ForecastUpdate, year: int = Query(default=2025)):
    """Update an existing forecast scenario."""
    with get_db_session() as db:
        scenario = db.query(Scenario).filter(
            Scenario.id == scenario_id,
            Scenario.is_active == True
        ).first()
        
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        if scenario.is_locked:
            raise HTTPException(status_code=403, detail="Scenario is locked and cannot be modified")
        
        # Update basic fields
        if request.name is not None:
            scenario.name = request.name
        if request.description is not None:
            scenario.description = request.description
        if request.status is not None:
            try:
                scenario.status = ScenarioStatus(request.status)
            except ValueError:
                pass
        
        # Update driver values
        if request.drivers is not None:
            model = create_default_fuel_model()
            
            for driver_name, value in request.drivers.items():
                if driver_name in model.drivers:
                    try:
                        model.set_driver_value(driver_name, year, None, Decimal(str(value)))
                    except (ValueError, TypeError):
                        pass
            
            ensure_driver_definitions(db)
            save_driver_values_to_scenario(db, model, scenario.id, year, "api")
        
        db.commit()
        
        # Get updated driver values
        driver_set = export_scenario_drivers(db, scenario_id, year)
        
        return ForecastDetail(
            id=scenario.id,
            name=scenario.name,
            description=scenario.description,
            scenario_type=scenario.scenario_type.value,
            status=scenario.status.value,
            year=year,
            created_at=scenario.created_at,
            updated_at=scenario.updated_at,
            is_locked=scenario.is_locked,
            drivers=driver_set.driver_values,
        )


# =============================================================================
# Delete (Archive) Forecast
# =============================================================================

@router.delete("/forecasts/{scenario_id}")
async def delete_forecast(scenario_id: int):
    """Archive a forecast scenario (soft delete)."""
    with get_db_session() as db:
        scenario = db.query(Scenario).filter(
            Scenario.id == scenario_id,
            Scenario.is_active == True
        ).first()
        
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        if scenario.is_locked:
            raise HTTPException(status_code=403, detail="Scenario is locked and cannot be deleted")
        
        scenario.is_active = False
        db.commit()
        
        return {"status": "archived", "scenario_id": scenario_id}


# =============================================================================
# Calculate Forecast
# =============================================================================

@router.post("/forecasts/{scenario_id}/calculate", response_model=CalculationResult)
async def calculate_forecast(scenario_id: int, year: int = Query(default=2025)):
    """Run fuel cost calculation for a scenario."""
    from src.engine.fuel_model import calculate_fuel_costs_from_drivers, summarize_annual_fuel_costs
    
    with get_db_session() as db:
        scenario = db.query(Scenario).filter(
            Scenario.id == scenario_id,
            Scenario.is_active == True
        ).first()
        
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        # Get driver values and create model
        driver_set = export_scenario_drivers(db, scenario_id, year)
        model = create_default_fuel_model()
        
        # Apply driver values
        for driver_name, value in driver_set.driver_values.items():
            if driver_name in model.drivers:
                if isinstance(value, dict):
                    val = value.get("annual", 0)
                else:
                    val = value
                try:
                    model.set_driver_value(driver_name, year, None, Decimal(str(val)))
                except (ValueError, TypeError):
                    pass
        
        # Calculate for both plants
        results = {"kyger": {}, "clifty": {}}
        monthly_all = []
        
        for plant_id, plant_name in [(1, "kyger"), (2, "clifty")]:
            monthly_results = []
            for month in range(1, 13):
                try:
                    summary = calculate_fuel_costs_from_drivers(db, model, plant_id, year, month)
                    monthly_results.append(summary)
                except Exception as e:
                    # Use placeholder data if calculation fails
                    pass
            
            if monthly_results:
                annual = summarize_annual_fuel_costs(monthly_results)
                results[plant_name] = annual
                
                for m_result in monthly_results:
                    monthly_all.append({
                        "month": m_result.period_month,
                        "plant": plant_name,
                        "mwh": float(m_result.net_delivered_mwh),
                        "coal_cost": float(m_result.total_coal_cost),
                        "total_cost": float(m_result.total_fuel_cost),
                    })
        
        # Calculate totals
        total_cost = results.get("kyger", {}).get("total_fuel_cost", 0) + results.get("clifty", {}).get("total_fuel_cost", 0)
        total_mwh = results.get("kyger", {}).get("total_mwh", 0) + results.get("clifty", {}).get("total_mwh", 0)
        cost_per_mwh = total_cost / total_mwh if total_mwh > 0 else 0
        
        capacity_factor = (
            results.get("kyger", {}).get("avg_capacity_factor", 0) + 
            results.get("clifty", {}).get("avg_capacity_factor", 0)
        ) / 2
        
        return CalculationResult(
            scenario_id=scenario_id,
            year=year,
            total_cost=total_cost,
            cost_per_mwh=cost_per_mwh,
            total_mwh=total_mwh,
            capacity_factor=capacity_factor,
            by_plant=results,
            monthly=monthly_all,
        )


# =============================================================================
# Multi-Year Projection
# =============================================================================

@router.get("/forecasts/{scenario_id}/projection", response_model=ProjectionResult)
async def get_projection(
    scenario_id: int,
    end_year: int = Query(default=2040, ge=2025, le=2050),
):
    """Get multi-year projection for a scenario."""
    with get_db_session() as db:
        scenario = db.query(Scenario).filter(
            Scenario.id == scenario_id,
            Scenario.is_active == True
        ).first()
        
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        # Determine base year (could be stored in scenario or extracted from drivers)
        base_year = datetime.now().year
        
        # Get driver values and create model
        driver_set = export_scenario_drivers(db, scenario_id, base_year)
        model = create_default_fuel_model()
        
        # Apply driver values
        for driver_name, value in driver_set.driver_values.items():
            if driver_name in model.drivers:
                if isinstance(value, dict):
                    val = value.get("annual", 0)
                else:
                    val = value
                try:
                    model.set_driver_value(driver_name, base_year, None, Decimal(str(val)))
                except (ValueError, TypeError):
                    pass
        
        # Run projection
        projection = project_multi_year(db, model, base_year, end_year)
        
        # Format results
        projections = []
        for proj in projection.system_projections:
            projections.append({
                "year": proj.year,
                "total_fuel_cost": proj.total_fuel_cost,
                "total_mwh": proj.total_mwh,
                "avg_fuel_cost_per_mwh": proj.avg_fuel_cost_per_mwh,
                "coal_price_eastern": proj.coal_price_eastern,
                "barge_rate": proj.barge_rate,
            })
        
        # Calculate summary
        total_cost = sum(p["total_fuel_cost"] for p in projections)
        total_mwh = sum(p["total_mwh"] for p in projections)
        avg_cost = total_cost / total_mwh if total_mwh > 0 else 0
        
        return ProjectionResult(
            scenario_id=scenario_id,
            base_year=base_year,
            end_year=end_year,
            projections=projections,
            summary={
                "total_cost": total_cost,
                "total_mwh": total_mwh,
                "avg_cost_per_mwh": avg_cost,
                "years": len(projections),
            }
        )


# =============================================================================
# Compare Scenarios
# =============================================================================

@router.get("/forecasts/compare", response_model=ComparisonResult)
async def compare_scenarios(
    scenario_a: int = Query(..., description="First scenario ID"),
    scenario_b: int = Query(..., description="Second scenario ID"),
    year: int = Query(default=2025),
):
    """Compare two forecast scenarios."""
    with get_db_session() as db:
        # Verify both scenarios exist
        for sid in [scenario_a, scenario_b]:
            scenario = db.query(Scenario).filter(
                Scenario.id == sid,
                Scenario.is_active == True
            ).first()
            if not scenario:
                raise HTTPException(status_code=404, detail=f"Scenario {sid} not found")
        
        # Get comparison
        comparison = compare_scenario_drivers(db, scenario_a, scenario_b, year)
        
        # Format differences
        differences = []
        for diff in comparison.get("differences", []):
            differences.append({
                "driver": diff.get("driver"),
                "scenario_a_value": diff.get("scenario_a"),
                "scenario_b_value": diff.get("scenario_b"),
            })
        
        return ComparisonResult(
            scenario_a_id=scenario_a,
            scenario_b_id=scenario_b,
            year=year,
            differences=differences,
            metrics_comparison={
                "total_drivers": comparison.get("total_drivers", 0),
                "same_count": comparison.get("same_count", 0),
                "different_count": comparison.get("different_count", 0),
            }
        )


# =============================================================================
# List Available Drivers
# =============================================================================

@router.get("/drivers", response_model=List[DriverDefinition])
async def list_drivers():
    """List all available drivers with their default values."""
    result = []
    for driver in ALL_DRIVERS:
        result.append(DriverDefinition(
            name=driver.name,
            label=driver.label,
            category=driver.category.value if hasattr(driver.category, 'value') else str(driver.category),
            unit=driver.unit or "",
            default_value=float(driver.default_value) if driver.default_value else None,
            is_plant_specific=getattr(driver, 'is_plant_specific', False),
        ))
    
    return result

