"""Scenario-based driver management.

Functions for loading and saving complete driver value sets to/from scenarios.
Enables copying drivers between scenarios and comparing driver values.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
import json

from sqlalchemy.orm import Session

from src.engine.drivers import FuelModel, DriverValueStore
from src.engine.default_drivers import create_default_fuel_model, ALL_DRIVERS
from src.models.driver import DriverDefinition, DriverValue, DriverValueHistory

logger = logging.getLogger(__name__)


@dataclass
class ScenarioDriverSet:
    """Complete set of driver values for a scenario/year."""
    scenario_id: int
    year: int
    driver_values: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Structure: {driver_name: {"annual": value, "monthly": {1: val, 2: val, ...}, "plant_specific": {...}}}
    
    def to_dict(self) -> Dict:
        """Export as dictionary."""
        return {
            "scenario_id": self.scenario_id,
            "year": self.year,
            "drivers": self.driver_values,
            "exported_at": datetime.utcnow().isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ScenarioDriverSet':
        """Create from dictionary."""
        return cls(
            scenario_id=data.get("scenario_id", 0),
            year=data.get("year", 0),
            driver_values=data.get("drivers", {}),
        )
    
    def to_json(self) -> str:
        """Export as JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'ScenarioDriverSet':
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


def ensure_driver_definitions(db: Session) -> Dict[str, DriverDefinition]:
    """Ensure all driver definitions exist in database.
    
    Creates any missing driver definitions from the default drivers.
    
    Returns:
        Dict mapping driver name to DriverDefinition
    """
    existing = {d.name: d for d in db.query(DriverDefinition).all()}
    
    for driver in ALL_DRIVERS:
        if driver.name not in existing:
            db_driver = DriverDefinition(
                name=driver.name,
                description=driver.description,
                driver_type=driver.driver_type.value,
                category=driver.category.value,
                unit=driver.unit,
                default_value=driver.default_value,
                min_value=driver.min_value,
                max_value=driver.max_value,
                step=driver.step,
                is_plant_specific=driver.is_plant_specific,
                display_order=driver.display_order,
            )
            if driver.depends_on:
                db_driver.set_dependencies(driver.depends_on)
            db.add(db_driver)
            existing[driver.name] = db_driver
    
    db.flush()
    return existing


def load_driver_values_from_scenario(
    db: Session,
    scenario_id: int,
    year: int,
    plant_id: Optional[int] = None,
) -> FuelModel:
    """Load a FuelModel with values from a scenario.
    
    Args:
        db: Database session
        scenario_id: Scenario to load from
        year: Year to load values for
        plant_id: Optional specific plant
        
    Returns:
        FuelModel populated with values from the scenario
    """
    model = create_default_fuel_model()
    
    # Build query
    query = db.query(DriverValue).join(DriverDefinition).filter(
        DriverValue.scenario_id == scenario_id,
        DriverValue.period_yyyymm.like(f"{year}%"),
    )
    
    if plant_id is not None:
        query = query.filter(
            (DriverValue.plant_id == plant_id) | (DriverValue.plant_id.is_(None))
        )
    
    values = query.all()
    
    # Load values into model
    for v in values:
        driver_name = v.driver.name
        period = v.period_yyyymm
        
        # Parse year and month from period
        v_year = int(period[:4])
        v_month = int(period[4:6]) if len(period) == 6 else None
        
        try:
            model.set_driver_value(
                driver_name,
                v_year,
                v_month,
                v.value,
                v.plant_id,
            )
        except ValueError:
            # Driver not registered in model
            logger.warning(f"Skipping unknown driver: {driver_name}")
    
    return model


def save_driver_values_to_scenario(
    db: Session,
    model: FuelModel,
    scenario_id: int,
    year: int,
    updated_by: Optional[str] = None,
) -> int:
    """Save driver values from a FuelModel to a scenario.
    
    Args:
        db: Database session
        model: FuelModel with values to save
        scenario_id: Target scenario ID
        year: Year to save values for
        updated_by: Optional username for audit
        
    Returns:
        Number of values saved
    """
    # Ensure driver definitions exist
    driver_defs = ensure_driver_definitions(db)
    
    saved_count = 0
    
    # Get all stored driver names
    stored_drivers = model.values.get_stored_drivers()
    
    for driver_name in stored_drivers:
        if driver_name not in driver_defs:
            logger.warning(f"Skipping unknown driver: {driver_name}")
            continue
        
        driver_def = driver_defs[driver_name]
        driver_values = model.values._values.get(driver_name, {})
        
        for plant_id, period_values in driver_values.items():
            for (v_year, v_month), value in period_values.items():
                if v_year != year:
                    continue
                
                # Format period
                if v_month:
                    period_yyyymm = f"{v_year}{v_month:02d}"
                else:
                    period_yyyymm = str(v_year)
                
                # Check for existing value
                existing = db.query(DriverValue).filter(
                    DriverValue.scenario_id == scenario_id,
                    DriverValue.driver_id == driver_def.id,
                    DriverValue.plant_id == plant_id,
                    DriverValue.period_yyyymm == period_yyyymm,
                ).first()
                
                if existing:
                    if existing.value != value:
                        old_value = existing.value
                        existing.value = value
                        existing.updated_at = datetime.utcnow()
                        existing.updated_by = updated_by
                        
                        # Record history
                        history = DriverValueHistory(
                            driver_value_id=existing.id,
                            scenario_id=scenario_id,
                            driver_id=driver_def.id,
                            plant_id=plant_id,
                            period_yyyymm=period_yyyymm,
                            old_value=old_value,
                            new_value=value,
                            change_type="update",
                            changed_by=updated_by,
                        )
                        db.add(history)
                    saved_count += 1
                else:
                    new_value = DriverValue(
                        scenario_id=scenario_id,
                        driver_id=driver_def.id,
                        plant_id=plant_id,
                        period_yyyymm=period_yyyymm,
                        value=value,
                        updated_by=updated_by,
                    )
                    db.add(new_value)
                    db.flush()
                    
                    # Record history
                    history = DriverValueHistory(
                        driver_value_id=new_value.id,
                        scenario_id=scenario_id,
                        driver_id=driver_def.id,
                        plant_id=plant_id,
                        period_yyyymm=period_yyyymm,
                        old_value=None,
                        new_value=value,
                        change_type="create",
                        changed_by=updated_by,
                    )
                    db.add(history)
                    saved_count += 1
    
    db.commit()
    return saved_count


def copy_scenario_drivers(
    db: Session,
    source_scenario_id: int,
    target_scenario_id: int,
    year: int,
    overwrite: bool = False,
    updated_by: Optional[str] = None,
) -> int:
    """Copy driver values from one scenario to another.
    
    Args:
        db: Database session
        source_scenario_id: Source scenario to copy from
        target_scenario_id: Target scenario to copy to
        year: Year to copy
        overwrite: If True, overwrite existing values in target
        updated_by: Optional username for audit
        
    Returns:
        Number of values copied
    """
    # Load source values
    source_model = load_driver_values_from_scenario(db, source_scenario_id, year)
    
    if not overwrite:
        # Load existing target values to avoid overwriting
        target_model = load_driver_values_from_scenario(db, target_scenario_id, year)
        
        # Merge: source values into target, but don't overwrite existing
        for driver_name in source_model.values.get_stored_drivers():
            source_values = source_model.values._values.get(driver_name, {})
            target_values = target_model.values._values.get(driver_name, {})
            
            for plant_id, period_values in source_values.items():
                for period, value in period_values.items():
                    # Only copy if not already in target
                    if plant_id not in target_values or period not in target_values[plant_id]:
                        target_model.set_driver_value(driver_name, period[0], period[1], value, plant_id)
        
        return save_driver_values_to_scenario(db, target_model, target_scenario_id, year, updated_by)
    else:
        return save_driver_values_to_scenario(db, source_model, target_scenario_id, year, updated_by)


def export_scenario_drivers(
    db: Session,
    scenario_id: int,
    year: int,
) -> ScenarioDriverSet:
    """Export all driver values for a scenario/year.
    
    Args:
        db: Database session
        scenario_id: Scenario to export
        year: Year to export
        
    Returns:
        ScenarioDriverSet with all values
    """
    result = ScenarioDriverSet(scenario_id=scenario_id, year=year)
    
    # Query all values
    values = db.query(DriverValue).join(DriverDefinition).filter(
        DriverValue.scenario_id == scenario_id,
        DriverValue.period_yyyymm.like(f"{year}%"),
    ).all()
    
    for v in values:
        driver_name = v.driver.name
        period = v.period_yyyymm
        is_annual = len(period) == 4
        month = int(period[4:6]) if not is_annual else None
        plant_id = v.plant_id
        
        if driver_name not in result.driver_values:
            result.driver_values[driver_name] = {
                "annual": None,
                "monthly": {},
                "plant_specific": {},
            }
        
        entry = result.driver_values[driver_name]
        
        if plant_id is not None:
            # Plant-specific value
            if plant_id not in entry["plant_specific"]:
                entry["plant_specific"][plant_id] = {"annual": None, "monthly": {}}
            
            if is_annual:
                entry["plant_specific"][plant_id]["annual"] = float(v.value)
            else:
                entry["plant_specific"][plant_id]["monthly"][month] = float(v.value)
        else:
            # System-wide value
            if is_annual:
                entry["annual"] = float(v.value)
            else:
                entry["monthly"][month] = float(v.value)
    
    return result


def import_scenario_drivers(
    db: Session,
    scenario_id: int,
    driver_set: ScenarioDriverSet,
    overwrite: bool = True,
    updated_by: Optional[str] = None,
) -> int:
    """Import driver values into a scenario.
    
    Args:
        db: Database session
        scenario_id: Target scenario
        driver_set: Driver values to import
        overwrite: Whether to overwrite existing values
        updated_by: Optional username for audit
        
    Returns:
        Number of values imported
    """
    model = create_default_fuel_model()
    year = driver_set.year
    
    for driver_name, values in driver_set.driver_values.items():
        try:
            # System-wide annual value
            if values.get("annual") is not None:
                model.set_driver_value(driver_name, year, None, Decimal(str(values["annual"])))
            
            # System-wide monthly values
            for month, value in values.get("monthly", {}).items():
                model.set_driver_value(driver_name, year, int(month), Decimal(str(value)))
            
            # Plant-specific values
            for plant_id, plant_values in values.get("plant_specific", {}).items():
                plant_id = int(plant_id)
                
                if plant_values.get("annual") is not None:
                    model.set_driver_value(driver_name, year, None, 
                                          Decimal(str(plant_values["annual"])), plant_id=plant_id)
                
                for month, value in plant_values.get("monthly", {}).items():
                    model.set_driver_value(driver_name, year, int(month), 
                                          Decimal(str(value)), plant_id=plant_id)
        except ValueError:
            logger.warning(f"Unknown driver in import: {driver_name}")
    
    return save_driver_values_to_scenario(db, model, scenario_id, year, updated_by)


def compare_scenario_drivers(
    db: Session,
    scenario_a_id: int,
    scenario_b_id: int,
    year: int,
) -> Dict[str, Any]:
    """Compare driver values between two scenarios.
    
    Args:
        db: Database session
        scenario_a_id: First scenario
        scenario_b_id: Second scenario
        year: Year to compare
        
    Returns:
        Dict with comparison results
    """
    set_a = export_scenario_drivers(db, scenario_a_id, year)
    set_b = export_scenario_drivers(db, scenario_b_id, year)
    
    all_drivers = set(set_a.driver_values.keys()) | set(set_b.driver_values.keys())
    
    differences = []
    same = []
    only_in_a = []
    only_in_b = []
    
    for driver_name in sorted(all_drivers):
        in_a = driver_name in set_a.driver_values
        in_b = driver_name in set_b.driver_values
        
        if in_a and not in_b:
            only_in_a.append(driver_name)
        elif in_b and not in_a:
            only_in_b.append(driver_name)
        else:
            val_a = set_a.driver_values[driver_name]
            val_b = set_b.driver_values[driver_name]
            
            if val_a == val_b:
                same.append(driver_name)
            else:
                differences.append({
                    "driver": driver_name,
                    "scenario_a": val_a,
                    "scenario_b": val_b,
                })
    
    return {
        "scenario_a_id": scenario_a_id,
        "scenario_b_id": scenario_b_id,
        "year": year,
        "total_drivers": len(all_drivers),
        "same_count": len(same),
        "different_count": len(differences),
        "only_in_a_count": len(only_in_a),
        "only_in_b_count": len(only_in_b),
        "differences": differences,
        "only_in_a": only_in_a,
        "only_in_b": only_in_b,
    }

