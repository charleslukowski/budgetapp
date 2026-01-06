"""Web UI routes using Jinja2 templates."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import Plant, Scenario, CostCategory
from src.models.scenario import ScenarioType

router = APIRouter()
templates = Jinja2Templates(directory="src/web/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Main dashboard page."""
    plants = db.query(Plant).filter(Plant.is_active == True).all()
    scenarios = db.query(Scenario).filter(Scenario.is_active == True).order_by(Scenario.updated_at.desc()).all()
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "plants": plants,
            "scenarios": scenarios,
            "title": "OVEC Budget System",
        }
    )


@router.get("/scenarios", response_class=HTMLResponse)
async def scenarios_list(request: Request, db: Session = Depends(get_db)):
    """Scenarios list page."""
    scenarios = db.query(Scenario).filter(Scenario.is_active == True).order_by(Scenario.updated_at.desc()).all()
    
    return templates.TemplateResponse(
        "scenarios.html",
        {
            "request": request,
            "scenarios": scenarios,
            "title": "Scenarios",
        }
    )


@router.get("/scenarios/{scenario_id}", response_class=HTMLResponse)
async def scenario_detail(
    request: Request,
    scenario_id: int,
    db: Session = Depends(get_db),
):
    """Scenario detail page with forecast data."""
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": "Scenario not found", "title": "Error"},
            status_code=404,
        )
    
    plants = db.query(Plant).filter(Plant.is_active == True).all()
    categories = db.query(CostCategory).filter(CostCategory.is_active == True).order_by(
        CostCategory.section, CostCategory.sort_order
    ).all()
    
    return templates.TemplateResponse(
        "scenario_detail.html",
        {
            "request": request,
            "scenario": scenario,
            "plants": plants,
            "categories": categories,
            "title": f"Scenario: {scenario.name}",
        }
    )


@router.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request, db: Session = Depends(get_db)):
    """Report generation page."""
    scenarios = db.query(Scenario).filter(Scenario.is_active == True).all()
    
    return templates.TemplateResponse(
        "reports.html",
        {
            "request": request,
            "scenarios": scenarios,
            "title": "Generate Reports",
        }
    )

