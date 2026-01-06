"""API routes for scenario management.

Provides operations for saving, loading, and comparing forecast scenarios:
- Save current inputs as a named scenario
- Load a scenario's inputs
- Compare two scenarios
- List all scenarios
- Set/get active scenarios for header display
"""

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from src.db.postgres import get_session
from src.models.scenario import Scenario, ScenarioType, ScenarioStatus
from src.models.scenario_inputs import (
    ScenarioInputSnapshot,
    capture_current_inputs,
    save_scenario_snapshot,
    get_scenario_snapshot,
    compare_snapshots,
)


# =============================================================================
# Active Scenario Cookie Names
# =============================================================================
COOKIE_ACTIVE_BUDGET = "active_budget_scenario"
COOKIE_ACTIVE_FUEL = "active_fuel_scenario"


def get_active_scenarios_from_request(request: Request) -> Dict[str, Optional[int]]:
    """Get active scenario IDs from cookies."""
    budget_id = request.cookies.get(COOKIE_ACTIVE_BUDGET)
    fuel_id = request.cookies.get(COOKIE_ACTIVE_FUEL)
    
    return {
        "budget": int(budget_id) if budget_id else None,
        "fuel": int(fuel_id) if fuel_id else None,
    }


def get_scenario_context(request: Request) -> Dict[str, Any]:
    """Get scenario context for templates (header dropdowns).
    
    Returns dict with:
    - budget_scenarios: list of budget scenarios
    - fuel_scenarios: list of fuel scenarios
    - active_budget: active budget scenario (or None)
    - active_fuel: active fuel scenario (or None)
    """
    active_ids = get_active_scenarios_from_request(request)
    
    with get_session() as db:
        # Get all active scenarios
        all_scenarios = db.query(Scenario).filter(
            Scenario.is_active == True
        ).order_by(Scenario.created_at.desc()).all()
        
        budget_scenarios = []
        fuel_scenarios = []
        active_budget = None
        active_fuel = None
        
        for s in all_scenarios:
            scenario_dict = {
                "id": s.id,
                "name": s.name,
                "version": s.version,
                "display_name": f"{s.name} v{s.version}",
                "status": s.status.value if s.status else "draft",
                "type": s.scenario_type.value if s.scenario_type else "internal_forecast",
            }
            
            if s.scenario_type == ScenarioType.BUDGET:
                budget_scenarios.append(scenario_dict)
                if active_ids["budget"] == s.id:
                    active_budget = scenario_dict
            else:
                # INTERNAL_FORECAST and EXTERNAL_FORECAST go to fuel
                fuel_scenarios.append(scenario_dict)
                if active_ids["fuel"] == s.id:
                    active_fuel = scenario_dict
        
        # If no active scenario set but we have scenarios, use the first published or first one
        if not active_budget and budget_scenarios:
            published = [s for s in budget_scenarios if s["status"] == "published"]
            active_budget = published[0] if published else budget_scenarios[0]
        
        if not active_fuel and fuel_scenarios:
            published = [s for s in fuel_scenarios if s["status"] == "published"]
            active_fuel = published[0] if published else fuel_scenarios[0]
        
        return {
            "budget_scenarios": budget_scenarios,
            "fuel_scenarios": fuel_scenarios,
            "active_budget": active_budget,
            "active_fuel": active_fuel,
        }


router = APIRouter(prefix="/api/scenarios", tags=["Scenarios"])


# =============================================================================
# Pydantic Models
# =============================================================================

class ScenarioResponse(BaseModel):
    """Response model for a scenario."""
    id: int
    name: str
    description: Optional[str]
    scenario_type: str
    status: str
    version: int
    parent_scenario_id: Optional[int]
    created_at: Optional[datetime]
    created_by: Optional[str]
    is_active: bool
    is_locked: bool
    
    # Summary from snapshot
    has_snapshot: bool = False
    snapshot_summary: Optional[dict] = None

    class Config:
        from_attributes = True


class CreateScenarioRequest(BaseModel):
    """Request to create/save a new scenario."""
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    scenario_type: str = "internal_forecast"
    year: int
    parent_scenario_id: Optional[int] = None
    change_summary: Optional[str] = None
    created_by: Optional[str] = None


class ScenarioComparisonResponse(BaseModel):
    """Response for scenario comparison."""
    scenario_a: dict
    scenario_b: dict
    differences: dict


# =============================================================================
# Scenario Endpoints
# =============================================================================

@router.get("/", response_model=List[ScenarioResponse])
async def list_scenarios(
    scenario_type: Optional[str] = None,
    status: Optional[str] = None,
    year: Optional[int] = None,
):
    """List all scenarios, optionally filtered by type/status."""
    with get_session() as db:
        query = db.query(Scenario).filter(Scenario.is_active == True)
        
        if scenario_type:
            query = query.filter(Scenario.scenario_type == scenario_type)
        if status:
            query = query.filter(Scenario.status == status)
        
        scenarios = query.order_by(Scenario.created_at.desc()).all()
        
        results = []
        for s in scenarios:
            # Get snapshot if exists
            snapshot = get_scenario_snapshot(db, s.id)
            
            # Filter by year if specified
            if year and snapshot and snapshot.year != year:
                continue
            
            results.append(ScenarioResponse(
                id=s.id,
                name=s.name,
                description=s.description,
                scenario_type=s.scenario_type.value if s.scenario_type else "internal_forecast",
                status=s.status.value if s.status else "draft",
                version=s.version,
                parent_scenario_id=s.parent_scenario_id,
                created_at=s.created_at,
                created_by=s.created_by,
                is_active=s.is_active,
                is_locked=s.is_locked,
                has_snapshot=snapshot is not None,
                snapshot_summary=snapshot.to_dict()["summary"] if snapshot else None,
            ))
        
        return results


# =============================================================================
# Active Scenario Management (for header display)
# NOTE: These routes MUST come before /{scenario_id} to avoid path conflicts
# =============================================================================

class SetActiveScenarioRequest(BaseModel):
    """Request to set active scenario."""
    scenario_type: str  # "budget" or "fuel"
    scenario_id: Optional[int] = None  # None to clear


@router.get("/active/current")
async def get_active_scenarios(request: Request):
    """Get currently active scenarios from cookies."""
    return get_scenario_context(request)


@router.post("/active/set")
async def set_active_scenario(req: SetActiveScenarioRequest, response: Response):
    """Set the active scenario for a given type.
    
    Sets a cookie to remember the user's selected scenario.
    """
    cookie_name = COOKIE_ACTIVE_BUDGET if req.scenario_type == "budget" else COOKIE_ACTIVE_FUEL
    
    if req.scenario_id:
        # Verify scenario exists
        with get_session() as db:
            scenario = db.query(Scenario).filter(Scenario.id == req.scenario_id).first()
            if not scenario:
                raise HTTPException(status_code=404, detail="Scenario not found")
        
        response.set_cookie(
            key=cookie_name,
            value=str(req.scenario_id),
            max_age=60 * 60 * 24 * 365,  # 1 year
            httponly=False,  # Allow JS access
            samesite="lax",
        )
        return {"status": "set", "type": req.scenario_type, "scenario_id": req.scenario_id}
    else:
        # Clear the cookie
        response.delete_cookie(key=cookie_name)
        return {"status": "cleared", "type": req.scenario_type}


@router.get("/active/context")
async def get_scenario_header_context(request: Request):
    """Get scenario context for header dropdowns.
    
    Returns lists of available scenarios and current selections.
    """
    return get_scenario_context(request)


# =============================================================================
# Individual Scenario Endpoints
# =============================================================================

@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(scenario_id: int):
    """Get a specific scenario by ID."""
    with get_session() as db:
        scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        snapshot = get_scenario_snapshot(db, scenario_id)
        
        return ScenarioResponse(
            id=scenario.id,
            name=scenario.name,
            description=scenario.description,
            scenario_type=scenario.scenario_type.value if scenario.scenario_type else "internal_forecast",
            status=scenario.status.value if scenario.status else "draft",
            version=scenario.version,
            parent_scenario_id=scenario.parent_scenario_id,
            created_at=scenario.created_at,
            created_by=scenario.created_by,
            is_active=scenario.is_active,
            is_locked=scenario.is_locked,
            has_snapshot=snapshot is not None,
            snapshot_summary=snapshot.to_dict()["summary"] if snapshot else None,
        )


@router.post("/", response_model=ScenarioResponse)
async def create_scenario(request: CreateScenarioRequest):
    """Create a new scenario and save current inputs as a snapshot.
    
    This captures the current state of all fuel model inputs:
    - Use factors
    - Heat rates
    - Coal pricing
    - Outage schedule
    """
    with get_session() as db:
        # Create scenario
        scenario_type = ScenarioType.INTERNAL_FORECAST
        if request.scenario_type == "budget":
            scenario_type = ScenarioType.BUDGET
        elif request.scenario_type == "external_forecast":
            scenario_type = ScenarioType.EXTERNAL_FORECAST
        
        scenario = Scenario(
            name=request.name,
            description=request.description,
            scenario_type=scenario_type,
            status=ScenarioStatus.DRAFT,
            version=1,
            parent_scenario_id=request.parent_scenario_id,
            created_by=request.created_by,
        )
        db.add(scenario)
        db.commit()
        db.refresh(scenario)
        
        # Save input snapshot
        snapshot = save_scenario_snapshot(
            db,
            scenario_id=scenario.id,
            year=request.year,
            change_summary=request.change_summary,
            created_by=request.created_by,
        )
        
        return ScenarioResponse(
            id=scenario.id,
            name=scenario.name,
            description=scenario.description,
            scenario_type=scenario.scenario_type.value,
            status=scenario.status.value,
            version=scenario.version,
            parent_scenario_id=scenario.parent_scenario_id,
            created_at=scenario.created_at,
            created_by=scenario.created_by,
            is_active=scenario.is_active,
            is_locked=scenario.is_locked,
            has_snapshot=True,
            snapshot_summary=snapshot.to_dict()["summary"],
        )


@router.get("/{scenario_id}/snapshot")
async def get_scenario_snapshot_detail(scenario_id: int):
    """Get the full input snapshot for a scenario."""
    with get_session() as db:
        scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        snapshot = get_scenario_snapshot(db, scenario_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="No snapshot found for this scenario")
        
        return snapshot.to_dict()


@router.post("/{scenario_id}/update-snapshot")
async def update_scenario_snapshot(
    scenario_id: int,
    year: int,
    change_summary: Optional[str] = None,
    updated_by: Optional[str] = None,
):
    """Update the snapshot for an existing scenario with current inputs.
    
    Note: Cannot update locked scenarios.
    """
    with get_session() as db:
        scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        if scenario.is_locked:
            raise HTTPException(status_code=403, detail="Scenario is locked")
        
        # Re-save snapshot
        snapshot = save_scenario_snapshot(
            db,
            scenario_id=scenario_id,
            year=year,
            change_summary=change_summary,
            created_by=updated_by,
        )
        
        return {
            "status": "updated",
            "scenario_id": scenario_id,
            "snapshot": snapshot.to_dict(),
        }


@router.get("/compare/{scenario_a_id}/{scenario_b_id}", response_model=ScenarioComparisonResponse)
async def compare_scenarios(scenario_a_id: int, scenario_b_id: int):
    """Compare two scenarios and return differences.
    
    Returns input differences between the two scenarios,
    useful for understanding what changed.
    """
    with get_session() as db:
        scenario_a = db.query(Scenario).filter(Scenario.id == scenario_a_id).first()
        scenario_b = db.query(Scenario).filter(Scenario.id == scenario_b_id).first()
        
        if not scenario_a:
            raise HTTPException(status_code=404, detail=f"Scenario {scenario_a_id} not found")
        if not scenario_b:
            raise HTTPException(status_code=404, detail=f"Scenario {scenario_b_id} not found")
        
        snapshot_a = get_scenario_snapshot(db, scenario_a_id)
        snapshot_b = get_scenario_snapshot(db, scenario_b_id)
        
        if not snapshot_a:
            raise HTTPException(status_code=404, detail=f"No snapshot for scenario {scenario_a_id}")
        if not snapshot_b:
            raise HTTPException(status_code=404, detail=f"No snapshot for scenario {scenario_b_id}")
        
        differences = compare_snapshots(snapshot_a, snapshot_b)
        
        return ScenarioComparisonResponse(
            scenario_a={
                "id": scenario_a.id,
                "name": scenario_a.name,
                "summary": snapshot_a.to_dict()["summary"],
            },
            scenario_b={
                "id": scenario_b.id,
                "name": scenario_b.name,
                "summary": snapshot_b.to_dict()["summary"],
            },
            differences=differences,
        )


@router.delete("/{scenario_id}")
async def delete_scenario(scenario_id: int):
    """Soft-delete a scenario (marks as inactive)."""
    with get_session() as db:
        scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        if scenario.is_locked:
            raise HTTPException(status_code=403, detail="Cannot delete locked scenario")
        
        scenario.is_active = False
        db.commit()
        
        return {"status": "deleted", "scenario_id": scenario_id}


@router.post("/{scenario_id}/lock")
async def lock_scenario(scenario_id: int):
    """Lock a scenario to prevent further modifications."""
    with get_session() as db:
        scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        
        scenario.is_locked = True
        scenario.status = ScenarioStatus.PUBLISHED
        db.commit()
        
        return {"status": "locked", "scenario_id": scenario_id}
