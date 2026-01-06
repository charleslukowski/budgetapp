"""Database models for driver-based forecasting.

Stores driver definitions and values persistently in the database.
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Numeric, ForeignKey, DateTime, 
    Text, Index, Boolean, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
import enum

from src.database import Base


class DriverTypeEnum(enum.Enum):
    """Types of drivers in the forecasting model."""
    INPUT = "input"
    PRICE_INDEX = "price_index"
    RATE = "rate"
    VOLUME = "volume"
    PERCENTAGE = "percentage"
    CALCULATED = "calculated"
    TOGGLE = "toggle"


class DriverCategoryEnum(enum.Enum):
    """Categories for organizing drivers."""
    COAL_PRICE = "coal_price"
    TRANSPORTATION = "transportation"
    HEAT_RATE = "heat_rate"
    GENERATION = "generation"
    INVENTORY = "inventory"
    ESCALATION = "escalation"
    CONSUMABLES = "consumables"
    BYPRODUCTS = "byproducts"
    OTHER = "other"


class DriverDefinition(Base):
    """Persistent driver definition.
    
    Stores the metadata about each driver - its name, type, unit,
    category, default value, dependencies, and display configuration.
    """
    
    __tablename__ = "driver_definitions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Identification
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    
    # Classification
    driver_type = Column(
        SQLEnum(DriverTypeEnum, name="driver_type_enum"),
        nullable=False,
        default=DriverTypeEnum.INPUT
    )
    category = Column(
        SQLEnum(DriverCategoryEnum, name="driver_category_enum"),
        nullable=False,
        default=DriverCategoryEnum.OTHER
    )
    
    # Value configuration
    unit = Column(String(50), nullable=False, default="")
    default_value = Column(Numeric(18, 6), default=0)
    min_value = Column(Numeric(18, 6), nullable=True)
    max_value = Column(Numeric(18, 6), nullable=True)
    step = Column(Numeric(18, 6), default=1)
    
    # For calculated drivers
    depends_on = Column(Text, nullable=True)  # JSON array of driver names
    calculation_formula = Column(Text, nullable=True)  # Description or code reference
    
    # Plant-specific flag
    is_plant_specific = Column(Boolean, default=False)
    
    # Display configuration
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    values = relationship("DriverValue", back_populates="driver", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<DriverDefinition(name='{self.name}', type={self.driver_type.value})>"
    
    def get_dependencies(self) -> list:
        """Parse and return the list of dependency driver names."""
        if not self.depends_on:
            return []
        import json
        try:
            return json.loads(self.depends_on)
        except (json.JSONDecodeError, TypeError):
            return []
    
    def set_dependencies(self, deps: list) -> None:
        """Set the list of dependency driver names."""
        import json
        self.depends_on = json.dumps(deps) if deps else None


class DriverValue(Base):
    """Stores a driver value for a specific scenario/period/plant combination.
    
    Values can be:
    - Monthly (period_yyyymm like '202501')
    - Annual (period_yyyymm like '2025' - just the year)
    - Plant-specific or system-wide (plant_id = NULL)
    """
    
    __tablename__ = "driver_values"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False, index=True)
    driver_id = Column(Integer, ForeignKey("driver_definitions.id"), nullable=False, index=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=True, index=True)  # NULL = system-wide
    
    # Period (YYYYMM for monthly, YYYY for annual)
    period_yyyymm = Column(String(6), nullable=False, index=True)
    
    # The value
    value = Column(Numeric(18, 6), nullable=False)
    
    # Notes/comments
    notes = Column(Text, nullable=True)
    
    # Audit
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(100), nullable=True)
    
    # Relationships
    scenario = relationship("Scenario")
    driver = relationship("DriverDefinition", back_populates="values")
    plant = relationship("Plant")
    
    # Composite indexes for common queries
    __table_args__ = (
        Index('ix_driver_value_lookup', 'scenario_id', 'driver_id', 'period_yyyymm'),
        Index('ix_driver_value_full', 'scenario_id', 'driver_id', 'plant_id', 'period_yyyymm'),
        Index('ix_driver_value_scenario_period', 'scenario_id', 'period_yyyymm'),
    )
    
    def __repr__(self):
        return f"<DriverValue(driver_id={self.driver_id}, period={self.period_yyyymm}, value={self.value})>"
    
    @property
    def year(self) -> int:
        """Extract year from period."""
        return int(self.period_yyyymm[:4])
    
    @property
    def month(self) -> int | None:
        """Extract month from period (None if annual)."""
        if len(self.period_yyyymm) == 6:
            return int(self.period_yyyymm[4:6])
        return None
    
    @property
    def is_annual(self) -> bool:
        """Check if this is an annual (not monthly) value."""
        return len(self.period_yyyymm) == 4


class DriverValueHistory(Base):
    """Audit trail for driver value changes.
    
    Tracks who changed what value, when, and what the previous value was.
    """
    
    __tablename__ = "driver_value_history"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Reference to the driver value (may be deleted)
    driver_value_id = Column(Integer, nullable=True)  # Not FK to allow deletion
    scenario_id = Column(Integer, nullable=False)
    driver_id = Column(Integer, nullable=False)
    plant_id = Column(Integer, nullable=True)
    period_yyyymm = Column(String(6), nullable=False)
    
    # Change details
    old_value = Column(Numeric(18, 6), nullable=True)
    new_value = Column(Numeric(18, 6), nullable=True)
    change_type = Column(String(20), nullable=False)  # 'create', 'update', 'delete'
    
    # Audit
    changed_at = Column(DateTime, default=datetime.utcnow)
    changed_by = Column(String(100), nullable=True)
    
    # Index for querying history
    __table_args__ = (
        Index('ix_driver_history_lookup', 'scenario_id', 'driver_id', 'period_yyyymm'),
    )
    
    def __repr__(self):
        return f"<DriverValueHistory(driver_id={self.driver_id}, change={self.change_type})>"

