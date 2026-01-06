"""Plant model - represents Kyger Creek and Clifty Creek power plants."""

from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship

from src.database import Base


class Plant(Base):
    """Power plant entity (Kyger Creek or Clifty Creek)."""
    
    __tablename__ = "plants"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    short_name = Column(String(20), nullable=False)
    capacity_mw = Column(Integer, nullable=False)  # Total capacity in MW
    unit_count = Column(Integer, nullable=False)   # Number of generating units
    unit_capacity_mw = Column(Integer, nullable=False)  # Capacity per unit
    is_active = Column(Boolean, default=True)
    
    # Relationships
    forecasts = relationship("Forecast", back_populates="plant")
    
    def __repr__(self):
        return f"<Plant(name='{self.name}', capacity={self.capacity_mw}MW)>"
    
    @property
    def max_annual_generation_mwh(self) -> float:
        """Calculate maximum possible annual generation (8760 hours)."""
        return self.capacity_mw * 8760
    
    def generation_at_capacity_factor(self, capacity_factor: float) -> float:
        """Calculate annual generation at given capacity factor."""
        return self.max_annual_generation_mwh * capacity_factor

