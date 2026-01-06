"""
Depreciation calculation engine.

Handles depreciation schedules for capital assets and generates
forecast data for the capital cost category.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import date

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database import SessionLocal
from src.models import Plant, Period, CostCategory, Scenario, Forecast
from src.models.capital_asset import CapitalAsset, CapitalProject, AssetStatus
from src.models.period import Granularity
from src.models.cost_category import CostSection


@dataclass
class DepreciationScheduleRow:
    """A single row in a depreciation schedule."""
    year: int
    month: Optional[int]
    beginning_book_value: Decimal
    depreciation_expense: Decimal
    accumulated_depreciation: Decimal
    ending_book_value: Decimal


def generate_depreciation_schedule(
    asset: CapitalAsset,
    start_year: int,
    end_year: int,
    monthly: bool = False,
) -> List[DepreciationScheduleRow]:
    """
    Generate a depreciation schedule for an asset.
    
    Args:
        asset: The capital asset
        start_year: First year of schedule
        end_year: Last year of schedule
        monthly: If True, generate monthly detail
    
    Returns:
        List of DepreciationScheduleRow objects
    """
    schedule = []
    
    accumulated = Decimal(str(asset.accumulated_depreciation or 0))
    book_value = asset.net_book_value
    
    for year in range(start_year, end_year + 1):
        if monthly:
            for month in range(1, 13):
                if book_value <= Decimal(str(asset.salvage_value or 0)):
                    break
                
                beginning_bv = book_value
                depreciation = asset.calculate_depreciation_for_period(year, month)
                
                # Don't depreciate below salvage value
                max_depr = book_value - Decimal(str(asset.salvage_value or 0))
                depreciation = min(depreciation, max_depr)
                
                accumulated += depreciation
                book_value -= depreciation
                
                schedule.append(DepreciationScheduleRow(
                    year=year,
                    month=month,
                    beginning_book_value=beginning_bv,
                    depreciation_expense=depreciation,
                    accumulated_depreciation=accumulated,
                    ending_book_value=book_value,
                ))
        else:
            if book_value <= Decimal(str(asset.salvage_value or 0)):
                break
            
            beginning_bv = book_value
            depreciation = asset.calculate_depreciation_for_period(year)
            
            # Don't depreciate below salvage value
            max_depr = book_value - Decimal(str(asset.salvage_value or 0))
            depreciation = min(depreciation, max_depr)
            
            accumulated += depreciation
            book_value -= depreciation
            
            schedule.append(DepreciationScheduleRow(
                year=year,
                month=None,
                beginning_book_value=beginning_bv,
                depreciation_expense=depreciation,
                accumulated_depreciation=accumulated,
                ending_book_value=book_value,
            ))
    
    return schedule


def calculate_total_depreciation_by_period(
    db: Session,
    year: int,
    month: Optional[int] = None,
    plant_id: Optional[int] = None,
) -> Decimal:
    """
    Calculate total depreciation expense for a period across all assets.
    
    Args:
        db: Database session
        year: Year to calculate
        month: Optional month (None for annual total)
        plant_id: Optional filter by plant
    
    Returns:
        Total depreciation for the period
    """
    query = db.query(CapitalAsset).filter(
        CapitalAsset.status == AssetStatus.ACTIVE.value
    )
    
    if plant_id:
        query = query.filter(CapitalAsset.plant_id == plant_id)
    
    assets = query.all()
    
    total = Decimal("0")
    for asset in assets:
        total += asset.calculate_depreciation_for_period(year, month)
    
    return total


def import_depreciation_to_forecast(
    scenario_id: int,
    year_from: int,
    year_to: int,
    include_monthly: bool = True,
    db: Session = None,
) -> dict:
    """
    Calculate depreciation for all assets and import to forecast.
    
    Args:
        scenario_id: Target scenario
        year_from: Start year
        year_to: End year
        include_monthly: Include monthly detail for first 2 years
        db: Database session
    
    Returns:
        Import statistics
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    try:
        # Get depreciation cost categories
        depr_existing = (
            db.query(CostCategory)
            .filter(CostCategory.short_name == "Depr Existing")
            .first()
        )
        
        depr_new = (
            db.query(CostCategory)
            .filter(CostCategory.short_name == "Depr New")
            .first()
        )
        
        # Get periods
        periods = {}
        for p in db.query(Period).filter(
            Period.year >= year_from,
            Period.year <= year_to
        ).all():
            if p.granularity == Granularity.MONTHLY:
                periods[(p.year, p.month)] = p
            else:
                periods[(p.year, None)] = p
        
        # Get plants
        plants = db.query(Plant).filter(Plant.is_active == True).all()
        
        stats = {
            "assets_processed": 0,
            "forecasts_created": 0,
            "forecasts_updated": 0,
            "total_depreciation": Decimal("0"),
        }
        
        # Process each plant
        for plant in plants:
            # Get active assets for this plant
            assets = (
                db.query(CapitalAsset)
                .filter(
                    CapitalAsset.plant_id == plant.id,
                    CapitalAsset.status == AssetStatus.ACTIVE.value,
                )
                .all()
            )
            
            stats["assets_processed"] += len(assets)
            
            # Calculate by period
            for year in range(year_from, year_to + 1):
                # Determine if monthly or annual
                use_monthly = include_monthly and year < year_from + 2
                
                if use_monthly:
                    for month in range(1, 13):
                        period = periods.get((year, month))
                        if not period:
                            continue
                        
                        total_depr = Decimal("0")
                        for asset in assets:
                            total_depr += asset.calculate_depreciation_for_period(year, month)
                        
                        if total_depr > 0 and depr_existing:
                            _upsert_forecast(
                                db, scenario_id, plant.id,
                                depr_existing.id, period.id, total_depr, stats
                            )
                        
                        stats["total_depreciation"] += total_depr
                else:
                    period = periods.get((year, None))
                    if not period:
                        continue
                    
                    total_depr = Decimal("0")
                    for asset in assets:
                        total_depr += asset.calculate_depreciation_for_period(year)
                    
                    if total_depr > 0 and depr_existing:
                        _upsert_forecast(
                            db, scenario_id, plant.id,
                            depr_existing.id, period.id, total_depr, stats
                        )
                    
                    stats["total_depreciation"] += total_depr
        
        db.commit()
        return stats
        
    finally:
        if close_db:
            db.close()


def _upsert_forecast(
    db: Session,
    scenario_id: int,
    plant_id: int,
    category_id: int,
    period_id: int,
    amount: Decimal,
    stats: dict,
) -> None:
    """Helper to create or update a forecast record."""
    existing = (
        db.query(Forecast)
        .filter(
            Forecast.scenario_id == scenario_id,
            Forecast.plant_id == plant_id,
            Forecast.category_id == category_id,
            Forecast.period_id == period_id,
        )
        .first()
    )
    
    if existing:
        existing.cost_dollars = amount
        existing.notes = "Auto-calculated depreciation"
        stats["forecasts_updated"] += 1
    else:
        forecast = Forecast(
            scenario_id=scenario_id,
            plant_id=plant_id,
            category_id=category_id,
            period_id=period_id,
            cost_dollars=amount,
            notes="Auto-calculated depreciation",
        )
        db.add(forecast)
        stats["forecasts_created"] += 1


def project_future_depreciation(
    db: Session,
    year_from: int,
    year_to: int,
    include_proposed_projects: bool = True,
) -> Dict[int, Decimal]:
    """
    Project future depreciation including proposed capital projects.
    
    Args:
        db: Database session
        year_from: Start year
        year_to: End year
        include_proposed_projects: Include approved but not yet in-service projects
    
    Returns:
        Dict mapping year to total depreciation
    """
    projections = {year: Decimal("0") for year in range(year_from, year_to + 1)}
    
    # Existing assets
    existing_assets = (
        db.query(CapitalAsset)
        .filter(CapitalAsset.status == AssetStatus.ACTIVE.value)
        .all()
    )
    
    for asset in existing_assets:
        for year in range(year_from, year_to + 1):
            projections[year] += asset.calculate_depreciation_for_period(year)
    
    # Proposed projects (if approved)
    if include_proposed_projects:
        proposed = (
            db.query(CapitalProject)
            .filter(CapitalProject.status.in_(["approved", "in_progress"]))
            .all()
        )
        
        for project in proposed:
            if not project.proposed_in_service_date:
                continue
            
            in_service_year = project.proposed_in_service_date.year
            annual_depr = project.projected_annual_depreciation
            
            for year in range(max(year_from, in_service_year), year_to + 1):
                # Prorate first year
                if year == in_service_year:
                    months_active = 12 - project.proposed_in_service_date.month + 1
                    projections[year] += annual_depr * Decimal(str(months_active / 12))
                else:
                    projections[year] += annual_depr
    
    return projections


def generate_cash_flow_comparison(
    db: Session,
    scenario_id: int,
    year_from: int,
    year_to: int,
) -> List[dict]:
    """
    Generate comparison of depreciation billing vs cash flow billing.
    
    Helps with the 2026 transition analysis.
    """
    comparison = []
    
    for year in range(year_from, year_to + 1):
        depreciation = calculate_total_depreciation_by_period(db, year)
        
        # Cash flow would be the sum of capital project spending for that year
        # This is a simplified proxy
        projects = (
            db.query(CapitalProject)
            .filter(
                CapitalProject.status.in_(["approved", "in_progress", "completed"]),
                func.extract('year', CapitalProject.proposed_in_service_date) == year,
            )
            .all()
        )
        
        cash_flow = sum(
            Decimal(str(p.total_estimated_cost)) for p in projects
        )
        
        comparison.append({
            "year": year,
            "depreciation_billing": float(depreciation),
            "cash_flow_billing": float(cash_flow),
            "difference": float(cash_flow - depreciation),
        })
    
    return comparison

