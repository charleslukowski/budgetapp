"""Forecast API routes."""

from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from pydantic import BaseModel
from typing import Optional

from src.database import get_db
from src.models import Forecast, Scenario, Plant, CostCategory, Period
from src.models.cost_category import CostSection
from src.models.period import Granularity

router = APIRouter()


class ForecastUpdate(BaseModel):
    """Schema for updating a forecast."""
    generation_mwh: Optional[float] = None
    cost_dollars: Optional[float] = None
    notes: Optional[str] = None
    updated_by: Optional[str] = None


class ForecastResponse(BaseModel):
    """Forecast response schema."""
    id: int
    scenario_id: int
    plant_id: Optional[int]
    category_id: int
    period_id: int
    generation_mwh: Optional[float]
    cost_dollars: Optional[float]
    cost_per_mwh: Optional[float]
    notes: Optional[str]
    
    # Joined fields
    plant_name: Optional[str] = None
    category_name: str = ""
    category_section: str = ""
    period_display: str = ""
    
    class Config:
        from_attributes = True


class ForecastSummary(BaseModel):
    """Summary of forecasts by section."""
    section: str
    total_cost: float
    total_generation: float
    cost_per_mwh: Optional[float]


@router.get("/scenario/{scenario_id}", response_model=list[ForecastResponse])
def get_scenario_forecasts(
    scenario_id: int,
    plant_id: Optional[int] = None,
    section: Optional[CostSection] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get all forecasts for a scenario with optional filters."""
    query = (
        db.query(Forecast)
        .options(
            joinedload(Forecast.plant),
            joinedload(Forecast.category),
            joinedload(Forecast.period),
        )
        .filter(Forecast.scenario_id == scenario_id)
    )
    
    if plant_id:
        query = query.filter(Forecast.plant_id == plant_id)
    
    if section:
        query = query.join(CostCategory).filter(CostCategory.section == section)
    
    if year:
        query = query.join(Period).filter(Period.year == year)
    
    forecasts = query.all()
    
    return [
        ForecastResponse(
            id=f.id,
            scenario_id=f.scenario_id,
            plant_id=f.plant_id,
            category_id=f.category_id,
            period_id=f.period_id,
            generation_mwh=float(f.generation_mwh) if f.generation_mwh else None,
            cost_dollars=float(f.cost_dollars) if f.cost_dollars else None,
            cost_per_mwh=float(f.cost_per_mwh) if f.cost_per_mwh else None,
            notes=f.notes,
            plant_name=f.plant.name if f.plant else "Combined",
            category_name=f.category.name,
            category_section=f.category.section.value,
            period_display=f.period.display_name,
        )
        for f in forecasts
    ]


@router.get("/scenario/{scenario_id}/summary")
def get_scenario_summary(
    scenario_id: int,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get summary totals by cost section for a scenario."""
    query = (
        db.query(
            CostCategory.section,
            func.sum(Forecast.cost_dollars).label("total_cost"),
            func.sum(Forecast.generation_mwh).label("total_generation"),
        )
        .join(CostCategory, Forecast.category_id == CostCategory.id)
        .filter(Forecast.scenario_id == scenario_id)
        .group_by(CostCategory.section)
    )
    
    if year:
        query = query.join(Period).filter(Period.year == year)
    
    results = query.all()
    
    summaries = []
    for section, total_cost, total_generation in results:
        cost = float(total_cost) if total_cost else 0
        gen = float(total_generation) if total_generation else 0
        cpm = cost / gen if gen > 0 else None
        
        summaries.append({
            "section": section.value,
            "total_cost": cost,
            "total_generation": gen,
            "cost_per_mwh": cpm,
        })
    
    return summaries


@router.put("/{forecast_id}", response_model=ForecastResponse)
def update_forecast(
    forecast_id: int,
    update: ForecastUpdate,
    db: Session = Depends(get_db),
):
    """Update a forecast value."""
    forecast = (
        db.query(Forecast)
        .options(
            joinedload(Forecast.plant),
            joinedload(Forecast.category),
            joinedload(Forecast.period),
        )
        .filter(Forecast.id == forecast_id)
        .first()
    )
    
    if not forecast:
        raise HTTPException(status_code=404, detail="Forecast not found")
    
    # Check if scenario is locked
    if forecast.scenario.is_locked:
        raise HTTPException(status_code=400, detail="Scenario is locked")
    
    # Update fields
    if update.generation_mwh is not None:
        forecast.generation_mwh = Decimal(str(update.generation_mwh))
    if update.cost_dollars is not None:
        forecast.cost_dollars = Decimal(str(update.cost_dollars))
    if update.notes is not None:
        forecast.notes = update.notes
    if update.updated_by:
        forecast.updated_by = update.updated_by
    
    db.commit()
    db.refresh(forecast)
    
    return ForecastResponse(
        id=forecast.id,
        scenario_id=forecast.scenario_id,
        plant_id=forecast.plant_id,
        category_id=forecast.category_id,
        period_id=forecast.period_id,
        generation_mwh=float(forecast.generation_mwh) if forecast.generation_mwh else None,
        cost_dollars=float(forecast.cost_dollars) if forecast.cost_dollars else None,
        cost_per_mwh=float(forecast.cost_per_mwh) if forecast.cost_per_mwh else None,
        notes=forecast.notes,
        plant_name=forecast.plant.name if forecast.plant else "Combined",
        category_name=forecast.category.name,
        category_section=forecast.category.section.value,
        period_display=forecast.period.display_name,
    )

