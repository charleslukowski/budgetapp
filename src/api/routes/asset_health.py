"""Asset Health integration API routes."""

import os
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from src.database import get_db
from src.etl.asset_health import (
    AssetHealthConnector,
    AssetHealthItem,
    RiskLevel,
    import_asset_health_to_forecast,
    get_plant_budget_conflicts,
)

router = APIRouter()


class AssetHealthItemResponse(BaseModel):
    """Asset health item response schema."""
    id: int
    plant_name: str
    equipment_name: str
    description: str
    year: int
    risk: str
    estimated_cost: float
    risk_factor: float


class ImportResult(BaseModel):
    """Import result schema."""
    items_fetched: int
    forecasts_created: int
    forecasts_updated: int
    total_cost: float
    risk_adjusted_cost: float


class ConflictItem(BaseModel):
    """Potential budget conflict."""
    asset_health_item: dict
    existing_forecast: dict
    potential_duplicate: bool


def get_connector() -> AssetHealthConnector:
    """Get Asset Health database connector."""
    conn_string = os.getenv("ASSET_HEALTH_DB_URL")
    if not conn_string:
        raise HTTPException(
            status_code=503,
            detail="Asset Health database not configured. Set ASSET_HEALTH_DB_URL environment variable.",
        )
    return AssetHealthConnector(conn_string)


@router.get("/status")
def check_connection():
    """Check Asset Health database connection status."""
    try:
        connector = get_connector()
        connected = connector.test_connection()
        return {
            "status": "connected" if connected else "disconnected",
            "configured": True,
        }
    except HTTPException:
        return {
            "status": "not_configured",
            "configured": False,
        }


@router.get("/items", response_model=List[AssetHealthItemResponse])
def list_asset_health_items(
    plant_id: Optional[int] = None,
    year_from: int = Query(default=2025),
    year_to: int = Query(default=2030),
    min_risk: Optional[RiskLevel] = None,
):
    """List asset health items from the external database."""
    connector = get_connector()
    
    try:
        items = connector.fetch_items(
            plant_id=plant_id,
            year_from=year_from,
            year_to=year_to,
            min_risk=min_risk,
        )
        
        return [
            AssetHealthItemResponse(
                id=item.id,
                plant_name=item.plant_name,
                equipment_name=item.equipment_name,
                description=item.description,
                year=item.year,
                risk=item.risk.value,
                estimated_cost=float(item.estimated_cost),
                risk_factor=item.risk_factor,
            )
            for item in items
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching items: {str(e)}")


@router.post("/import/{scenario_id}", response_model=ImportResult)
def import_to_scenario(
    scenario_id: int,
    year_from: int = Query(default=2025),
    year_to: int = Query(default=2040),
    apply_risk_weighting: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """
    Import asset health items into a forecast scenario.
    
    - Aggregates items by plant and year
    - Optionally applies risk-weighted probability
    - Creates/updates forecasts in the Asset Health cost category
    """
    connector = get_connector()
    
    try:
        stats = import_asset_health_to_forecast(
            connector=connector,
            scenario_id=scenario_id,
            year_from=year_from,
            year_to=year_to,
            apply_risk_weighting=apply_risk_weighting,
            db=db,
        )
        
        return ImportResult(
            items_fetched=stats["items_fetched"],
            forecasts_created=stats["forecasts_created"],
            forecasts_updated=stats["forecasts_updated"],
            total_cost=float(stats["total_cost"]),
            risk_adjusted_cost=float(stats["risk_adjusted_cost"]),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import error: {str(e)}")


@router.get("/conflicts/{scenario_id}", response_model=List[ConflictItem])
def find_budget_conflicts(
    scenario_id: int,
    year: int = Query(default=2025),
    db: Session = Depends(get_db),
):
    """
    Find potential double-budgeting conflicts.
    
    Compares Asset Health items with existing plant-submitted budgets
    to identify items that may have been budgeted in both places.
    """
    connector = get_connector()
    
    try:
        conflicts = get_plant_budget_conflicts(
            connector=connector,
            scenario_id=scenario_id,
            year=year,
            db=db,
        )
        
        return [
            ConflictItem(
                asset_health_item=c["asset_health_item"],
                existing_forecast=c["existing_forecast"],
                potential_duplicate=c["potential_duplicate"],
            )
            for c in conflicts
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking conflicts: {str(e)}")

