"""API routes for scenario management.

Provides operations for saving, loading, and comparing forecast scenarios:
- List all scenarios
- Create/update scenarios
- Delete scenarios
"""

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from src.db.postgres import get_session
from src.models.scenario import Scenario, ScenarioType, ScenarioStatus


# =============================================================================
# Active Scenario Cookie Names
# =============================================================================
COOKIE_ACTIVE_BUDGET = "active_budget_scenario"


def get_active_scenarios_from_request(request: Request) -> Dict[str, Optional[int]]:
    """Get active scenario IDs from cookies."""
    budget_id = request.cookies.get(COOKIE_ACTIVE_BUDGET)

    return {
        "budget": int(budget_id) if budget_id else None,
    }


def get_scenario_context(request: Request) -> Dict[str, Any]:
    """Get scenario context for templates (header dropdowns).

    Returns dict with:
    - budget_scenarios: list of budget scenarios
    - active_budget: active budget scenario (or None)
    """
    active_ids = get_active_scenarios_from_request(request)

    with get_session() as db:
        # Get all active scenarios
        all_scenarios = db.query(Scenario).filter(
            Scenario.is_active == True
        ).order_by(Scenario.created_at.desc()).all()

        budget_scenarios = []
        active_budget = None

        for s in all_scenarios:
            scenario_dict = {
                "id": s.id,
                "name": s.name,
                "version": s.version,
                "display_name": f"{s.name} v{s.version}",
                "status": s.status.value if s.status else "draft",
                "type": s.scenario_type.value if s.scenario_type else "budget",
            }

            budget_scenarios.append(scenario_dict)
            if active_ids["budget"] == s.id:
                active_budget = scenario_dict

        # If no active scenario set but we have scenarios, use the first published or first one
        if not active_budget and budget_scenarios:
            published = [s for s in budget_scenarios if s["status"] == "published"]
            active_budget = published[0] if published else budget_scenarios[0]

        return {
            "budget_scenarios": budget_scenarios,
            "active_budget": active_budget,
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

    class Config:
        from_attributes = True


class CreateScenarioRequest(BaseModel):
    """Request to create/save a new scenario."""
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    scenario_type: str = "budget"
    year: int
    parent_scenario_id: Optional[int] = None
    created_by: Optional[str] = None


class SetActiveScenarioRequest(BaseModel):
    """Request to set active scenario."""
    scenario_id: Optional[int] = None  # None to clear


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
            results.append(ScenarioResponse(
                id=s.id,
                name=s.name,
                description=s.description,
                scenario_type=s.scenario_type.value if s.scenario_type else "budget",
                status=s.status.value if s.status else "draft",
                version=s.version,
                parent_scenario_id=s.parent_scenario_id,
                created_at=s.created_at,
                created_by=s.created_by,
                is_active=s.is_active,
                is_locked=s.is_locked,
            ))

        return results


# =============================================================================
# Active Scenario Management (for header display)
# NOTE: These routes MUST come before /{scenario_id} to avoid path conflicts
# =============================================================================

@router.get("/active/current")
async def get_active_scenarios(request: Request):
    """Get currently active scenarios from cookies."""
    return get_scenario_context(request)


@router.post("/active/set")
async def set_active_scenario(req: SetActiveScenarioRequest, response: Response):
    """Set the active scenario.

    Sets a cookie to remember the user's selected scenario.
    """
    if req.scenario_id:
        # Verify scenario exists
        with get_session() as db:
            scenario = db.query(Scenario).filter(Scenario.id == req.scenario_id).first()
            if not scenario:
                raise HTTPException(status_code=404, detail="Scenario not found")

        response.set_cookie(
            key=COOKIE_ACTIVE_BUDGET,
            value=str(req.scenario_id),
            max_age=60 * 60 * 24 * 365,  # 1 year
            httponly=False,  # Allow JS access
            samesite="lax",
        )
        return {"status": "set", "scenario_id": req.scenario_id}
    else:
        # Clear the cookie
        response.delete_cookie(key=COOKIE_ACTIVE_BUDGET)
        return {"status": "cleared"}


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

        return ScenarioResponse(
            id=scenario.id,
            name=scenario.name,
            description=scenario.description,
            scenario_type=scenario.scenario_type.value if scenario.scenario_type else "budget",
            status=scenario.status.value if scenario.status else "draft",
            version=scenario.version,
            parent_scenario_id=scenario.parent_scenario_id,
            created_at=scenario.created_at,
            created_by=scenario.created_by,
            is_active=scenario.is_active,
            is_locked=scenario.is_locked,
        )


@router.post("/", response_model=ScenarioResponse)
async def create_scenario(request: CreateScenarioRequest):
    """Create a new scenario."""
    with get_session() as db:
        # Create scenario
        scenario_type = ScenarioType.BUDGET
        if request.scenario_type == "internal_forecast":
            scenario_type = ScenarioType.INTERNAL_FORECAST
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
