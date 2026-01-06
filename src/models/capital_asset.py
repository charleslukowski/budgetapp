"""Capital Asset and Depreciation models."""

from datetime import date
from decimal import Decimal
from enum import Enum
from sqlalchemy import Column, Integer, String, Numeric, Date, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship

from src.database import Base


class DepreciationMethod(str, Enum):
    """Depreciation calculation methods."""
    STRAIGHT_LINE = "straight_line"
    DECLINING_BALANCE = "declining_balance"
    UNITS_OF_PRODUCTION = "units_of_production"


class AssetStatus(str, Enum):
    """Asset lifecycle status."""
    ACTIVE = "active"
    FULLY_DEPRECIATED = "fully_depreciated"
    RETIRED = "retired"
    PROPOSED = "proposed"  # Not yet approved/in-service


class CapitalAsset(Base):
    """
    Capital asset with depreciation tracking.
    
    Supports the 2026 transition from cash flow billing to depreciation billing.
    """
    
    __tablename__ = "capital_assets"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Asset identification
    asset_number = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Plant association
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=True)
    
    # Financial details
    original_cost = Column(Numeric(18, 2), nullable=False)
    salvage_value = Column(Numeric(18, 2), default=0)
    useful_life_years = Column(Integer, nullable=False)
    
    # Dates
    in_service_date = Column(Date, nullable=False)
    retirement_date = Column(Date, nullable=True)
    
    # Depreciation settings
    depreciation_method = Column(String(50), default=DepreciationMethod.STRAIGHT_LINE.value)
    
    # Current state
    accumulated_depreciation = Column(Numeric(18, 2), default=0)
    status = Column(String(50), default=AssetStatus.ACTIVE.value)
    
    # Relationships
    plant = relationship("Plant")
    
    def __repr__(self):
        return f"<CapitalAsset(number='{self.asset_number}', name='{self.name}')>"
    
    @property
    def depreciable_base(self) -> Decimal:
        """Calculate the depreciable base (cost - salvage)."""
        return Decimal(str(self.original_cost)) - Decimal(str(self.salvage_value or 0))
    
    @property
    def annual_depreciation(self) -> Decimal:
        """Calculate annual straight-line depreciation."""
        if self.useful_life_years <= 0:
            return Decimal("0")
        return self.depreciable_base / self.useful_life_years
    
    @property
    def monthly_depreciation(self) -> Decimal:
        """Calculate monthly straight-line depreciation."""
        return self.annual_depreciation / 12
    
    @property
    def net_book_value(self) -> Decimal:
        """Calculate current net book value."""
        return Decimal(str(self.original_cost)) - Decimal(str(self.accumulated_depreciation or 0))
    
    @property
    def remaining_life_years(self) -> float:
        """Calculate remaining useful life."""
        if not self.in_service_date:
            return float(self.useful_life_years)
        
        today = date.today()
        years_in_service = (today - self.in_service_date).days / 365.25
        remaining = self.useful_life_years - years_in_service
        return max(0, remaining)
    
    @property
    def is_fully_depreciated(self) -> bool:
        """Check if asset is fully depreciated."""
        return self.net_book_value <= Decimal(str(self.salvage_value or 0))
    
    def calculate_depreciation_for_period(
        self,
        year: int,
        month: int = None,
    ) -> Decimal:
        """
        Calculate depreciation for a specific period.
        
        Args:
            year: The year to calculate for
            month: Optional month (1-12). If None, calculates full year.
        
        Returns:
            Depreciation amount for the period
        """
        # Check if asset is in service during this period
        period_start = date(year, month or 1, 1)
        period_end = date(year, month or 12, 28)  # Approximate month end
        
        if self.in_service_date > period_end:
            return Decimal("0")  # Not yet in service
        
        if self.retirement_date and self.retirement_date < period_start:
            return Decimal("0")  # Already retired
        
        if self.is_fully_depreciated:
            return Decimal("0")
        
        if month:
            # Monthly calculation
            # Prorate for first month if in-service mid-month
            if (self.in_service_date.year == year and 
                self.in_service_date.month == month):
                days_in_month = 30  # Approximate
                days_active = days_in_month - self.in_service_date.day + 1
                return self.monthly_depreciation * Decimal(str(days_active / days_in_month))
            return self.monthly_depreciation
        else:
            # Annual calculation
            if self.in_service_date.year == year:
                # Prorate for first year
                months_active = 12 - self.in_service_date.month + 1
                return self.annual_depreciation * Decimal(str(months_active / 12))
            return self.annual_depreciation


class CapitalProject(Base):
    """
    Proposed capital project with NPV/IRR analysis.
    
    Tracks projects through approval process and converts to
    CapitalAsset upon in-service.
    """
    
    __tablename__ = "capital_projects"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Project identification
    project_number = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Plant association
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=True)
    
    # Financial estimates
    estimated_cost = Column(Numeric(18, 2), nullable=False)
    contingency_percent = Column(Numeric(5, 2), default=10)  # e.g., 10%
    
    # Financial analysis
    npv = Column(Numeric(18, 2), nullable=True)  # Net Present Value
    irr = Column(Numeric(8, 4), nullable=True)    # Internal Rate of Return
    payback_years = Column(Numeric(8, 2), nullable=True)
    
    # Timeline
    proposed_start_date = Column(Date, nullable=True)
    proposed_in_service_date = Column(Date, nullable=True)
    
    # Depreciation projection
    estimated_useful_life = Column(Integer, nullable=True)
    
    # Approval workflow
    status = Column(String(50), default="proposed")  # proposed, approved, in_progress, completed, cancelled
    approved_date = Column(Date, nullable=True)
    approved_by = Column(String(100), nullable=True)
    
    # Link to created asset
    capital_asset_id = Column(Integer, ForeignKey("capital_assets.id"), nullable=True)
    
    # Relationships
    plant = relationship("Plant")
    capital_asset = relationship("CapitalAsset")
    
    def __repr__(self):
        return f"<CapitalProject(number='{self.project_number}', name='{self.name}')>"
    
    @property
    def total_estimated_cost(self) -> Decimal:
        """Calculate total cost including contingency."""
        base = Decimal(str(self.estimated_cost))
        contingency = base * (Decimal(str(self.contingency_percent or 0)) / 100)
        return base + contingency
    
    @property
    def projected_annual_depreciation(self) -> Decimal:
        """Project annual depreciation if approved."""
        if not self.estimated_useful_life or self.estimated_useful_life <= 0:
            return Decimal("0")
        return self.total_estimated_cost / self.estimated_useful_life
    
    def convert_to_asset(
        self,
        actual_cost: Decimal = None,
        in_service_date: date = None,
    ) -> CapitalAsset:
        """
        Convert approved project to a capital asset.
        
        Args:
            actual_cost: Final cost (uses estimate if None)
            in_service_date: Actual in-service date
        
        Returns:
            Created CapitalAsset instance
        """
        asset = CapitalAsset(
            asset_number=f"A-{self.project_number}",
            name=self.name,
            description=self.description,
            plant_id=self.plant_id,
            original_cost=actual_cost or self.total_estimated_cost,
            salvage_value=Decimal("0"),
            useful_life_years=self.estimated_useful_life or 20,
            in_service_date=in_service_date or date.today(),
            depreciation_method=DepreciationMethod.STRAIGHT_LINE.value,
            status=AssetStatus.ACTIVE.value,
        )
        
        self.capital_asset = asset
        self.status = "completed"
        
        return asset

