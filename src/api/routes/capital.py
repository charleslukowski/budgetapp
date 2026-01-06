"""Capital assets and depreciation API routes."""

from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from src.database import get_db
from src.models.capital_asset import CapitalAsset, CapitalProject, AssetStatus
from src.engine.depreciation import (
    generate_depreciation_schedule,
    import_depreciation_to_forecast,
    project_future_depreciation,
    generate_cash_flow_comparison,
)

router = APIRouter()


# Request/Response Models

class AssetCreate(BaseModel):
    """Create capital asset request."""
    asset_number: str
    name: str
    description: Optional[str] = None
    plant_id: Optional[int] = None
    original_cost: float
    salvage_value: float = 0
    useful_life_years: int
    in_service_date: date


class AssetResponse(BaseModel):
    """Capital asset response."""
    id: int
    asset_number: str
    name: str
    description: Optional[str]
    plant_id: Optional[int]
    original_cost: float
    salvage_value: float
    useful_life_years: int
    in_service_date: date
    depreciation_method: str
    accumulated_depreciation: float
    net_book_value: float
    annual_depreciation: float
    remaining_life_years: float
    status: str
    
    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    """Create capital project request."""
    project_number: str
    name: str
    description: Optional[str] = None
    plant_id: Optional[int] = None
    estimated_cost: float
    contingency_percent: float = 10.0
    proposed_start_date: Optional[date] = None
    proposed_in_service_date: Optional[date] = None
    estimated_useful_life: Optional[int] = None
    npv: Optional[float] = None
    irr: Optional[float] = None
    payback_years: Optional[float] = None


class ProjectResponse(BaseModel):
    """Capital project response."""
    id: int
    project_number: str
    name: str
    description: Optional[str]
    plant_id: Optional[int]
    estimated_cost: float
    contingency_percent: float
    total_estimated_cost: float
    proposed_start_date: Optional[date]
    proposed_in_service_date: Optional[date]
    estimated_useful_life: Optional[int]
    projected_annual_depreciation: float
    npv: Optional[float]
    irr: Optional[float]
    payback_years: Optional[float]
    status: str
    
    class Config:
        from_attributes = True


class DepreciationRow(BaseModel):
    """Depreciation schedule row."""
    year: int
    month: Optional[int]
    beginning_book_value: float
    depreciation_expense: float
    accumulated_depreciation: float
    ending_book_value: float


class DepreciationImportResult(BaseModel):
    """Result of depreciation import."""
    assets_processed: int
    forecasts_created: int
    forecasts_updated: int
    total_depreciation: float


class CashFlowComparison(BaseModel):
    """Cash flow vs depreciation comparison."""
    year: int
    depreciation_billing: float
    cash_flow_billing: float
    difference: float


# Asset Endpoints

@router.get("/assets", response_model=List[AssetResponse])
def list_assets(
    plant_id: Optional[int] = None,
    status: Optional[AssetStatus] = None,
    db: Session = Depends(get_db),
):
    """List all capital assets."""
    query = db.query(CapitalAsset)
    
    if plant_id:
        query = query.filter(CapitalAsset.plant_id == plant_id)
    if status:
        query = query.filter(CapitalAsset.status == status.value)
    
    assets = query.order_by(CapitalAsset.in_service_date.desc()).all()
    
    return [
        AssetResponse(
            id=a.id,
            asset_number=a.asset_number,
            name=a.name,
            description=a.description,
            plant_id=a.plant_id,
            original_cost=float(a.original_cost),
            salvage_value=float(a.salvage_value or 0),
            useful_life_years=a.useful_life_years,
            in_service_date=a.in_service_date,
            depreciation_method=a.depreciation_method,
            accumulated_depreciation=float(a.accumulated_depreciation or 0),
            net_book_value=float(a.net_book_value),
            annual_depreciation=float(a.annual_depreciation),
            remaining_life_years=a.remaining_life_years,
            status=a.status,
        )
        for a in assets
    ]


@router.post("/assets", response_model=AssetResponse)
def create_asset(asset: AssetCreate, db: Session = Depends(get_db)):
    """Create a new capital asset."""
    db_asset = CapitalAsset(
        asset_number=asset.asset_number,
        name=asset.name,
        description=asset.description,
        plant_id=asset.plant_id,
        original_cost=Decimal(str(asset.original_cost)),
        salvage_value=Decimal(str(asset.salvage_value)),
        useful_life_years=asset.useful_life_years,
        in_service_date=asset.in_service_date,
    )
    
    db.add(db_asset)
    db.commit()
    db.refresh(db_asset)
    
    return AssetResponse(
        id=db_asset.id,
        asset_number=db_asset.asset_number,
        name=db_asset.name,
        description=db_asset.description,
        plant_id=db_asset.plant_id,
        original_cost=float(db_asset.original_cost),
        salvage_value=float(db_asset.salvage_value or 0),
        useful_life_years=db_asset.useful_life_years,
        in_service_date=db_asset.in_service_date,
        depreciation_method=db_asset.depreciation_method,
        accumulated_depreciation=float(db_asset.accumulated_depreciation or 0),
        net_book_value=float(db_asset.net_book_value),
        annual_depreciation=float(db_asset.annual_depreciation),
        remaining_life_years=db_asset.remaining_life_years,
        status=db_asset.status,
    )


@router.get("/assets/{asset_id}/schedule", response_model=List[DepreciationRow])
def get_asset_schedule(
    asset_id: int,
    year_from: int = Query(default=2025),
    year_to: int = Query(default=2040),
    monthly: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Get depreciation schedule for an asset."""
    asset = db.query(CapitalAsset).filter(CapitalAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    schedule = generate_depreciation_schedule(
        asset=asset,
        start_year=year_from,
        end_year=year_to,
        monthly=monthly,
    )
    
    return [
        DepreciationRow(
            year=row.year,
            month=row.month,
            beginning_book_value=float(row.beginning_book_value),
            depreciation_expense=float(row.depreciation_expense),
            accumulated_depreciation=float(row.accumulated_depreciation),
            ending_book_value=float(row.ending_book_value),
        )
        for row in schedule
    ]


# Project Endpoints

@router.get("/projects", response_model=List[ProjectResponse])
def list_projects(
    plant_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all capital projects."""
    query = db.query(CapitalProject)
    
    if plant_id:
        query = query.filter(CapitalProject.plant_id == plant_id)
    if status:
        query = query.filter(CapitalProject.status == status)
    
    projects = query.order_by(CapitalProject.proposed_in_service_date).all()
    
    return [
        ProjectResponse(
            id=p.id,
            project_number=p.project_number,
            name=p.name,
            description=p.description,
            plant_id=p.plant_id,
            estimated_cost=float(p.estimated_cost),
            contingency_percent=float(p.contingency_percent or 0),
            total_estimated_cost=float(p.total_estimated_cost),
            proposed_start_date=p.proposed_start_date,
            proposed_in_service_date=p.proposed_in_service_date,
            estimated_useful_life=p.estimated_useful_life,
            projected_annual_depreciation=float(p.projected_annual_depreciation),
            npv=float(p.npv) if p.npv else None,
            irr=float(p.irr) if p.irr else None,
            payback_years=float(p.payback_years) if p.payback_years else None,
            status=p.status,
        )
        for p in projects
    ]


@router.post("/projects", response_model=ProjectResponse)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new capital project."""
    db_project = CapitalProject(
        project_number=project.project_number,
        name=project.name,
        description=project.description,
        plant_id=project.plant_id,
        estimated_cost=Decimal(str(project.estimated_cost)),
        contingency_percent=Decimal(str(project.contingency_percent)),
        proposed_start_date=project.proposed_start_date,
        proposed_in_service_date=project.proposed_in_service_date,
        estimated_useful_life=project.estimated_useful_life,
        npv=Decimal(str(project.npv)) if project.npv else None,
        irr=Decimal(str(project.irr)) if project.irr else None,
        payback_years=Decimal(str(project.payback_years)) if project.payback_years else None,
    )
    
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    return ProjectResponse(
        id=db_project.id,
        project_number=db_project.project_number,
        name=db_project.name,
        description=db_project.description,
        plant_id=db_project.plant_id,
        estimated_cost=float(db_project.estimated_cost),
        contingency_percent=float(db_project.contingency_percent or 0),
        total_estimated_cost=float(db_project.total_estimated_cost),
        proposed_start_date=db_project.proposed_start_date,
        proposed_in_service_date=db_project.proposed_in_service_date,
        estimated_useful_life=db_project.estimated_useful_life,
        projected_annual_depreciation=float(db_project.projected_annual_depreciation),
        npv=float(db_project.npv) if db_project.npv else None,
        irr=float(db_project.irr) if db_project.irr else None,
        payback_years=float(db_project.payback_years) if db_project.payback_years else None,
        status=db_project.status,
    )


@router.put("/projects/{project_id}/approve")
def approve_project(
    project_id: int,
    approved_by: str = Query(...),
    db: Session = Depends(get_db),
):
    """Approve a capital project."""
    project = db.query(CapitalProject).filter(CapitalProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project.status = "approved"
    project.approved_date = date.today()
    project.approved_by = approved_by
    
    db.commit()
    return {"message": f"Project '{project.name}' approved"}


# Depreciation Analysis Endpoints

@router.post("/depreciation/import/{scenario_id}", response_model=DepreciationImportResult)
def import_depreciation(
    scenario_id: int,
    year_from: int = Query(default=2025),
    year_to: int = Query(default=2040),
    include_monthly: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """Import depreciation calculations to forecast."""
    stats = import_depreciation_to_forecast(
        scenario_id=scenario_id,
        year_from=year_from,
        year_to=year_to,
        include_monthly=include_monthly,
        db=db,
    )
    
    return DepreciationImportResult(
        assets_processed=stats["assets_processed"],
        forecasts_created=stats["forecasts_created"],
        forecasts_updated=stats["forecasts_updated"],
        total_depreciation=float(stats["total_depreciation"]),
    )


@router.get("/depreciation/projection")
def get_depreciation_projection(
    year_from: int = Query(default=2025),
    year_to: int = Query(default=2040),
    include_projects: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """Get projected depreciation for future years."""
    projections = project_future_depreciation(
        db=db,
        year_from=year_from,
        year_to=year_to,
        include_proposed_projects=include_projects,
    )
    
    return [
        {"year": year, "depreciation": float(amount)}
        for year, amount in projections.items()
    ]


@router.get("/billing-comparison", response_model=List[CashFlowComparison])
def get_billing_comparison(
    scenario_id: int,
    year_from: int = Query(default=2024),
    year_to: int = Query(default=2030),
    db: Session = Depends(get_db),
):
    """
    Compare depreciation billing vs cash flow billing.
    
    Helps analyze the 2026 billing transition.
    """
    comparison = generate_cash_flow_comparison(
        db=db,
        scenario_id=scenario_id,
        year_from=year_from,
        year_to=year_to,
    )
    
    return [CashFlowComparison(**row) for row in comparison]

