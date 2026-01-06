"""Forecast model - the core data entity for projections."""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, Numeric, ForeignKey, DateTime, Text, Index, String
from sqlalchemy.orm import relationship

from src.database import Base


class Forecast(Base):
    """
    Forecast data point - the intersection of:
    - Scenario (which forecast version)
    - Plant (Kyger or Clifty)
    - Cost Category (what type of cost)
    - Period (when)
    """
    
    __tablename__ = "forecasts"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False, index=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=True, index=True)  # NULL for combined/total
    category_id = Column(Integer, ForeignKey("cost_categories.id"), nullable=False, index=True)
    period_id = Column(Integer, ForeignKey("periods.id"), nullable=False, index=True)
    
    # Data values
    generation_mwh = Column(Numeric(18, 4), nullable=True)  # Generation for this period
    cost_dollars = Column(Numeric(18, 2), nullable=True)    # Cost in dollars
    
    # Notes/comments
    notes = Column(Text, nullable=True)
    
    # Audit
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(100), nullable=True)
    
    # Relationships
    scenario = relationship("Scenario", back_populates="forecasts")
    plant = relationship("Plant", back_populates="forecasts")
    category = relationship("CostCategory", back_populates="forecasts")
    period = relationship("Period", back_populates="forecasts")
    
    # Composite indexes for common queries
    __table_args__ = (
        Index('ix_forecast_scenario_period', 'scenario_id', 'period_id'),
        Index('ix_forecast_scenario_plant', 'scenario_id', 'plant_id'),
        Index('ix_forecast_full', 'scenario_id', 'plant_id', 'category_id', 'period_id'),
    )
    
    def __repr__(self):
        return f"<Forecast(scenario={self.scenario_id}, period={self.period_id}, cost=${self.cost_dollars})>"
    
    @property
    def cost_per_mwh(self) -> Decimal | None:
        """Calculate $/MWhr metric."""
        if self.generation_mwh and self.generation_mwh > 0 and self.cost_dollars:
            return Decimal(self.cost_dollars) / Decimal(self.generation_mwh)
        return None
    
    @property
    def cost_per_mwh_formatted(self) -> str:
        """Formatted $/MWhr for display."""
        cpm = self.cost_per_mwh
        if cpm is not None:
            return f"${cpm:.2f}/MWhr"
        return "N/A"
