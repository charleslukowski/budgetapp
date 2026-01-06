"""Period model - time dimension for forecasts."""

from enum import Enum
from sqlalchemy import Column, Integer, String, Enum as SQLEnum
from sqlalchemy.orm import relationship

from src.database import Base


class Granularity(str, Enum):
    """Time granularity levels."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class Period(Base):
    """Time period entity for forecasting."""
    
    __tablename__ = "periods"
    
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=True)  # 1-12 for monthly, NULL for annual
    quarter = Column(Integer, nullable=True)  # 1-4 for quarterly, NULL otherwise
    granularity = Column(SQLEnum(Granularity), nullable=False)
    
    # Relationships
    forecasts = relationship("Forecast", back_populates="period")
    
    def __repr__(self):
        if self.granularity == Granularity.MONTHLY:
            return f"<Period({self.year}-{self.month:02d})>"
        elif self.granularity == Granularity.QUARTERLY:
            return f"<Period({self.year} Q{self.quarter})>"
        return f"<Period({self.year})>"
    
    @property
    def display_name(self) -> str:
        """Human-readable period name."""
        if self.granularity == Granularity.MONTHLY:
            from calendar import month_abbr
            return f"{month_abbr[self.month]} {self.year}"
        elif self.granularity == Granularity.QUARTERLY:
            return f"Q{self.quarter} {self.year}"
        return str(self.year)
    
    @property
    def hours_in_period(self) -> int:
        """Number of hours in this period (for $/MWhr calculations)."""
        if self.granularity == Granularity.ANNUAL:
            return 8760
        elif self.granularity == Granularity.QUARTERLY:
            return 8760 // 4  # Approximate
        else:
            # Monthly - varies by month
            from calendar import monthrange
            days = monthrange(self.year, self.month)[1]
            return days * 24
    
    @property
    def sort_key(self) -> tuple:
        """Key for sorting periods chronologically."""
        month = self.month or (self.quarter * 3 if self.quarter else 1)
        return (self.year, month)

