"""Use Factor Input model for database-driven use factor management.

Stores monthly use factor inputs per plant, matching the Excel 'Use Factor Input' sheet:
- Base use factor (for normal operations, all units)
- Ozone use factor for non-SCR units (Unit 6 during May-Sep)
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, Numeric, ForeignKey, DateTime, 
    UniqueConstraint, Index, String, Text
)
from sqlalchemy.orm import relationship

from src.database import Base


class UseFactorInput(Base):
    """Monthly use factor inputs for a plant.
    
    Matches Excel 'Use Factor Input' sheet:
    - Row 3/4: Clifty/Kyger "without NOx Allowance" (base use factor)
    - Row 9/10: "with NOx Allowance" (ozone season for non-SCR units)
    """
    
    __tablename__ = "use_factor_inputs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Plant and period
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False)  # 1-12
    
    # Use factors (0-1 range, stored as decimal)
    # Base use factor - applied to all units during normal operations
    use_factor_base = Column(Numeric(5, 4), nullable=False, default=0.85)
    
    # Ozone season use factor for non-SCR units (like Clifty Unit 6)
    # Applied during May-Sep for units without SCR
    use_factor_ozone_non_scr = Column(Numeric(5, 4), nullable=False, default=0.0)
    
    # Optional notes
    notes = Column(Text, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(100), nullable=True)
    
    # Relationships
    plant = relationship("Plant")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('plant_id', 'year', 'month', name='uq_use_factor_plant_year_month'),
        Index('ix_use_factor_plant_year', 'plant_id', 'year'),
    )
    
    def __repr__(self):
        return (
            f"<UseFactorInput(plant_id={self.plant_id}, {self.year}-{self.month:02d}, "
            f"base={self.use_factor_base}, ozone={self.use_factor_ozone_non_scr})>"
        )
    
    @property
    def period_yyyymm(self) -> str:
        """Return period as YYYYMM string."""
        return f"{self.year}{self.month:02d}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "plant_id": self.plant_id,
            "year": self.year,
            "month": self.month,
            "use_factor_base": float(self.use_factor_base) if self.use_factor_base else 0.85,
            "use_factor_ozone_non_scr": float(self.use_factor_ozone_non_scr) if self.use_factor_ozone_non_scr else 0.0,
            "notes": self.notes,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def get_use_factors_for_year(db, plant_id: int, year: int) -> dict:
    """Get all use factors for a plant/year as a dictionary.
    
    Returns:
        Dict with month (1-12) as key, dict with 'base' and 'ozone_non_scr' as value.
        Missing months will have default values.
    """
    from decimal import Decimal
    
    inputs = db.query(UseFactorInput).filter(
        UseFactorInput.plant_id == plant_id,
        UseFactorInput.year == year
    ).all()
    
    # Build result with defaults
    result = {}
    for month in range(1, 13):
        result[month] = {
            "base": Decimal("0.85"),
            "ozone_non_scr": Decimal("0.0"),
        }
    
    # Override with database values
    for inp in inputs:
        result[inp.month] = {
            "base": inp.use_factor_base or Decimal("0.85"),
            "ozone_non_scr": inp.use_factor_ozone_non_scr or Decimal("0.0"),
        }
    
    return result


def build_use_factor_params_from_db(db, plant_id: int, year: int):
    """Build UseFactorParams from database values for a plant/year.
    
    This creates a UseFactorParams object that can be used with the
    generation calculation engine.
    
    Args:
        db: Database session
        plant_id: Plant ID (1=Kyger, 2=Clifty)
        year: Year to load factors for
        
    Returns:
        UseFactorParams with monthly values loaded from database
    """
    from decimal import Decimal
    from src.engine.generation import UseFactorParams
    
    # Get use factors from database
    db_factors = get_use_factors_for_year(db, plant_id, year)
    
    # Calculate average base factor and average ozone factor
    base_factors = [db_factors[m]["base"] for m in range(1, 13)]
    ozone_factors = [db_factors[m]["ozone_non_scr"] for m in range(1, 13)]
    
    avg_base = sum(base_factors) / Decimal("12")
    # For ozone, only average the ozone season months (5-9)
    ozone_season_factors = [ozone_factors[m-1] for m in range(5, 10)]
    avg_ozone = sum(ozone_season_factors) / Decimal("5") if ozone_season_factors else Decimal("0")
    
    # Build monthly overrides for any months that differ from the average
    monthly_unit_overrides = {}
    
    # For each month, if the base factor differs significantly from average,
    # we need to handle this per-unit. For simplicity, we'll use a monthly
    # pattern approach where each month can have its own factor.
    # The UseFactorParams.get_use_factor() method handles the logic.
    
    params = UseFactorParams(
        base_use_factor=avg_base,
        ozone_use_factor_non_scr=avg_ozone,
        monthly_unit_overrides={},
    )
    
    # Add monthly variations as overrides
    # For each month, if the base differs from avg, add override for all SCR units
    # For ozone months, if ozone_non_scr differs, add override for non-SCR units
    for month in range(1, 13):
        month_base = db_factors[month]["base"]
        month_ozone = db_factors[month]["ozone_non_scr"]
        
        # We can't easily add per-unit overrides without knowing the unit structure
        # So we'll store the monthly factors directly in the params
        # The fuel_model.py calculate_fuel_costs will need to extract these
        pass
    
    # Store the raw monthly data for direct access
    params._monthly_base_factors = {m: db_factors[m]["base"] for m in range(1, 13)}
    params._monthly_ozone_factors = {m: db_factors[m]["ozone_non_scr"] for m in range(1, 13)}
    
    return params


def upsert_use_factor(
    db,
    plant_id: int,
    year: int,
    month: int,
    use_factor_base: float,
    use_factor_ozone_non_scr: float = 0.0,
    notes: str = None,
    updated_by: str = None,
) -> UseFactorInput:
    """Insert or update a use factor input.
    
    Returns:
        The created or updated UseFactorInput record.
    """
    from decimal import Decimal
    
    existing = db.query(UseFactorInput).filter(
        UseFactorInput.plant_id == plant_id,
        UseFactorInput.year == year,
        UseFactorInput.month == month,
    ).first()
    
    if existing:
        existing.use_factor_base = Decimal(str(use_factor_base))
        existing.use_factor_ozone_non_scr = Decimal(str(use_factor_ozone_non_scr))
        if notes is not None:
            existing.notes = notes
        existing.updated_by = updated_by
        existing.updated_at = datetime.utcnow()
        db.commit()
        return existing
    else:
        new_input = UseFactorInput(
            plant_id=plant_id,
            year=year,
            month=month,
            use_factor_base=Decimal(str(use_factor_base)),
            use_factor_ozone_non_scr=Decimal(str(use_factor_ozone_non_scr)),
            notes=notes,
            updated_by=updated_by,
        )
        db.add(new_input)
        db.commit()
        db.refresh(new_input)
        return new_input

