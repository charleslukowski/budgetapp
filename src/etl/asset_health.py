"""
Asset Health Integration Module

Connects to the custom Asset Health database to import projected repairs
and maintenance items into the forecasting system.

Asset Health data points:
- Year of repair
- Risk level (high/medium/low)
- Description
- Dollar estimate
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.models import Plant, Period, CostCategory, Scenario, Forecast
from src.models.period import Granularity
from src.models.cost_category import CostSection


class RiskLevel(str, Enum):
    """Risk levels for asset health items."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class AssetHealthItem:
    """Represents a single asset health/repair item."""
    id: int
    plant_id: int
    plant_name: str
    equipment_name: str
    description: str
    year: int
    risk: RiskLevel
    estimated_cost: Decimal
    created_date: Optional[datetime] = None
    
    @property
    def risk_factor(self) -> float:
        """Get probability weight based on risk level."""
        return {
            RiskLevel.HIGH: 0.90,    # 90% likely to occur
            RiskLevel.MEDIUM: 0.70,  # 70% likely
            RiskLevel.LOW: 0.50,     # 50% likely
        }.get(self.risk, 0.70)


class AssetHealthConnector:
    """
    Connector to the Asset Health custom database.
    
    This class handles the connection to the external SQL Server database
    where engineers enter projected repairs and maintenance items.
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize the connector.
        
        Args:
            connection_string: SQLAlchemy connection string to the Asset Health DB.
                             If None, will read from environment variable.
        """
        self.connection_string = connection_string
        self._engine = None
    
    @property
    def engine(self):
        """Lazy-load the database engine."""
        if self._engine is None and self.connection_string:
            self._engine = create_engine(self.connection_string)
        return self._engine
    
    def test_connection(self) -> bool:
        """Test the database connection."""
        if not self.engine:
            return False
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
    
    def fetch_items(
        self,
        plant_id: Optional[int] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        min_risk: Optional[RiskLevel] = None,
    ) -> List[AssetHealthItem]:
        """
        Fetch asset health items from the database.
        
        Args:
            plant_id: Filter by plant ID
            year_from: Filter items scheduled from this year
            year_to: Filter items scheduled up to this year
            min_risk: Minimum risk level to include
        
        Returns:
            List of AssetHealthItem objects
        """
        if not self.engine:
            raise ValueError("No connection string configured")
        
        # Build query - adjust table/column names to match actual schema
        query = """
            SELECT 
                id,
                plant_id,
                plant_name,
                equipment_name,
                description,
                repair_year,
                risk_level,
                estimated_cost,
                created_date
            FROM asset_health_items
            WHERE 1=1
        """
        params = {}
        
        if plant_id:
            query += " AND plant_id = :plant_id"
            params["plant_id"] = plant_id
        
        if year_from:
            query += " AND repair_year >= :year_from"
            params["year_from"] = year_from
        
        if year_to:
            query += " AND repair_year <= :year_to"
            params["year_to"] = year_to
        
        if min_risk:
            risk_order = {"high": 1, "medium": 2, "low": 3}
            query += " AND risk_order <= :risk_order"
            params["risk_order"] = risk_order.get(min_risk.value, 3)
        
        query += " ORDER BY repair_year, risk_level"
        
        items = []
        with self.engine.connect() as conn:
            result = conn.execute(text(query), params)
            for row in result:
                items.append(AssetHealthItem(
                    id=row.id,
                    plant_id=row.plant_id,
                    plant_name=row.plant_name,
                    equipment_name=row.equipment_name,
                    description=row.description,
                    year=row.repair_year,
                    risk=RiskLevel(row.risk_level.lower()),
                    estimated_cost=Decimal(str(row.estimated_cost)),
                    created_date=row.created_date,
                ))
        
        return items


def import_asset_health_to_forecast(
    connector: AssetHealthConnector,
    scenario_id: int,
    year_from: int,
    year_to: int,
    apply_risk_weighting: bool = True,
    db: Session = None,
) -> dict:
    """
    Import asset health items into forecast as O&M costs.
    
    Args:
        connector: AssetHealthConnector instance
        scenario_id: Target scenario to update
        year_from: Start year
        year_to: End year
        apply_risk_weighting: If True, multiply costs by risk probability
        db: Database session
    
    Returns:
        Dict with import statistics
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    try:
        # Get the Asset Health category
        asset_health_category = (
            db.query(CostCategory)
            .filter(CostCategory.short_name == "Asset Health")
            .first()
        )
        
        if not asset_health_category:
            # Create if doesn't exist
            asset_health_category = CostCategory(
                name="Asset Health Items",
                short_name="Asset Health",
                section=CostSection.OPERATING,
                sort_order=5,
                is_active=True,
            )
            db.add(asset_health_category)
            db.commit()
        
        # Get plant mappings
        plants = {p.name: p for p in db.query(Plant).all()}
        plants.update({p.short_name: p for p in db.query(Plant).all()})
        
        # Get period mappings
        periods = {}
        for p in db.query(Period).filter(Period.year >= year_from, Period.year <= year_to).all():
            if p.granularity == Granularity.ANNUAL:
                periods[(p.year, None)] = p
            else:
                periods[(p.year, p.month)] = p
        
        # Fetch items
        items = connector.fetch_items(year_from=year_from, year_to=year_to)
        
        stats = {
            "items_fetched": len(items),
            "forecasts_created": 0,
            "forecasts_updated": 0,
            "total_cost": Decimal("0"),
            "risk_adjusted_cost": Decimal("0"),
        }
        
        # Aggregate by plant/year
        aggregated = {}
        for item in items:
            plant = plants.get(item.plant_name)
            if not plant:
                continue
            
            key = (plant.id, item.year)
            if key not in aggregated:
                aggregated[key] = Decimal("0")
            
            cost = item.estimated_cost
            if apply_risk_weighting:
                cost = cost * Decimal(str(item.risk_factor))
            
            aggregated[key] += cost
            stats["total_cost"] += item.estimated_cost
            stats["risk_adjusted_cost"] += cost
        
        # Create/update forecasts
        for (plant_id, year), total_cost in aggregated.items():
            period = periods.get((year, None))  # Annual period
            if not period:
                continue
            
            existing = (
                db.query(Forecast)
                .filter(
                    Forecast.scenario_id == scenario_id,
                    Forecast.plant_id == plant_id,
                    Forecast.category_id == asset_health_category.id,
                    Forecast.period_id == period.id,
                )
                .first()
            )
            
            if existing:
                existing.cost_dollars = total_cost
                existing.notes = f"Auto-imported from Asset Health ({len(items)} items)"
                stats["forecasts_updated"] += 1
            else:
                forecast = Forecast(
                    scenario_id=scenario_id,
                    plant_id=plant_id,
                    category_id=asset_health_category.id,
                    period_id=period.id,
                    cost_dollars=total_cost,
                    notes=f"Auto-imported from Asset Health",
                )
                db.add(forecast)
                stats["forecasts_created"] += 1
        
        db.commit()
        return stats
        
    finally:
        if close_db:
            db.close()


def get_plant_budget_conflicts(
    connector: AssetHealthConnector,
    scenario_id: int,
    year: int,
    db: Session = None,
) -> List[dict]:
    """
    Find potential double-budgeting conflicts.
    
    Compares Asset Health items with existing plant-submitted budgets
    to identify items that may have been budgeted twice.
    
    Returns list of potential conflicts for review.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    try:
        conflicts = []
        
        # Get existing O&M forecasts (excluding Asset Health category)
        asset_health_cat = (
            db.query(CostCategory)
            .filter(CostCategory.short_name == "Asset Health")
            .first()
        )
        
        existing_om = (
            db.query(Forecast)
            .join(CostCategory)
            .join(Period)
            .filter(
                Forecast.scenario_id == scenario_id,
                CostCategory.section == CostSection.OPERATING,
                Period.year == year,
            )
        )
        
        if asset_health_cat:
            existing_om = existing_om.filter(
                Forecast.category_id != asset_health_cat.id
            )
        
        existing_om = existing_om.all()
        
        # Get Asset Health items for the year
        ah_items = connector.fetch_items(year_from=year, year_to=year)
        
        # Simple keyword matching for potential conflicts
        keywords_to_check = ["boiler", "turbine", "generator", "transformer", "pump", "motor"]
        
        for item in ah_items:
            item_lower = item.description.lower()
            for keyword in keywords_to_check:
                if keyword in item_lower:
                    for forecast in existing_om:
                        if keyword in forecast.category.name.lower():
                            conflicts.append({
                                "asset_health_item": {
                                    "id": item.id,
                                    "description": item.description,
                                    "cost": float(item.estimated_cost),
                                    "plant": item.plant_name,
                                },
                                "existing_forecast": {
                                    "category": forecast.category.name,
                                    "cost": float(forecast.cost_dollars) if forecast.cost_dollars else 0,
                                    "plant": forecast.plant.name if forecast.plant else "Combined",
                                },
                                "potential_duplicate": True,
                            })
        
        return conflicts
        
    finally:
        if close_db:
            db.close()


# CLI usage
if __name__ == "__main__":
    import sys
    import os
    
    # Get connection string from environment
    ah_conn_string = os.getenv("ASSET_HEALTH_DB_URL")
    
    if not ah_conn_string:
        print("Error: ASSET_HEALTH_DB_URL environment variable not set")
        print("Expected format: mssql+pyodbc://user:pass@server/database?driver=...")
        sys.exit(1)
    
    connector = AssetHealthConnector(ah_conn_string)
    
    if connector.test_connection():
        print("Connected to Asset Health database")
        items = connector.fetch_items(year_from=2025, year_to=2030)
        print(f"Found {len(items)} asset health items")
        for item in items[:10]:
            print(f"  - {item.year}: {item.description} (${item.estimated_cost:,.0f})")
    else:
        print("Failed to connect to Asset Health database")

