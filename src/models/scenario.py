"""Scenario model - different forecast versions."""

from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum as SQLEnum, Text, ForeignKey
from sqlalchemy.orm import relationship

from src.database import Base


class ScenarioType(str, Enum):
    """Types of forecast scenarios."""
    BUDGET = "budget"
    INTERNAL_FORECAST = "internal_forecast"
    EXTERNAL_FORECAST = "external_forecast"


class ScenarioStatus(str, Enum):
    """Scenario workflow status."""
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Scenario(Base):
    """Forecast scenario/version entity."""
    
    __tablename__ = "scenarios"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    scenario_type = Column(SQLEnum(ScenarioType), nullable=False, index=True)
    status = Column(SQLEnum(ScenarioStatus), default=ScenarioStatus.DRAFT)
    
    # Versioning
    version = Column(Integer, default=1)
    parent_scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100), nullable=True)
    
    # Flags
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)  # Prevent further edits
    
    # Relationships
    forecasts = relationship("Forecast", back_populates="scenario")
    parent = relationship("Scenario", remote_side=[id])
    
    def __repr__(self):
        return f"<Scenario(name='{self.name}', type={self.scenario_type.value})>"
    
    @property
    def display_name(self) -> str:
        """Display name with version."""
        return f"{self.name} (v{self.version})"

