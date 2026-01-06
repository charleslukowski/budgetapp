"""API routes for outage template management.

Provides CRUD operations for reusable outage patterns:
- List all templates (system + user-created)
- Create user templates
- Apply templates to specific unit/month
- Initialize system templates
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field

from src.db.postgres import get_session
from src.models.outage_template import (
    OutageTemplate,
    get_all_templates,
    get_template_by_id,
    create_template,
    update_template,
    delete_template,
    initialize_system_templates,
)
from src.models.unit_outage import upsert_unit_outage


router = APIRouter(prefix="/api/outage-templates", tags=["Outage Templates"])


# =============================================================================
# Pydantic Models
# =============================================================================

class OutageTemplateResponse(BaseModel):
    """Response model for an outage template."""
    id: int
    name: str
    description: Optional[str]
    category: Optional[str]
    default_days: float
    typical_months: List[int]
    min_days: Optional[float]
    max_days: Optional[float]
    is_system_template: bool
    color: str

    class Config:
        from_attributes = True


class CreateTemplateRequest(BaseModel):
    """Request to create a new template."""
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    default_days: float = Field(ge=0, le=31, default=21)
    typical_months: Optional[List[int]] = None
    min_days: Optional[float] = None
    max_days: Optional[float] = None
    color: str = "#f59e0b"


class UpdateTemplateRequest(BaseModel):
    """Request to update a template."""
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    default_days: Optional[float] = None
    typical_months: Optional[List[int]] = None
    min_days: Optional[float] = None
    max_days: Optional[float] = None
    color: Optional[str] = None


class ApplyTemplateRequest(BaseModel):
    """Request to apply a template to specific cells."""
    template_id: int
    plant_id: int
    year: int
    applications: List[dict]  # [{unit_number, month}, ...]
    override_days: Optional[float] = None  # Override template default


# =============================================================================
# Template Endpoints
# =============================================================================

@router.get("/", response_model=List[OutageTemplateResponse])
async def list_templates():
    """Get all outage templates.
    
    Returns system templates first, then user-created templates.
    """
    with get_session() as db:
        templates = get_all_templates(db)
        return [OutageTemplateResponse(**t.to_dict()) for t in templates]


@router.get("/{template_id}", response_model=OutageTemplateResponse)
async def get_template(template_id: int):
    """Get a specific template by ID."""
    with get_session() as db:
        template = get_template_by_id(db, template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return OutageTemplateResponse(**template.to_dict())


@router.post("/", response_model=OutageTemplateResponse)
async def create_new_template(request: CreateTemplateRequest):
    """Create a new user template."""
    with get_session() as db:
        template = create_template(
            db,
            name=request.name,
            description=request.description,
            category=request.category,
            default_days=Decimal(str(request.default_days)),
            typical_months=request.typical_months,
            min_days=Decimal(str(request.min_days)) if request.min_days else None,
            max_days=Decimal(str(request.max_days)) if request.max_days else None,
            color=request.color,
            is_system_template=False,
        )
        return OutageTemplateResponse(**template.to_dict())


@router.put("/{template_id}", response_model=OutageTemplateResponse)
async def update_existing_template(template_id: int, request: UpdateTemplateRequest):
    """Update an existing template.
    
    Note: System templates cannot be modified.
    """
    with get_session() as db:
        template = get_template_by_id(db, template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        if template.is_system_template:
            raise HTTPException(status_code=403, detail="System templates cannot be modified")
        
        # Build update dict
        updates = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.description is not None:
            updates["description"] = request.description
        if request.category is not None:
            updates["category"] = request.category
        if request.default_days is not None:
            updates["default_days"] = Decimal(str(request.default_days))
        if request.typical_months is not None:
            updates["typical_months"] = request.typical_months
        if request.min_days is not None:
            updates["min_days"] = Decimal(str(request.min_days))
        if request.max_days is not None:
            updates["max_days"] = Decimal(str(request.max_days))
        if request.color is not None:
            updates["color"] = request.color
        
        result = update_template(db, template_id, **updates)
        return OutageTemplateResponse(**result.to_dict())


@router.delete("/{template_id}")
async def delete_existing_template(template_id: int):
    """Delete a user template.
    
    Note: System templates cannot be deleted.
    """
    with get_session() as db:
        template = get_template_by_id(db, template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        if template.is_system_template:
            raise HTTPException(status_code=403, detail="System templates cannot be deleted")
        
        delete_template(db, template_id)
        return {"status": "deleted", "template_id": template_id}


@router.post("/apply")
async def apply_template(request: ApplyTemplateRequest):
    """Apply a template to specific unit/month cells.
    
    Creates or updates outage records for each application.
    """
    with get_session() as db:
        template = get_template_by_id(db, request.template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Determine days to apply
        days = Decimal(str(request.override_days)) if request.override_days else template.default_days
        
        results = []
        for app in request.applications:
            unit_number = app.get("unit_number")
            month = app.get("month")
            
            if not unit_number or not month:
                continue
            if month < 1 or month > 12:
                continue
            
            result = upsert_unit_outage(
                db,
                plant_id=request.plant_id,
                unit_number=unit_number,
                year=request.year,
                month=month,
                planned_outage_days=days,
                outage_type=template.category,
                outage_description=template.name,
            )
            
            results.append({
                "unit_number": unit_number,
                "month": month,
                "planned_days": float(days),
                "template": template.name,
            })
        
        return {
            "status": "applied",
            "template_id": request.template_id,
            "template_name": template.name,
            "plant_id": request.plant_id,
            "year": request.year,
            "applied_count": len(results),
            "results": results,
        }


@router.post("/init-system")
async def init_system_templates():
    """Initialize system templates.
    
    Creates default templates if they don't exist.
    """
    with get_session() as db:
        count = initialize_system_templates(db)
        return {
            "status": "initialized",
            "templates_created": count,
        }

