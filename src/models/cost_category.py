"""Cost category model - hierarchical cost structure."""

from enum import Enum
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from src.database import Base


class CostSection(str, Enum):
    """Top-level cost sections."""
    FUEL = "fuel"
    OPERATING = "operating"
    NON_OPERATING = "non_operating"
    CAPITAL = "capital"


class CostCategory(Base):
    """Hierarchical cost category for organizing expenses."""
    
    __tablename__ = "cost_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    short_name = Column(String(50), nullable=False)
    section = Column(SQLEnum(CostSection), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("cost_categories.id"), nullable=True)
    sort_order = Column(Integer, default=0)
    is_subtotal = Column(Boolean, default=False)  # True for subtotal rows
    is_active = Column(Boolean, default=True)
    
    # Self-referential relationship for hierarchy
    parent = relationship("CostCategory", remote_side=[id], back_populates="children")
    children = relationship("CostCategory", back_populates="parent")
    
    # Forecasts using this category
    forecasts = relationship("Forecast", back_populates="category")
    
    def __repr__(self):
        return f"<CostCategory(name='{self.name}', section={self.section.value})>"
    
    @property
    def full_path(self) -> str:
        """Full hierarchical path (e.g., 'Fuel > Coal Procurement')."""
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name


# Import Boolean here to avoid circular import issues
from sqlalchemy import Boolean

