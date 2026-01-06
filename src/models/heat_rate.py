"""Heat Rate Input model for database-driven heat rate management.

Stores monthly heat rate inputs per plant/unit:
- Baseline heat rate (BTU/kWh at full load)
- Min load heat rate (BTU/kWh at minimum load)
- SUF correction factor
- PRB blend adjustment
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, Numeric, ForeignKey, DateTime, 
    UniqueConstraint, Index, String, Text
)
from sqlalchemy.orm import relationship

from src.database import Base


class HeatRateInput(Base):
    """Monthly heat rate inputs for a plant or unit.
    
    Supports both plant-level and unit-level heat rate configuration.
    When unit_number is NULL, the values apply to the entire plant.
    Unit-level values override plant-level values.
    """
    
    __tablename__ = "heat_rate_inputs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Plant and period
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False, index=True)
    unit_number = Column(Integer, nullable=True)  # NULL = plant-level, 1-6 = unit-level
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False)  # 1-12
    
    # Heat rate values (BTU/kWh)
    # Baseline heat rate at full load
    baseline_heat_rate = Column(Numeric(10, 2), nullable=False, default=9850)
    
    # Heat rate at minimum load (for curve interpolation)
    min_load_heat_rate = Column(Numeric(10, 2), nullable=True)  # NULL = no curve, use baseline
    
    # SUF (Surplus Use Factor) correction - adjustment to heat rate based on use factor
    # Positive = higher heat rate at low use factors, negative = lower
    suf_correction = Column(Numeric(8, 2), nullable=False, default=0)
    
    # PRB blend adjustment - adjustment for PRB coal blend percentage
    # Typically positive (higher heat rate with more PRB)
    prb_blend_adjustment = Column(Numeric(8, 2), nullable=False, default=0)
    
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
        UniqueConstraint('plant_id', 'unit_number', 'year', 'month', 
                        name='uq_heat_rate_plant_unit_year_month'),
        Index('ix_heat_rate_plant_year', 'plant_id', 'year'),
        Index('ix_heat_rate_lookup', 'plant_id', 'unit_number', 'year', 'month'),
    )
    
    def __repr__(self):
        unit_str = f"Unit {self.unit_number}" if self.unit_number else "Plant"
        return (
            f"<HeatRateInput(plant_id={self.plant_id}, {unit_str}, "
            f"{self.year}-{self.month:02d}, baseline={self.baseline_heat_rate})>"
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
            "unit_number": self.unit_number,
            "year": self.year,
            "month": self.month,
            "baseline_heat_rate": float(self.baseline_heat_rate) if self.baseline_heat_rate else 9850,
            "min_load_heat_rate": float(self.min_load_heat_rate) if self.min_load_heat_rate else None,
            "suf_correction": float(self.suf_correction) if self.suf_correction else 0,
            "prb_blend_adjustment": float(self.prb_blend_adjustment) if self.prb_blend_adjustment else 0,
            "notes": self.notes,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def get_heat_rate_for_month(
    db,
    plant_id: int,
    year: int,
    month: int,
    unit_number: int = None,
) -> dict:
    """Get heat rate for a specific month and optionally unit.
    
    Priority:
    1. Unit-specific value (if unit_number provided)
    2. Plant-level value
    3. Default values
    
    Returns:
        Dict with heat rate components.
    """
    from decimal import Decimal
    
    # Default values
    result = {
        "baseline_heat_rate": Decimal("9850"),
        "min_load_heat_rate": None,
        "suf_correction": Decimal("0"),
        "prb_blend_adjustment": Decimal("0"),
        "source": "default",
    }
    
    # Try plant-level first
    plant_input = db.query(HeatRateInput).filter(
        HeatRateInput.plant_id == plant_id,
        HeatRateInput.year == year,
        HeatRateInput.month == month,
        HeatRateInput.unit_number.is_(None),
    ).first()
    
    if plant_input:
        result = {
            "baseline_heat_rate": plant_input.baseline_heat_rate or Decimal("9850"),
            "min_load_heat_rate": plant_input.min_load_heat_rate,
            "suf_correction": plant_input.suf_correction or Decimal("0"),
            "prb_blend_adjustment": plant_input.prb_blend_adjustment or Decimal("0"),
            "source": "plant",
        }
    
    # Override with unit-level if provided and exists
    if unit_number is not None:
        unit_input = db.query(HeatRateInput).filter(
            HeatRateInput.plant_id == plant_id,
            HeatRateInput.year == year,
            HeatRateInput.month == month,
            HeatRateInput.unit_number == unit_number,
        ).first()
        
        if unit_input:
            result = {
                "baseline_heat_rate": unit_input.baseline_heat_rate or Decimal("9850"),
                "min_load_heat_rate": unit_input.min_load_heat_rate,
                "suf_correction": unit_input.suf_correction or Decimal("0"),
                "prb_blend_adjustment": unit_input.prb_blend_adjustment or Decimal("0"),
                "source": f"unit_{unit_number}",
            }
    
    return result


def get_heat_rates_for_year(db, plant_id: int, year: int) -> dict:
    """Get all heat rate inputs for a plant/year.
    
    Returns:
        Dict with month (1-12) as key, containing plant and unit values.
    """
    from decimal import Decimal
    
    inputs = db.query(HeatRateInput).filter(
        HeatRateInput.plant_id == plant_id,
        HeatRateInput.year == year
    ).all()
    
    # Build result structure
    result = {}
    for month in range(1, 13):
        result[month] = {
            "plant": {
                "baseline_heat_rate": Decimal("9850"),
                "min_load_heat_rate": None,
                "suf_correction": Decimal("0"),
                "prb_blend_adjustment": Decimal("0"),
            },
            "units": {},
        }
    
    # Populate with database values
    for inp in inputs:
        hr_data = {
            "baseline_heat_rate": inp.baseline_heat_rate,
            "min_load_heat_rate": inp.min_load_heat_rate,
            "suf_correction": inp.suf_correction,
            "prb_blend_adjustment": inp.prb_blend_adjustment,
        }
        
        if inp.unit_number is None:
            result[inp.month]["plant"] = hr_data
        else:
            result[inp.month]["units"][inp.unit_number] = hr_data
    
    return result


def upsert_heat_rate(
    db,
    plant_id: int,
    year: int,
    month: int,
    baseline_heat_rate: float,
    min_load_heat_rate: float = None,
    suf_correction: float = 0,
    prb_blend_adjustment: float = 0,
    unit_number: int = None,
    notes: str = None,
    updated_by: str = None,
) -> HeatRateInput:
    """Insert or update a heat rate input.
    
    Returns:
        The created or updated HeatRateInput record.
    """
    from decimal import Decimal
    
    existing = db.query(HeatRateInput).filter(
        HeatRateInput.plant_id == plant_id,
        HeatRateInput.year == year,
        HeatRateInput.month == month,
        HeatRateInput.unit_number == unit_number if unit_number else HeatRateInput.unit_number.is_(None),
    ).first()
    
    if existing:
        existing.baseline_heat_rate = Decimal(str(baseline_heat_rate))
        existing.min_load_heat_rate = Decimal(str(min_load_heat_rate)) if min_load_heat_rate else None
        existing.suf_correction = Decimal(str(suf_correction))
        existing.prb_blend_adjustment = Decimal(str(prb_blend_adjustment))
        if notes is not None:
            existing.notes = notes
        existing.updated_by = updated_by
        existing.updated_at = datetime.utcnow()
        db.commit()
        return existing
    else:
        new_input = HeatRateInput(
            plant_id=plant_id,
            unit_number=unit_number,
            year=year,
            month=month,
            baseline_heat_rate=Decimal(str(baseline_heat_rate)),
            min_load_heat_rate=Decimal(str(min_load_heat_rate)) if min_load_heat_rate else None,
            suf_correction=Decimal(str(suf_correction)),
            prb_blend_adjustment=Decimal(str(prb_blend_adjustment)),
            notes=notes,
            updated_by=updated_by,
        )
        db.add(new_input)
        db.commit()
        db.refresh(new_input)
        return new_input

