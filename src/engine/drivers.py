"""Driver-based forecasting framework.

Provides a flexible system for managing forecast drivers:
- Driver definitions with types, units, and dependencies
- Period-based value storage with fallback logic
- Calculation ordering via topological sort
- Integration with existing fuel cost calculation engine
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Set, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class DriverType(Enum):
    """Types of drivers in the forecasting model."""
    INPUT = "input"              # User-provided input value
    PRICE_INDEX = "price_index"  # Market price index (coal, gas, etc.)
    RATE = "rate"                # Rate per unit ($/ton, BTU/kWh)
    VOLUME = "volume"            # Quantity (tons, MWh, hours)
    PERCENTAGE = "percentage"    # Percentage value (0-100 or 0-1)
    CALCULATED = "calculated"    # Derived from other drivers
    TOGGLE = "toggle"            # Boolean on/off flag


class DriverCategory(Enum):
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


@dataclass
class Driver:
    """Definition of a forecast driver.
    
    A driver is a named variable that can hold values for different time periods.
    Drivers can be simple inputs or calculated from other drivers.
    """
    name: str
    driver_type: DriverType
    unit: str
    default_value: Decimal = Decimal("0")
    category: DriverCategory = DriverCategory.OTHER
    description: str = ""
    
    # For calculated drivers
    depends_on: List[str] = field(default_factory=list)
    calculation: Optional[Callable[['FuelModel', int, int], Decimal]] = None
    
    # Display/UI hints
    display_order: int = 0
    min_value: Optional[Decimal] = None
    max_value: Optional[Decimal] = None
    step: Decimal = Decimal("1")
    
    # Plant-specific flag
    is_plant_specific: bool = False
    
    def __post_init__(self):
        """Validate driver configuration."""
        if self.driver_type == DriverType.CALCULATED and not self.calculation:
            logger.warning(f"Driver '{self.name}' is CALCULATED but has no calculation function")
        if self.driver_type != DriverType.CALCULATED and self.depends_on:
            logger.warning(f"Driver '{self.name}' has dependencies but is not CALCULATED type")

    def __hash__(self):
        return hash(self.name)
    
    def __eq__(self, other):
        if isinstance(other, Driver):
            return self.name == other.name
        return False


class DriverValueStore:
    """Stores driver values by period with fallback logic.
    
    Values are stored in a hierarchy:
    - Monthly values (most specific)
    - Annual values (fallback for any month in that year)
    - Default value (ultimate fallback)
    
    Values can also be plant-specific.
    """
    
    def __init__(self):
        # Structure: {driver_name: {plant_id: {(year, month): value}}}
        # plant_id of None means system-wide value
        self._values: Dict[str, Dict[Optional[int], Dict[Tuple[int, Optional[int]], Decimal]]] = defaultdict(
            lambda: defaultdict(dict)
        )
    
    def set_value(
        self,
        driver_name: str,
        year: int,
        month: Optional[int],
        value: Decimal,
        plant_id: Optional[int] = None,
    ) -> None:
        """Set a driver value for a specific period.
        
        Args:
            driver_name: Name of the driver
            year: Year
            month: Month (1-12) or None for annual value
            value: The value to set
            plant_id: Optional plant ID for plant-specific values
        """
        self._values[driver_name][plant_id][(year, month)] = value
    
    def get_value(
        self,
        driver_name: str,
        year: int,
        month: int,
        plant_id: Optional[int] = None,
        default: Decimal = Decimal("0"),
    ) -> Decimal:
        """Get a driver value with fallback logic.
        
        Fallback order:
        1. Plant-specific monthly value
        2. Plant-specific annual value
        3. System-wide monthly value
        4. System-wide annual value
        5. Provided default
        
        Args:
            driver_name: Name of the driver
            year: Year
            month: Month (1-12)
            plant_id: Optional plant ID
            default: Default value if not found
            
        Returns:
            The driver value
        """
        driver_values = self._values.get(driver_name, {})
        
        # Try plant-specific first
        if plant_id is not None:
            plant_values = driver_values.get(plant_id, {})
            # Try monthly
            if (year, month) in plant_values:
                return plant_values[(year, month)]
            # Try annual
            if (year, None) in plant_values:
                return plant_values[(year, None)]
        
        # Fall back to system-wide
        system_values = driver_values.get(None, {})
        # Try monthly
        if (year, month) in system_values:
            return system_values[(year, month)]
        # Try annual
        if (year, None) in system_values:
            return system_values[(year, None)]
        
        return default
    
    def get_all_monthly_values(
        self,
        driver_name: str,
        year: int,
        plant_id: Optional[int] = None,
        default: Decimal = Decimal("0"),
    ) -> Dict[int, Decimal]:
        """Get values for all 12 months of a year.
        
        Args:
            driver_name: Name of the driver
            year: Year
            plant_id: Optional plant ID
            default: Default value for months without explicit values
            
        Returns:
            Dict mapping month (1-12) to value
        """
        return {
            month: self.get_value(driver_name, year, month, plant_id, default)
            for month in range(1, 13)
        }
    
    def clear(self, driver_name: Optional[str] = None) -> None:
        """Clear stored values.
        
        Args:
            driver_name: If provided, only clear values for this driver.
                        If None, clear all values.
        """
        if driver_name:
            if driver_name in self._values:
                del self._values[driver_name]
        else:
            self._values.clear()
    
    def get_stored_drivers(self) -> List[str]:
        """Get list of driver names that have stored values."""
        return list(self._values.keys())


class FuelModel:
    """Main driver-based fuel forecasting model.
    
    Manages driver definitions, values, and calculations.
    Supports dependency resolution and topological ordering.
    """
    
    def __init__(self):
        self.drivers: Dict[str, Driver] = {}
        self.values = DriverValueStore()
        self._calculation_order: List[str] = []
        self._order_dirty: bool = True
    
    def register_driver(self, driver: Driver) -> None:
        """Register a driver definition.
        
        Args:
            driver: Driver to register
        """
        if driver.name in self.drivers:
            logger.warning(f"Overwriting existing driver: {driver.name}")
        
        self.drivers[driver.name] = driver
        self._order_dirty = True
    
    def register_drivers(self, drivers: List[Driver]) -> None:
        """Register multiple drivers at once.
        
        Args:
            drivers: List of drivers to register
        """
        for driver in drivers:
            self.register_driver(driver)
    
    def get_driver(self, name: str) -> Driver:
        """Get a driver definition by name.
        
        Args:
            name: Driver name
            
        Returns:
            Driver definition
            
        Raises:
            ValueError: If driver not found
        """
        if name not in self.drivers:
            raise ValueError(f"Unknown driver: {name}")
        return self.drivers[name]
    
    def set_driver_value(
        self,
        driver_name: str,
        year: int,
        month: Optional[int],
        value: Decimal,
        plant_id: Optional[int] = None,
    ) -> None:
        """Set a driver value for a period.
        
        Args:
            driver_name: Name of the driver
            year: Year
            month: Month (1-12) or None for annual value
            value: The value to set
            plant_id: Optional plant ID for plant-specific values
            
        Raises:
            ValueError: If driver not registered
        """
        if driver_name not in self.drivers:
            raise ValueError(f"Unknown driver: {driver_name}")
        
        self.values.set_value(driver_name, year, month, value, plant_id)
    
    def get_driver_value(
        self,
        driver_name: str,
        year: int,
        month: int,
        plant_id: Optional[int] = None,
    ) -> Decimal:
        """Get a driver value for a period.
        
        For calculated drivers, this will compute the value.
        For input drivers, this retrieves from the value store.
        
        Args:
            driver_name: Name of the driver
            year: Year
            month: Month (1-12)
            plant_id: Optional plant ID
            
        Returns:
            The driver value
            
        Raises:
            ValueError: If driver not registered
        """
        if driver_name not in self.drivers:
            raise ValueError(f"Unknown driver: {driver_name}")
        
        driver = self.drivers[driver_name]
        
        # For calculated drivers, compute the value
        if driver.driver_type == DriverType.CALCULATED and driver.calculation:
            return driver.calculation(self, year, month, plant_id)
        
        # For input drivers, get from store with default fallback
        return self.values.get_value(
            driver_name, year, month, plant_id, driver.default_value
        )
    
    def get_all_driver_values(
        self,
        year: int,
        month: int,
        plant_id: Optional[int] = None,
    ) -> Dict[str, Decimal]:
        """Get all driver values for a period.
        
        Args:
            year: Year
            month: Month (1-12)
            plant_id: Optional plant ID
            
        Returns:
            Dict mapping driver name to value
        """
        result = {}
        for name in self._get_calculation_order():
            result[name] = self.get_driver_value(name, year, month, plant_id)
        return result
    
    def _get_calculation_order(self) -> List[str]:
        """Get drivers in dependency order (topological sort).
        
        Returns:
            List of driver names in calculation order
        """
        if not self._order_dirty:
            return self._calculation_order
        
        # Build dependency graph
        visited: Set[str] = set()
        temp_visited: Set[str] = set()
        order: List[str] = []
        
        def visit(name: str) -> None:
            if name in temp_visited:
                raise ValueError(f"Circular dependency detected involving: {name}")
            if name in visited:
                return
            
            temp_visited.add(name)
            
            driver = self.drivers.get(name)
            if driver:
                for dep in driver.depends_on:
                    if dep in self.drivers:
                        visit(dep)
            
            temp_visited.remove(name)
            visited.add(name)
            order.append(name)
        
        # Visit all drivers
        for name in self.drivers:
            if name not in visited:
                visit(name)
        
        self._calculation_order = order
        self._order_dirty = False
        
        return self._calculation_order
    
    @property
    def calculation_order(self) -> List[str]:
        """Get the calculation order (for testing/debugging)."""
        return self._get_calculation_order()
    
    def get_drivers_by_category(self, category: DriverCategory) -> List[Driver]:
        """Get all drivers in a category.
        
        Args:
            category: The category to filter by
            
        Returns:
            List of drivers in that category
        """
        return [d for d in self.drivers.values() if d.category == category]
    
    def get_input_drivers(self) -> List[Driver]:
        """Get all non-calculated drivers (user inputs).
        
        Returns:
            List of input drivers
        """
        return [
            d for d in self.drivers.values()
            if d.driver_type != DriverType.CALCULATED
        ]
    
    def get_calculated_drivers(self) -> List[Driver]:
        """Get all calculated drivers.
        
        Returns:
            List of calculated drivers
        """
        return [
            d for d in self.drivers.values()
            if d.driver_type == DriverType.CALCULATED
        ]
    
    def validate_dependencies(self) -> List[str]:
        """Validate that all driver dependencies exist.
        
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        for name, driver in self.drivers.items():
            for dep in driver.depends_on:
                if dep not in self.drivers:
                    errors.append(f"Driver '{name}' depends on unknown driver '{dep}'")
        return errors
    
    def to_dict(self, year: int, month: int, plant_id: Optional[int] = None) -> Dict:
        """Export all driver values as a dictionary.
        
        Args:
            year: Year
            month: Month
            plant_id: Optional plant ID
            
        Returns:
            Dict with driver metadata and values
        """
        return {
            "year": year,
            "month": month,
            "plant_id": plant_id,
            "drivers": {
                name: {
                    "value": float(self.get_driver_value(name, year, month, plant_id)),
                    "type": driver.driver_type.value,
                    "category": driver.category.value,
                    "unit": driver.unit,
                }
                for name, driver in self.drivers.items()
            }
        }
    
    def copy(self) -> 'FuelModel':
        """Create a copy of this model with the same drivers but empty values.
        
        Returns:
            New FuelModel instance
        """
        new_model = FuelModel()
        for driver in self.drivers.values():
            new_model.register_driver(driver)
        return new_model


def create_calculation(
    *dependencies: str,
    formula: Callable[[Dict[str, Decimal]], Decimal],
) -> Callable[['FuelModel', int, int, Optional[int]], Decimal]:
    """Helper to create a calculation function for a driver.
    
    Args:
        dependencies: Names of drivers this calculation depends on
        formula: Function that takes a dict of dependency values and returns result
        
    Returns:
        Calculation function suitable for Driver.calculation
    """
    def calc(model: FuelModel, year: int, month: int, plant_id: Optional[int] = None) -> Decimal:
        dep_values = {
            dep: model.get_driver_value(dep, year, month, plant_id)
            for dep in dependencies
        }
        return formula(dep_values)
    return calc

