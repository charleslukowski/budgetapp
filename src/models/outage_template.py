"""Outage template model - stores reusable outage patterns.

Templates allow users to save common outage scenarios (e.g., "Major Overhaul", 
"Minor Inspection", "Turbine Outage") and apply them to the outage schedule
with one click.
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column, Integer, String, Text, Numeric, DateTime, Boolean,
    ForeignKey, JSON
)
from sqlalchemy.orm import relationship, Session
from typing import Dict, List, Optional

from src.database import Base


class OutageTemplate(Base):
    """A reusable outage pattern template.
    
    Stores the name, description, and default values for a common
    outage type that can be applied to any unit/month.
    """
    
    __tablename__ = "outage_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Template identification
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    
    # Template category
    category = Column(String(50), nullable=True)  # "MAJOR", "MINOR", "INSPECTION", "TURBINE", "BOILER"
    
    # Default outage values
    default_days = Column(Numeric(5, 2), nullable=False, default=21)
    
    # Typical months for this type (JSON array of month numbers)
    # e.g., [4, 10] for spring/fall outages
    typical_months = Column(JSON, nullable=True)
    
    # Typical duration range (for display)
    min_days = Column(Numeric(5, 2), nullable=True)
    max_days = Column(Numeric(5, 2), nullable=True)
    
    # Whether this is a system template (vs user-created)
    is_system_template = Column(Boolean, default=False)
    
    # Color for UI display
    color = Column(String(7), default="#f59e0b")  # Hex color
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<OutageTemplate(id={self.id}, name='{self.name}', days={self.default_days})>"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "default_days": float(self.default_days),
            "typical_months": self.typical_months or [],
            "min_days": float(self.min_days) if self.min_days else None,
            "max_days": float(self.max_days) if self.max_days else None,
            "is_system_template": self.is_system_template,
            "color": self.color,
        }


# =============================================================================
# Helper Functions
# =============================================================================

def get_all_templates(db: Session) -> List[OutageTemplate]:
    """Get all outage templates, system templates first."""
    return db.query(OutageTemplate).order_by(
        OutageTemplate.is_system_template.desc(),
        OutageTemplate.name
    ).all()


def get_template_by_id(db: Session, template_id: int) -> Optional[OutageTemplate]:
    """Get a specific template by ID."""
    return db.query(OutageTemplate).filter(OutageTemplate.id == template_id).first()


def get_template_by_name(db: Session, name: str) -> Optional[OutageTemplate]:
    """Get a template by name."""
    return db.query(OutageTemplate).filter(OutageTemplate.name == name).first()


def create_template(
    db: Session,
    name: str,
    default_days: Decimal,
    description: Optional[str] = None,
    category: Optional[str] = None,
    typical_months: Optional[List[int]] = None,
    min_days: Optional[Decimal] = None,
    max_days: Optional[Decimal] = None,
    color: str = "#f59e0b",
    is_system_template: bool = False,
    created_by: Optional[str] = None,
) -> OutageTemplate:
    """Create a new outage template."""
    template = OutageTemplate(
        name=name,
        description=description,
        category=category,
        default_days=default_days,
        typical_months=typical_months,
        min_days=min_days,
        max_days=max_days,
        color=color,
        is_system_template=is_system_template,
        created_by=created_by,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_template(
    db: Session,
    template_id: int,
    **kwargs
) -> Optional[OutageTemplate]:
    """Update an existing template."""
    template = get_template_by_id(db, template_id)
    if not template:
        return None
    
    # Don't allow modifying system templates
    if template.is_system_template:
        return None
    
    for key, value in kwargs.items():
        if hasattr(template, key):
            setattr(template, key, value)
    
    template.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(template)
    return template


def delete_template(db: Session, template_id: int) -> bool:
    """Delete a template (only user-created ones)."""
    template = get_template_by_id(db, template_id)
    if not template or template.is_system_template:
        return False
    
    db.delete(template)
    db.commit()
    return True


def initialize_system_templates(db: Session) -> int:
    """Initialize default system templates.
    
    Creates standard outage templates if they don't exist.
    Returns the number of templates created.
    """
    templates = [
        {
            "name": "Major Overhaul",
            "description": "Full unit major overhaul including turbine/generator inspection",
            "category": "MAJOR",
            "default_days": Decimal("28"),
            "typical_months": [4, 10],  # Spring and fall
            "min_days": Decimal("21"),
            "max_days": Decimal("42"),
            "color": "#dc2626",  # Red
        },
        {
            "name": "Minor Overhaul",
            "description": "Minor unit overhaul, typically boiler or auxiliary equipment",
            "category": "MINOR",
            "default_days": Decimal("14"),
            "typical_months": [3, 4, 10, 11],
            "min_days": Decimal("7"),
            "max_days": Decimal("21"),
            "color": "#f59e0b",  # Amber
        },
        {
            "name": "Boiler Inspection",
            "description": "Boiler tube inspection and maintenance",
            "category": "INSPECTION",
            "default_days": Decimal("7"),
            "typical_months": [3, 4, 9, 10],
            "min_days": Decimal("5"),
            "max_days": Decimal("10"),
            "color": "#eab308",  # Yellow
        },
        {
            "name": "Turbine Inspection",
            "description": "Turbine generator inspection",
            "category": "INSPECTION",
            "default_days": Decimal("10"),
            "typical_months": [4, 10],
            "min_days": Decimal("7"),
            "max_days": Decimal("14"),
            "color": "#3b82f6",  # Blue
        },
        {
            "name": "SCR Catalyst Change",
            "description": "SCR catalyst replacement outage",
            "category": "INSPECTION",
            "default_days": Decimal("5"),
            "typical_months": [3, 4],
            "min_days": Decimal("3"),
            "max_days": Decimal("7"),
            "color": "#8b5cf6",  # Purple
        },
        {
            "name": "Short Maintenance",
            "description": "Quick maintenance or forced outage recovery",
            "category": "MINOR",
            "default_days": Decimal("3"),
            "typical_months": None,  # Any month
            "min_days": Decimal("1"),
            "max_days": Decimal("5"),
            "color": "#10b981",  # Green
        },
    ]
    
    created_count = 0
    for t in templates:
        existing = get_template_by_name(db, t["name"])
        if not existing:
            create_template(
                db,
                is_system_template=True,
                **t
            )
            created_count += 1
    
    return created_count

