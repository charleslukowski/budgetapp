"""Plant API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.database import get_db
from src.models import Plant

router = APIRouter()


class PlantResponse(BaseModel):
    """Plant response schema."""
    id: int
    name: str
    short_name: str
    capacity_mw: int
    unit_count: int
    unit_capacity_mw: int
    is_active: bool
    max_annual_generation_mwh: float
    
    class Config:
        from_attributes = True


@router.get("/", response_model=list[PlantResponse])
def list_plants(db: Session = Depends(get_db)):
    """Get all plants."""
    plants = db.query(Plant).filter(Plant.is_active == True).all()
    return [
        PlantResponse(
            id=p.id,
            name=p.name,
            short_name=p.short_name,
            capacity_mw=p.capacity_mw,
            unit_count=p.unit_count,
            unit_capacity_mw=p.unit_capacity_mw,
            is_active=p.is_active,
            max_annual_generation_mwh=p.max_annual_generation_mwh,
        )
        for p in plants
    ]


@router.get("/{plant_id}", response_model=PlantResponse)
def get_plant(plant_id: int, db: Session = Depends(get_db)):
    """Get a specific plant."""
    plant = db.query(Plant).filter(Plant.id == plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")
    return PlantResponse(
        id=plant.id,
        name=plant.name,
        short_name=plant.short_name,
        capacity_mw=plant.capacity_mw,
        unit_count=plant.unit_count,
        unit_capacity_mw=plant.unit_capacity_mw,
        is_active=plant.is_active,
        max_annual_generation_mwh=plant.max_annual_generation_mwh,
    )

