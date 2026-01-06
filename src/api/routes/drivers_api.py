"""
Driver-based forecasting API endpoints.

Provides CRUD operations for driver definitions and values,
as well as calculation endpoints using the driver framework.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from decimal import Decimal
from pydantic import BaseModel
from datetime import datetime

from src.db.postgres import get_session
from src.models.driver import DriverDefinition, DriverValue, DriverValueHistory
from src.engine.drivers import (
    FuelModel,
    Driver,
    DriverType,
    DriverCategory,
    DriverValueStore,
)
from src.engine.default_drivers import (
    create_default_fuel_model,
    ALL_DRIVERS,
    get_drivers_by_category,
)
from src.engine.fuel_model import (
    calculate_fuel_costs_from_drivers,
    calculate_annual_fuel_costs_from_drivers,
    calculate_system_fuel_costs_from_drivers,
    summarize_annual_fuel_costs,
)

router = APIRouter(prefix="/api/drivers", tags=["Drivers"])


# =============================================================================
# Pydantic Models
# =============================================================================

class DriverDefinitionResponse(BaseModel):
    """Response model for a driver definition."""
    name: str
    description: str
    driver_type: str
    category: str
    unit: str
    default_value: float
    min_value: Optional[float]
    max_value: Optional[float]
    step: float
    is_plant_specific: bool
    depends_on: List[str]
    is_calculated: bool

    class Config:
        from_attributes = True


class DriverValueInput(BaseModel):
    """Input model for setting a driver value."""
    driver_name: str
    value: float
    period_yyyymm: str  # YYYYMM for monthly, YYYY for annual
    plant_id: Optional[int] = None
    notes: Optional[str] = None


class BulkDriverValueInput(BaseModel):
    """Input model for bulk setting driver values."""
    values: List[DriverValueInput]
    updated_by: Optional[str] = None


class DriverValueResponse(BaseModel):
    """Response model for a driver value."""
    driver_name: str
    value: float
    period_yyyymm: str
    plant_id: Optional[int]
    notes: Optional[str]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class CalculationRequest(BaseModel):
    """Request model for fuel cost calculation."""
    driver_values: Optional[Dict[str, float]] = None
    use_database_values: bool = True


# =============================================================================
# Driver Definition Endpoints
# =============================================================================

@router.get("/definitions", response_model=List[DriverDefinitionResponse])
async def get_driver_definitions(
    category: Optional[str] = None,
    include_calculated: bool = True,
):
    """Get all driver definitions.
    
    Args:
        category: Filter by category (coal_price, transportation, etc.)
        include_calculated: Whether to include calculated drivers
    """
    drivers = ALL_DRIVERS
    
    # Filter by category
    if category:
        try:
            cat = DriverCategory(category)
            drivers = [d for d in drivers if d.category == cat]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown category: {category}")
    
    # Filter calculated
    if not include_calculated:
        drivers = [d for d in drivers if d.driver_type != DriverType.CALCULATED]
    
    return [
        DriverDefinitionResponse(
            name=d.name,
            description=d.description,
            driver_type=d.driver_type.value,
            category=d.category.value,
            unit=d.unit,
            default_value=float(d.default_value),
            min_value=float(d.min_value) if d.min_value else None,
            max_value=float(d.max_value) if d.max_value else None,
            step=float(d.step),
            is_plant_specific=d.is_plant_specific,
            depends_on=d.depends_on,
            is_calculated=d.driver_type == DriverType.CALCULATED,
        )
        for d in sorted(drivers, key=lambda x: (x.category.value, x.display_order))
    ]


@router.get("/definitions/{driver_name}", response_model=DriverDefinitionResponse)
async def get_driver_definition(driver_name: str):
    """Get a specific driver definition by name."""
    for d in ALL_DRIVERS:
        if d.name == driver_name:
            return DriverDefinitionResponse(
                name=d.name,
                description=d.description,
                driver_type=d.driver_type.value,
                category=d.category.value,
                unit=d.unit,
                default_value=float(d.default_value),
                min_value=float(d.min_value) if d.min_value else None,
                max_value=float(d.max_value) if d.max_value else None,
                step=float(d.step),
                is_plant_specific=d.is_plant_specific,
                depends_on=d.depends_on,
                is_calculated=d.driver_type == DriverType.CALCULATED,
            )
    raise HTTPException(status_code=404, detail=f"Driver not found: {driver_name}")


@router.get("/categories")
async def get_driver_categories():
    """Get all driver categories with counts."""
    categories = {}
    for d in ALL_DRIVERS:
        cat = d.category.value
        if cat not in categories:
            categories[cat] = {"name": cat, "count": 0, "input_count": 0, "calculated_count": 0}
        categories[cat]["count"] += 1
        if d.driver_type == DriverType.CALCULATED:
            categories[cat]["calculated_count"] += 1
        else:
            categories[cat]["input_count"] += 1
    
    return list(categories.values())


# =============================================================================
# Driver Value Endpoints
# =============================================================================

@router.get("/values/{scenario_id}/{year}")
async def get_driver_values(
    scenario_id: int,
    year: int,
    month: Optional[int] = None,
    plant_id: Optional[int] = None,
    category: Optional[str] = None,
):
    """Get driver values for a scenario and year.
    
    Args:
        scenario_id: Scenario ID
        year: Year
        month: Optional month (1-12), if None returns annual values
        plant_id: Optional plant ID filter
        category: Optional category filter
    """
    with get_session() as db:
        # Build query
        query = db.query(DriverValue).join(DriverDefinition).filter(
            DriverValue.scenario_id == scenario_id,
        )
        
        # Filter by period
        if month:
            period = f"{year}{month:02d}"
            query = query.filter(DriverValue.period_yyyymm == period)
        else:
            # Get all values for the year (annual and monthly)
            query = query.filter(DriverValue.period_yyyymm.like(f"{year}%"))
        
        # Filter by plant
        if plant_id:
            query = query.filter(
                (DriverValue.plant_id == plant_id) | (DriverValue.plant_id.is_(None))
            )
        
        # Filter by category
        if category:
            query = query.filter(DriverDefinition.category == category)
        
        values = query.all()
        
        # Build response with driver names
        result = []
        for v in values:
            result.append({
                "driver_name": v.driver.name,
                "value": float(v.value),
                "period_yyyymm": v.period_yyyymm,
                "plant_id": v.plant_id,
                "notes": v.notes,
                "updated_at": v.updated_at.isoformat() if v.updated_at else None,
            })
        
        return result


@router.post("/values/{scenario_id}")
async def set_driver_values(
    scenario_id: int,
    input_data: BulkDriverValueInput,
):
    """Set driver values for a scenario.
    
    Args:
        scenario_id: Scenario ID
        input_data: Driver values to set
    """
    with get_session() as db:
        # Get driver name to ID mapping
        driver_defs = {d.name: d for d in db.query(DriverDefinition).all()}
        
        # If no definitions in DB, seed from defaults
        if not driver_defs:
            # Seed driver definitions
            for driver in ALL_DRIVERS:
                db_driver = DriverDefinition(
                    name=driver.name,
                    description=driver.description,
                    driver_type=driver.driver_type.value,
                    category=driver.category.value,
                    unit=driver.unit,
                    default_value=driver.default_value,
                    min_value=driver.min_value,
                    max_value=driver.max_value,
                    step=driver.step,
                    is_plant_specific=driver.is_plant_specific,
                    display_order=driver.display_order,
                )
                if driver.depends_on:
                    db_driver.set_dependencies(driver.depends_on)
                db.add(db_driver)
            db.flush()
            driver_defs = {d.name: d for d in db.query(DriverDefinition).all()}
        
        results = []
        for val in input_data.values:
            # Validate driver exists
            if val.driver_name not in driver_defs:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown driver: {val.driver_name}"
                )
            
            driver_def = driver_defs[val.driver_name]
            
            # Check for existing value
            existing = db.query(DriverValue).filter(
                DriverValue.scenario_id == scenario_id,
                DriverValue.driver_id == driver_def.id,
                DriverValue.plant_id == val.plant_id,
                DriverValue.period_yyyymm == val.period_yyyymm,
            ).first()
            
            if existing:
                # Update existing value
                old_value = existing.value
                existing.value = Decimal(str(val.value))
                existing.notes = val.notes
                existing.updated_by = input_data.updated_by
                existing.updated_at = datetime.utcnow()
                
                # Record history
                history = DriverValueHistory(
                    driver_value_id=existing.id,
                    scenario_id=scenario_id,
                    driver_id=driver_def.id,
                    plant_id=val.plant_id,
                    period_yyyymm=val.period_yyyymm,
                    old_value=old_value,
                    new_value=Decimal(str(val.value)),
                    change_type="update",
                    changed_by=input_data.updated_by,
                )
                db.add(history)
            else:
                # Create new value
                new_value = DriverValue(
                    scenario_id=scenario_id,
                    driver_id=driver_def.id,
                    plant_id=val.plant_id,
                    period_yyyymm=val.period_yyyymm,
                    value=Decimal(str(val.value)),
                    notes=val.notes,
                    updated_by=input_data.updated_by,
                )
                db.add(new_value)
                db.flush()
                
                # Record history
                history = DriverValueHistory(
                    driver_value_id=new_value.id,
                    scenario_id=scenario_id,
                    driver_id=driver_def.id,
                    plant_id=val.plant_id,
                    period_yyyymm=val.period_yyyymm,
                    old_value=None,
                    new_value=Decimal(str(val.value)),
                    change_type="create",
                    changed_by=input_data.updated_by,
                )
                db.add(history)
            
            results.append({
                "driver_name": val.driver_name,
                "period_yyyymm": val.period_yyyymm,
                "plant_id": val.plant_id,
                "value": val.value,
                "status": "updated" if existing else "created",
            })
        
        db.commit()
        
        return {
            "scenario_id": scenario_id,
            "updated_count": len(results),
            "results": results,
        }


@router.delete("/values/{scenario_id}/{driver_name}")
async def delete_driver_value(
    scenario_id: int,
    driver_name: str,
    period_yyyymm: str,
    plant_id: Optional[int] = None,
):
    """Delete a driver value.
    
    Args:
        scenario_id: Scenario ID
        driver_name: Driver name
        period_yyyymm: Period
        plant_id: Optional plant ID
    """
    with get_session() as db:
        driver_def = db.query(DriverDefinition).filter(
            DriverDefinition.name == driver_name
        ).first()
        
        if not driver_def:
            raise HTTPException(status_code=404, detail=f"Driver not found: {driver_name}")
        
        value = db.query(DriverValue).filter(
            DriverValue.scenario_id == scenario_id,
            DriverValue.driver_id == driver_def.id,
            DriverValue.plant_id == plant_id,
            DriverValue.period_yyyymm == period_yyyymm,
        ).first()
        
        if not value:
            raise HTTPException(status_code=404, detail="Value not found")
        
        # Record history
        history = DriverValueHistory(
            driver_value_id=value.id,
            scenario_id=scenario_id,
            driver_id=driver_def.id,
            plant_id=plant_id,
            period_yyyymm=period_yyyymm,
            old_value=value.value,
            new_value=None,
            change_type="delete",
        )
        db.add(history)
        
        db.delete(value)
        db.commit()
        
        return {"status": "deleted", "driver_name": driver_name, "period_yyyymm": period_yyyymm}


# =============================================================================
# Calculation Endpoints
# =============================================================================

def _load_driver_model_from_db(db: Session, scenario_id: int, year: int) -> FuelModel:
    """Load a FuelModel from database values for a scenario/year."""
    model = create_default_fuel_model()
    
    # Get driver definitions from DB
    driver_defs = {d.name: d for d in db.query(DriverDefinition).all()}
    
    # Get all values for this scenario and year
    values = db.query(DriverValue).join(DriverDefinition).filter(
        DriverValue.scenario_id == scenario_id,
        DriverValue.period_yyyymm.like(f"{year}%"),
    ).all()
    
    # Load values into model
    for v in values:
        driver_name = v.driver.name
        period = v.period_yyyymm
        
        # Parse year and month from period
        v_year = int(period[:4])
        v_month = int(period[4:6]) if len(period) == 6 else None
        
        model.set_driver_value(
            driver_name,
            v_year,
            v_month,
            v.value,
            v.plant_id,
        )
    
    return model


@router.get("/calculate/{scenario_id}/{year}")
async def calculate_from_drivers(
    scenario_id: int,
    year: int,
    plant_id: Optional[int] = None,
):
    """Calculate fuel costs using driver values from database.
    
    Args:
        scenario_id: Scenario ID to load values from
        year: Year to calculate
        plant_id: Optional plant ID (None for both plants)
    """
    with get_session() as db:
        # Load driver model from database
        driver_model = _load_driver_model_from_db(db, scenario_id, year)
        
        if plant_id:
            # Calculate for single plant
            monthly = calculate_annual_fuel_costs_from_drivers(db, driver_model, plant_id, year)
            annual = summarize_annual_fuel_costs(monthly)
            
            return {
                "scenario_id": scenario_id,
                "year": year,
                "plant_id": plant_id,
                "annual": annual,
                "monthly": [m.to_dict() for m in monthly],
            }
        else:
            # Calculate for system
            result = calculate_system_fuel_costs_from_drivers(db, driver_model, year)
            return {
                "scenario_id": scenario_id,
                **result,
            }


@router.post("/calculate/{year}")
async def calculate_with_inputs(
    year: int,
    request: CalculationRequest,
    plant_id: Optional[int] = None,
):
    """Calculate fuel costs with provided driver values.
    
    This endpoint allows ad-hoc calculations without saving to database.
    
    Args:
        year: Year to calculate
        request: Calculation request with driver values
        plant_id: Optional plant ID (None for both plants)
    """
    # Create model with defaults
    model = create_default_fuel_model()
    
    # Override with provided values (annual values)
    if request.driver_values:
        for name, value in request.driver_values.items():
            try:
                model.set_driver_value(name, year, None, Decimal(str(value)))
            except ValueError:
                pass  # Skip unknown drivers
    
    with get_session() as db:
        if plant_id:
            # Calculate for single plant
            monthly = calculate_annual_fuel_costs_from_drivers(db, model, plant_id, year)
            annual = summarize_annual_fuel_costs(monthly)
            
            return {
                "year": year,
                "plant_id": plant_id,
                "annual": annual,
                "monthly": [m.to_dict() for m in monthly],
            }
        else:
            # Calculate for system
            return calculate_system_fuel_costs_from_drivers(db, model, year)


@router.get("/calculate/{scenario_id}/{year}/{month}")
async def calculate_month_from_drivers(
    scenario_id: int,
    year: int,
    month: int,
    plant_id: int,
):
    """Calculate fuel costs for a specific month.
    
    Args:
        scenario_id: Scenario ID
        year: Year
        month: Month (1-12)
        plant_id: Plant ID (required for monthly calculation)
    """
    with get_session() as db:
        driver_model = _load_driver_model_from_db(db, scenario_id, year)
        result = calculate_fuel_costs_from_drivers(db, driver_model, plant_id, year, month)
        return result.to_dict()


# =============================================================================
# Seed/Initialize Endpoints
# =============================================================================

@router.post("/seed")
async def seed_driver_definitions():
    """Seed driver definitions from the default drivers.
    
    This creates or updates the driver_definitions table with all
    default OVEC drivers.
    """
    with get_session() as db:
        seeded = 0
        updated = 0
        
        for driver in ALL_DRIVERS:
            existing = db.query(DriverDefinition).filter(
                DriverDefinition.name == driver.name
            ).first()
            
            if existing:
                # Update existing
                existing.description = driver.description
                existing.unit = driver.unit
                existing.default_value = driver.default_value
                existing.min_value = driver.min_value
                existing.max_value = driver.max_value
                existing.step = driver.step
                existing.is_plant_specific = driver.is_plant_specific
                existing.display_order = driver.display_order
                if driver.depends_on:
                    existing.set_dependencies(driver.depends_on)
                updated += 1
            else:
                # Create new
                db_driver = DriverDefinition(
                    name=driver.name,
                    description=driver.description,
                    driver_type=driver.driver_type.value,
                    category=driver.category.value,
                    unit=driver.unit,
                    default_value=driver.default_value,
                    min_value=driver.min_value,
                    max_value=driver.max_value,
                    step=driver.step,
                    is_plant_specific=driver.is_plant_specific,
                    display_order=driver.display_order,
                )
                if driver.depends_on:
                    db_driver.set_dependencies(driver.depends_on)
                db.add(db_driver)
                seeded += 1
        
        db.commit()
        
        return {
            "status": "success",
            "seeded": seeded,
            "updated": updated,
            "total": seeded + updated,
        }


# =============================================================================
# Scenario Management Endpoints
# =============================================================================

class ScenarioDriverExport(BaseModel):
    """Export format for scenario driver values."""
    scenario_id: int
    year: int
    drivers: Dict[str, Dict]


class ScenarioDriverImport(BaseModel):
    """Import format for scenario driver values."""
    year: int
    drivers: Dict[str, Dict]
    overwrite: bool = True


@router.post("/scenarios/{scenario_id}/copy-from/{source_id}")
async def copy_scenario_drivers(
    scenario_id: int,
    source_id: int,
    year: int,
    overwrite: bool = False,
):
    """Copy driver values from one scenario to another.
    
    Args:
        scenario_id: Target scenario ID
        source_id: Source scenario ID to copy from
        year: Year to copy
        overwrite: If True, overwrite existing values in target
    """
    from src.engine.scenario_drivers import copy_scenario_drivers as copy_drivers
    
    with get_session() as db:
        count = copy_drivers(db, source_id, scenario_id, year, overwrite)
        
        return {
            "status": "success",
            "source_scenario_id": source_id,
            "target_scenario_id": scenario_id,
            "year": year,
            "values_copied": count,
        }


@router.get("/scenarios/{scenario_id}/export/{year}")
async def export_scenario_drivers(
    scenario_id: int,
    year: int,
):
    """Export all driver values for a scenario/year as JSON.
    
    Args:
        scenario_id: Scenario ID
        year: Year to export
    """
    from src.engine.scenario_drivers import export_scenario_drivers as export_drivers
    
    with get_session() as db:
        driver_set = export_drivers(db, scenario_id, year)
        return driver_set.to_dict()


@router.post("/scenarios/{scenario_id}/import")
async def import_scenario_drivers(
    scenario_id: int,
    data: ScenarioDriverImport,
):
    """Import driver values into a scenario from JSON.
    
    Args:
        scenario_id: Target scenario ID
        data: Driver values to import
    """
    from src.engine.scenario_drivers import (
        import_scenario_drivers as import_drivers,
        ScenarioDriverSet,
    )
    
    driver_set = ScenarioDriverSet(
        scenario_id=scenario_id,
        year=data.year,
        driver_values=data.drivers,
    )
    
    with get_session() as db:
        count = import_drivers(db, scenario_id, driver_set, data.overwrite)
        
        return {
            "status": "success",
            "scenario_id": scenario_id,
            "year": data.year,
            "values_imported": count,
        }


@router.get("/scenarios/{scenario_a}/compare/{scenario_b}/{year}")
async def compare_scenarios(
    scenario_a: int,
    scenario_b: int,
    year: int,
):
    """Compare driver values between two scenarios.
    
    Args:
        scenario_a: First scenario ID
        scenario_b: Second scenario ID
        year: Year to compare
    """
    from src.engine.scenario_drivers import compare_scenario_drivers
    
    with get_session() as db:
        return compare_scenario_drivers(db, scenario_a, scenario_b, year)


# =============================================================================
# Excel Import Endpoints
# =============================================================================

class ExcelImportRequest(BaseModel):
    """Request for Excel import."""
    file_path: str
    year: int
    plant_id: Optional[int] = None


@router.post("/import/excel/{scenario_id}")
async def import_from_excel(
    scenario_id: int,
    request: ExcelImportRequest,
):
    """Import driver values from an Excel file.
    
    Args:
        scenario_id: Target scenario ID
        request: Import request with file path and year
    """
    from src.etl.fuel_excel_import import import_fuel_drivers_from_excel
    
    with get_session() as db:
        result = import_fuel_drivers_from_excel(
            db,
            scenario_id,
            request.file_path,
            request.year,
            request.plant_id,
        )
        
        return {
            "status": "success" if result.success else "error",
            "file": result.file_path,
            "scenario_id": result.scenario_id,
            "year": result.year,
            "drivers_imported": result.drivers_imported,
            "values_imported": result.values_imported,
            "errors": result.errors,
            "warnings": result.warnings,
            "details": result.details,
        }


# =============================================================================
# Multi-Year Projection Endpoints
# =============================================================================

@router.get("/projections/{scenario_id}/{start_year}/{end_year}")
async def get_multi_year_projection(
    scenario_id: int,
    start_year: int,
    end_year: int = 2040,
    format: str = "full",
):
    """Calculate multi-year fuel cost projections.
    
    Args:
        scenario_id: Scenario ID with base year driver values
        start_year: Starting year
        end_year: Ending year (default 2040)
        format: Output format - "full" or "sponsor"
    """
    from src.engine.projections import project_multi_year, create_sponsor_projection
    from src.engine.scenario_drivers import load_driver_values_from_scenario
    
    with get_session() as db:
        # Load base model from scenario
        base_model = load_driver_values_from_scenario(db, scenario_id, start_year)
        
        if format == "sponsor":
            result = create_sponsor_projection(db, base_model, start_year, end_year)
        else:
            result = project_multi_year(db, base_model, start_year, end_year)
        
        return result.to_dict()


@router.get("/projections/simple/{start_year}/{end_year}")
async def get_simple_projection(
    start_year: int,
    end_year: int = 2040,
    coal_escalation: float = 2.5,
    transport_escalation: float = 2.0,
):
    """Calculate projections using default drivers with specified escalation.
    
    Args:
        start_year: Starting year
        end_year: Ending year
        coal_escalation: Annual coal price escalation rate (%)
        transport_escalation: Annual transport cost escalation rate (%)
    """
    from src.engine.projections import project_multi_year
    from src.engine.default_drivers import create_default_fuel_model
    
    # Create model with specified escalation rates
    base_model = create_default_fuel_model()
    base_model.set_driver_value("escalation_coal_annual", start_year, None, Decimal(str(coal_escalation)))
    base_model.set_driver_value("escalation_transport_annual", start_year, None, Decimal(str(transport_escalation)))
    
    with get_session() as db:
        result = project_multi_year(db, base_model, start_year, end_year)
        return result.to_dict()


@router.post("/projections/{scenario_id}/sponsor")
async def create_sponsor_report(
    scenario_id: int,
    start_year: int,
    end_year: int = 2040,
):
    """Create sponsor-format projection report.
    
    Years 1-2: Monthly detail
    Years 3+: Annual summary
    
    Args:
        scenario_id: Scenario ID with base year driver values
        start_year: Starting year
        end_year: Ending year
    """
    from src.engine.projections import create_sponsor_projection
    from src.engine.scenario_drivers import load_driver_values_from_scenario
    
    with get_session() as db:
        base_model = load_driver_values_from_scenario(db, scenario_id, start_year)
        result = create_sponsor_projection(db, base_model, start_year, end_year)
        
        return {
            "status": "success",
            "scenario_id": scenario_id,
            **result.to_dict(),
        }


@router.get("/projections/escalated-drivers/{base_year}/{target_year}")
async def get_escalated_drivers(
    base_year: int,
    target_year: int,
    scenario_id: Optional[int] = None,
):
    """Preview escalated driver values for a target year.
    
    Shows what the driver values would be after applying escalation
    from base year to target year.
    
    Args:
        base_year: Base year
        target_year: Target year
        scenario_id: Optional scenario ID (uses defaults if not provided)
    """
    from src.engine.projections import create_escalated_model
    from src.engine.default_drivers import create_default_fuel_model
    
    if scenario_id:
        from src.engine.scenario_drivers import load_driver_values_from_scenario
        with get_session() as db:
            base_model = load_driver_values_from_scenario(db, scenario_id, base_year)
    else:
        base_model = create_default_fuel_model()
    
    escalated = create_escalated_model(base_model, base_year, target_year)
    
    # Get key drivers to show
    key_drivers = [
        "coal_price_eastern",
        "coal_price_ilb",
        "coal_price_prb",
        "barge_rate_ohio",
        "barge_rate_upper_ohio",
        "rail_rate_prb",
    ]
    
    result = {
        "base_year": base_year,
        "target_year": target_year,
        "years_escalated": target_year - base_year,
        "drivers": {},
    }
    
    for driver_name in key_drivers:
        try:
            base_value = float(base_model.get_driver_value(driver_name, base_year, 1))
            escalated_value = float(escalated.get_driver_value(driver_name, target_year, 1))
            change_pct = ((escalated_value - base_value) / base_value * 100) if base_value > 0 else 0
            
            result["drivers"][driver_name] = {
                "base_value": base_value,
                "escalated_value": escalated_value,
                "change_pct": round(change_pct, 2),
            }
        except ValueError:
            pass
    
    return result

