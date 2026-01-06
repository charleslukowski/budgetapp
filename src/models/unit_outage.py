"""Unit Outage Input model for database-driven outage tracking.

Stores monthly outage days per unit per plant:
- Planned outage days
- Forced outage days (estimate)
- Used to calculate EFOR and Availability
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, Numeric, ForeignKey, DateTime, 
    UniqueConstraint, Index, String, Text, Boolean
)
from sqlalchemy.orm import relationship, Session
from typing import Dict, List, Optional

from src.database import Base


class UnitOutageInput(Base):
    """Monthly outage inputs for a specific unit.
    
    Stores planned and forced outage days by month for each unit.
    Used to calculate:
    - Unit availability factor
    - EFOR (Equivalent Forced Outage Rate)
    - Overall plant availability
    """
    
    __tablename__ = "unit_outage_inputs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Plant, unit, and period
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False, index=True)
    unit_number = Column(Integer, nullable=False)  # 1-5 for Kyger, 1-6 for Clifty
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False)  # 1-12
    
    # Outage days
    # Planned outages - scheduled maintenance, overhauls, etc.
    planned_outage_days = Column(Numeric(5, 2), nullable=False, default=0)
    
    # Forced outages - unplanned outages (forecasted/estimated for future periods)
    forced_outage_days = Column(Numeric(5, 2), nullable=False, default=0)
    
    # Reserve shutdown days - unit available but not dispatched for economic reasons
    reserve_shutdown_days = Column(Numeric(5, 2), nullable=False, default=0)
    
    # Outage type details (for planned outages)
    outage_type = Column(String(50), nullable=True)  # "MAJOR", "MINOR", "INSPECTION", "BOILER", "TURBINE"
    outage_description = Column(Text, nullable=True)  # Description of planned work
    
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
        UniqueConstraint(
            'plant_id', 'unit_number', 'year', 'month',
            name='uq_unit_outage_plant_unit_period'
        ),
        Index('ix_unit_outage_plant_year', 'plant_id', 'year'),
        Index('ix_unit_outage_lookup', 'plant_id', 'unit_number', 'year', 'month'),
    )
    
    def __repr__(self):
        return (
            f"<UnitOutageInput(plant_id={self.plant_id}, unit={self.unit_number}, "
            f"year={self.year}, month={self.month}, "
            f"planned={self.planned_outage_days}, forced={self.forced_outage_days})>"
        )
    
    @property
    def total_outage_days(self) -> Decimal:
        """Total unavailable days (planned + forced)."""
        return (self.planned_outage_days or Decimal("0")) + (self.forced_outage_days or Decimal("0"))
    
    @property
    def total_unavailable_days(self) -> Decimal:
        """Total days unit is not generating (outage + reserve shutdown)."""
        return self.total_outage_days + (self.reserve_shutdown_days or Decimal("0"))


# =============================================================================
# EFOR / Availability Calculation Functions
# =============================================================================

def get_hours_in_month(year: int, month: int) -> int:
    """Get total hours in a month."""
    from calendar import monthrange
    days = monthrange(year, month)[1]
    return days * 24


def calculate_unit_availability(
    outage: UnitOutageInput,
    year: int,
    month: int
) -> Dict[str, Decimal]:
    """Calculate availability metrics for a unit-month.
    
    Returns:
        Dict with availability metrics:
        - availability_factor: (1 - outage_hours / period_hours)
        - efor: Equivalent Forced Outage Rate
        - planned_outage_rate: Planned outage as % of period
        - total_unavailable_pct: Total unavailable as % of period
    """
    from calendar import monthrange
    
    days_in_month = monthrange(year, month)[1]
    hours_in_month = Decimal(str(days_in_month * 24))
    
    # Handle None values in outage fields
    planned_days = Decimal(str(outage.planned_outage_days or 0)) if outage else Decimal("0")
    forced_days = Decimal(str(outage.forced_outage_days or 0)) if outage else Decimal("0")
    reserve_days = Decimal(str(outage.reserve_shutdown_days or 0)) if outage else Decimal("0")
    
    # Convert days to hours
    planned_hours = planned_days * Decimal("24")
    forced_hours = forced_days * Decimal("24")
    reserve_hours = reserve_days * Decimal("24")
    
    # Available hours = total - planned - forced
    available_hours = max(Decimal("0"), hours_in_month - planned_hours - forced_hours)
    
    # Availability factor (excluding forced and planned)
    availability_factor = available_hours / hours_in_month if hours_in_month > 0 else Decimal("1")
    
    # EFOR = Forced Outage Hours / (Service Hours + Forced Outage Hours)
    # Service Hours = Available Hours - Reserve Shutdown
    service_hours = max(Decimal("0"), available_hours - reserve_hours)
    efor_denominator = service_hours + forced_hours
    efor = forced_hours / efor_denominator if efor_denominator > 0 else Decimal("0")
    
    # Planned outage rate
    planned_outage_rate = planned_hours / hours_in_month if hours_in_month > 0 else Decimal("0")
    
    # Total unavailable percentage
    total_unavailable_hours = planned_hours + forced_hours + reserve_hours
    total_unavailable_pct = total_unavailable_hours / hours_in_month if hours_in_month > 0 else Decimal("0")
    
    return {
        "availability_factor": availability_factor,
        "efor": efor,
        "planned_outage_rate": planned_outage_rate,
        "total_unavailable_pct": total_unavailable_pct,
        "available_hours": available_hours,
        "service_hours": service_hours,
        "period_hours": hours_in_month,
    }


def calculate_plant_availability(
    outages: List[UnitOutageInput],
    year: int,
    month: int,
    unit_capacities: Dict[int, Decimal]
) -> Dict[str, Decimal]:
    """Calculate weighted average availability for a plant.
    
    Args:
        outages: List of unit outage records for the period
        year: Year
        month: Month
        unit_capacities: Dict of unit_number -> capacity_mw
        
    Returns:
        Dict with plant-level availability metrics (capacity-weighted)
    """
    total_capacity = sum(unit_capacities.values())
    if total_capacity == 0:
        return {
            "weighted_availability": Decimal("1"),
            "weighted_efor": Decimal("0"),
            "total_outage_days": Decimal("0"),
        }
    
    # Build dict of outages by unit
    outage_by_unit = {o.unit_number: o for o in outages}
    
    weighted_availability = Decimal("0")
    weighted_efor = Decimal("0")
    total_outage_days = Decimal("0")
    
    for unit_num, capacity in unit_capacities.items():
        weight = capacity / total_capacity
        outage = outage_by_unit.get(unit_num)
        
        if outage:
            metrics = calculate_unit_availability(outage, year, month)
            weighted_availability += metrics["availability_factor"] * weight
            weighted_efor += metrics["efor"] * weight
            total_outage_days += outage.total_outage_days
        else:
            # No outage record = fully available
            weighted_availability += Decimal("1") * weight
    
    return {
        "weighted_availability": weighted_availability,
        "weighted_efor": weighted_efor,
        "total_outage_days": total_outage_days,
    }


# =============================================================================
# Database Query Functions
# =============================================================================

def get_unit_outages_for_period(
    db: Session,
    plant_id: int,
    year: int,
    month: int
) -> List[UnitOutageInput]:
    """Get all unit outages for a plant/month."""
    return db.query(UnitOutageInput).filter(
        UnitOutageInput.plant_id == plant_id,
        UnitOutageInput.year == year,
        UnitOutageInput.month == month
    ).order_by(UnitOutageInput.unit_number).all()


def get_unit_outages_for_year(
    db: Session,
    plant_id: int,
    year: int,
    unit_number: Optional[int] = None
) -> List[UnitOutageInput]:
    """Get all unit outages for a plant/year, optionally filtered by unit."""
    query = db.query(UnitOutageInput).filter(
        UnitOutageInput.plant_id == plant_id,
        UnitOutageInput.year == year
    )
    if unit_number is not None:
        query = query.filter(UnitOutageInput.unit_number == unit_number)
    return query.order_by(UnitOutageInput.unit_number, UnitOutageInput.month).all()


def get_unit_outage(
    db: Session,
    plant_id: int,
    unit_number: int,
    year: int,
    month: int
) -> Optional[UnitOutageInput]:
    """Get outage record for a specific unit/month."""
    return db.query(UnitOutageInput).filter(
        UnitOutageInput.plant_id == plant_id,
        UnitOutageInput.unit_number == unit_number,
        UnitOutageInput.year == year,
        UnitOutageInput.month == month
    ).first()


def upsert_unit_outage(
    db: Session,
    plant_id: int,
    unit_number: int,
    year: int,
    month: int,
    planned_outage_days: Decimal = Decimal("0"),
    forced_outage_days: Decimal = Decimal("0"),
    reserve_shutdown_days: Decimal = Decimal("0"),
    outage_type: Optional[str] = None,
    outage_description: Optional[str] = None,
    notes: Optional[str] = None,
    updated_by: Optional[str] = None,
) -> UnitOutageInput:
    """Create or update a unit outage record."""
    existing = get_unit_outage(db, plant_id, unit_number, year, month)
    
    if existing:
        existing.planned_outage_days = planned_outage_days
        existing.forced_outage_days = forced_outage_days
        existing.reserve_shutdown_days = reserve_shutdown_days
        existing.outage_type = outage_type
        existing.outage_description = outage_description
        existing.notes = notes
        existing.updated_at = datetime.utcnow()
        existing.updated_by = updated_by
        result = existing
    else:
        result = UnitOutageInput(
            plant_id=plant_id,
            unit_number=unit_number,
            year=year,
            month=month,
            planned_outage_days=planned_outage_days,
            forced_outage_days=forced_outage_days,
            reserve_shutdown_days=reserve_shutdown_days,
            outage_type=outage_type,
            outage_description=outage_description,
            notes=notes,
            updated_by=updated_by,
        )
        db.add(result)
    
    db.commit()
    db.refresh(result)
    return result


def build_unit_availability_from_db(
    db: Session,
    plant_id: int,
    year: int,
    month: int,
    num_units: int = 5
) -> Dict[int, Decimal]:
    """Build unit availability factors from database outage records.
    
    Returns:
        Dict of unit_number -> availability_factor (0-1)
    """
    outages = get_unit_outages_for_period(db, plant_id, year, month)
    outage_by_unit = {o.unit_number: o for o in outages}
    
    availability = {}
    for unit_num in range(1, num_units + 1):
        outage = outage_by_unit.get(unit_num)
        if outage:
            metrics = calculate_unit_availability(outage, year, month)
            availability[unit_num] = metrics["availability_factor"]
        else:
            availability[unit_num] = Decimal("1")  # No outage = fully available
    
    return availability


def get_annual_outage_summary(
    db: Session,
    plant_id: int,
    year: int
) -> Dict[str, any]:
    """Get annual outage summary for a plant.
    
    Returns summary statistics for display in UI.
    """
    outages = get_unit_outages_for_year(db, plant_id, year)
    
    # Aggregate by unit
    unit_totals = {}
    for outage in outages:
        if outage.unit_number not in unit_totals:
            unit_totals[outage.unit_number] = {
                "planned_days": Decimal("0"),
                "forced_days": Decimal("0"),
                "reserve_days": Decimal("0"),
            }
        unit_totals[outage.unit_number]["planned_days"] += outage.planned_outage_days or Decimal("0")
        unit_totals[outage.unit_number]["forced_days"] += outage.forced_outage_days or Decimal("0")
        unit_totals[outage.unit_number]["reserve_days"] += outage.reserve_shutdown_days or Decimal("0")
    
    # Plant totals
    total_planned = sum(u["planned_days"] for u in unit_totals.values())
    total_forced = sum(u["forced_days"] for u in unit_totals.values())
    total_reserve = sum(u["reserve_days"] for u in unit_totals.values())
    
    return {
        "plant_id": plant_id,
        "year": year,
        "unit_totals": unit_totals,
        "total_planned_days": total_planned,
        "total_forced_days": total_forced,
        "total_reserve_days": total_reserve,
        "total_outage_days": total_planned + total_forced,
    }

