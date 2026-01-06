"""Tests for fuel model calculation engine."""

import pytest
from decimal import Decimal

from src.engine.drivers import (
    FuelModel,
    Driver,
    DriverType,
    DriverCategory,
    DriverValueStore,
    create_calculation,
)
from src.engine.default_drivers import (
    create_default_fuel_model,
    ALL_DRIVERS,
    COAL_PRICE_DRIVERS,
    TRANSPORTATION_DRIVERS,
    HEAT_RATE_DRIVERS,
    GENERATION_DRIVERS,
    INVENTORY_DRIVERS,
    ESCALATION_DRIVERS,
)


class TestDriverValueStore:
    """Tests for DriverValueStore class."""
    
    def test_set_and_get_monthly_value(self):
        """Test setting and getting monthly values."""
        store = DriverValueStore()
        
        store.set_value("coal_price", 2025, 1, Decimal("55.00"))
        
        value = store.get_value("coal_price", 2025, 1, default=Decimal("0"))
        assert value == Decimal("55.00")
    
    def test_set_and_get_annual_value(self):
        """Test setting and getting annual values."""
        store = DriverValueStore()
        
        store.set_value("coal_price", 2025, None, Decimal("50.00"))
        
        # Get annual value via monthly request (should fallback)
        value = store.get_value("coal_price", 2025, 6, default=Decimal("0"))
        assert value == Decimal("50.00")
    
    def test_monthly_overrides_annual(self):
        """Test that monthly value takes precedence over annual."""
        store = DriverValueStore()
        
        store.set_value("coal_price", 2025, None, Decimal("50.00"))  # Annual
        store.set_value("coal_price", 2025, 3, Decimal("55.00"))     # March
        
        # March should use monthly value
        assert store.get_value("coal_price", 2025, 3, default=Decimal("0")) == Decimal("55.00")
        # Other months should use annual
        assert store.get_value("coal_price", 2025, 6, default=Decimal("0")) == Decimal("50.00")
    
    def test_plant_specific_values(self):
        """Test plant-specific value storage."""
        store = DriverValueStore()
        
        # System-wide value
        store.set_value("heat_rate", 2025, None, Decimal("9850"))
        # Plant-specific value
        store.set_value("heat_rate", 2025, None, Decimal("9900"), plant_id=2)
        
        # Plant 2 should use its specific value
        assert store.get_value("heat_rate", 2025, 1, plant_id=2, default=Decimal("0")) == Decimal("9900")
        # Plant 1 (or None) should use system value
        assert store.get_value("heat_rate", 2025, 1, plant_id=1, default=Decimal("0")) == Decimal("9850")
        assert store.get_value("heat_rate", 2025, 1, plant_id=None, default=Decimal("0")) == Decimal("9850")
    
    def test_fallback_to_default(self):
        """Test fallback to provided default."""
        store = DriverValueStore()
        
        value = store.get_value("nonexistent", 2025, 1, default=Decimal("100"))
        assert value == Decimal("100")
    
    def test_get_all_monthly_values(self):
        """Test getting all 12 months."""
        store = DriverValueStore()
        
        store.set_value("use_factor", 2025, None, Decimal("85"))  # Annual default
        store.set_value("use_factor", 2025, 7, Decimal("90"))     # July override
        store.set_value("use_factor", 2025, 8, Decimal("92"))     # August override
        
        values = store.get_all_monthly_values("use_factor", 2025, default=Decimal("80"))
        
        assert values[1] == Decimal("85")   # Jan uses annual
        assert values[7] == Decimal("90")   # July uses specific
        assert values[8] == Decimal("92")   # August uses specific
        assert values[12] == Decimal("85")  # Dec uses annual


class TestDriver:
    """Tests for Driver dataclass."""
    
    def test_driver_creation(self):
        """Test creating a driver."""
        driver = Driver(
            name="test_driver",
            driver_type=DriverType.PRICE_INDEX,
            unit="$/ton",
            default_value=Decimal("100"),
            category=DriverCategory.COAL_PRICE,
            description="Test driver",
        )
        
        assert driver.name == "test_driver"
        assert driver.driver_type == DriverType.PRICE_INDEX
        assert driver.default_value == Decimal("100")
    
    def test_driver_equality(self):
        """Test driver equality is based on name."""
        driver1 = Driver(name="coal_price", driver_type=DriverType.PRICE_INDEX, unit="$/ton")
        driver2 = Driver(name="coal_price", driver_type=DriverType.RATE, unit="$/mmbtu")
        driver3 = Driver(name="other", driver_type=DriverType.PRICE_INDEX, unit="$/ton")
        
        assert driver1 == driver2  # Same name
        assert driver1 != driver3  # Different name
    
    def test_driver_hash(self):
        """Test driver is hashable (for use in sets/dicts)."""
        driver = Driver(name="coal_price", driver_type=DriverType.PRICE_INDEX, unit="$/ton")
        
        # Should be hashable
        driver_set = {driver}
        assert driver in driver_set


class TestFuelModel:
    """Tests for FuelModel class."""
    
    def test_register_driver(self):
        """Test driver registration."""
        model = FuelModel()
        
        driver = Driver(
            name="test_driver",
            driver_type=DriverType.PRICE_INDEX,
            unit="$/ton",
            default_value=Decimal("100"),
        )
        
        model.register_driver(driver)
        
        assert "test_driver" in model.drivers
        assert model.drivers["test_driver"].default_value == Decimal("100")
    
    def test_register_multiple_drivers(self):
        """Test registering multiple drivers at once."""
        model = FuelModel()
        
        drivers = [
            Driver(name="driver1", driver_type=DriverType.INPUT, unit=""),
            Driver(name="driver2", driver_type=DriverType.INPUT, unit=""),
        ]
        
        model.register_drivers(drivers)
        
        assert "driver1" in model.drivers
        assert "driver2" in model.drivers
    
    def test_set_and_get_driver_value(self):
        """Test setting and getting driver values."""
        model = FuelModel()
        
        driver = Driver(
            name="coal_price",
            driver_type=DriverType.PRICE_INDEX,
            unit="$/mmbtu",
            default_value=Decimal("2.50"),
        )
        model.register_driver(driver)
        
        # Set value for Jan 2025
        model.set_driver_value("coal_price", 2025, 1, Decimal("2.75"))
        
        # Get value
        value = model.get_driver_value("coal_price", 2025, 1)
        assert value == Decimal("2.75")
    
    def test_driver_value_fallback_to_default(self):
        """Test fallback to default value."""
        model = FuelModel()
        
        driver = Driver(
            name="coal_price",
            driver_type=DriverType.PRICE_INDEX,
            unit="$/mmbtu",
            default_value=Decimal("2.50"),
        )
        model.register_driver(driver)
        
        # Get value for period with no set value
        value = model.get_driver_value("coal_price", 2025, 3)
        assert value == Decimal("2.50")
    
    def test_driver_value_fallback_to_annual(self):
        """Test fallback from monthly to annual value."""
        model = FuelModel()
        
        driver = Driver(
            name="coal_price",
            driver_type=DriverType.PRICE_INDEX,
            unit="$/mmbtu",
            default_value=Decimal("2.50"),
        )
        model.register_driver(driver)
        
        # Set annual value
        model.set_driver_value("coal_price", 2025, None, Decimal("2.60"))
        
        # Get monthly value should fallback to annual
        value = model.get_driver_value("coal_price", 2025, 6)
        assert value == Decimal("2.60")
    
    def test_unknown_driver_raises(self):
        """Test that unknown driver raises error."""
        model = FuelModel()
        
        with pytest.raises(ValueError):
            model.get_driver_value("unknown_driver", 2025, 1)
    
    def test_unknown_driver_set_raises(self):
        """Test that setting unknown driver raises error."""
        model = FuelModel()
        
        with pytest.raises(ValueError):
            model.set_driver_value("unknown_driver", 2025, 1, Decimal("100"))
    
    def test_get_driver(self):
        """Test getting a driver definition."""
        model = FuelModel()
        driver = Driver(name="test", driver_type=DriverType.INPUT, unit="")
        model.register_driver(driver)
        
        retrieved = model.get_driver("test")
        assert retrieved.name == "test"
    
    def test_get_unknown_driver_raises(self):
        """Test getting unknown driver raises error."""
        model = FuelModel()
        
        with pytest.raises(ValueError):
            model.get_driver("unknown")
    
    def test_calculated_driver(self):
        """Test a calculated driver."""
        model = FuelModel()
        
        # Register base drivers
        model.register_driver(Driver(
            name="price",
            driver_type=DriverType.PRICE_INDEX,
            unit="$/ton",
            default_value=Decimal("50"),
        ))
        model.register_driver(Driver(
            name="quantity",
            driver_type=DriverType.VOLUME,
            unit="tons",
            default_value=Decimal("100"),
        ))
        
        # Register calculated driver
        def calc_cost(m, y, mo, p=None):
            price = m.get_driver_value("price", y, mo, p)
            qty = m.get_driver_value("quantity", y, mo, p)
            return price * qty
        
        model.register_driver(Driver(
            name="total_cost",
            driver_type=DriverType.CALCULATED,
            unit="$",
            depends_on=["price", "quantity"],
            calculation=calc_cost,
        ))
        
        # Calculate
        cost = model.get_driver_value("total_cost", 2025, 1)
        assert cost == Decimal("5000")  # 50 * 100
    
    def test_get_input_drivers(self):
        """Test filtering to input-only drivers."""
        model = FuelModel()
        
        model.register_driver(Driver(name="input1", driver_type=DriverType.INPUT, unit=""))
        model.register_driver(Driver(name="input2", driver_type=DriverType.PRICE_INDEX, unit=""))
        model.register_driver(Driver(name="calc1", driver_type=DriverType.CALCULATED, unit=""))
        
        inputs = model.get_input_drivers()
        names = [d.name for d in inputs]
        
        assert "input1" in names
        assert "input2" in names
        assert "calc1" not in names
    
    def test_get_calculated_drivers(self):
        """Test filtering to calculated drivers."""
        model = FuelModel()
        
        model.register_driver(Driver(name="input1", driver_type=DriverType.INPUT, unit=""))
        model.register_driver(Driver(name="calc1", driver_type=DriverType.CALCULATED, unit=""))
        
        calcs = model.get_calculated_drivers()
        names = [d.name for d in calcs]
        
        assert "calc1" in names
        assert "input1" not in names


class TestDefaultDrivers:
    """Tests for default OVEC driver definitions."""
    
    def test_default_fuel_model_creation(self):
        """Test creating default OVEC fuel model."""
        model = create_default_fuel_model()
        
        # Check some expected drivers exist
        assert "coal_price_eastern" in model.drivers
        assert "coal_price_ilb" in model.drivers
        assert "heat_rate_baseline" in model.drivers
        assert "generation_mwh" in model.drivers
        assert "use_factor" in model.drivers
    
    def test_all_drivers_have_required_fields(self):
        """Test that all default drivers have required fields."""
        for driver in ALL_DRIVERS:
            assert driver.name, f"Driver missing name"
            assert driver.driver_type is not None, f"Driver {driver.name} missing type"
            assert driver.unit is not None, f"Driver {driver.name} missing unit"
            assert driver.category is not None, f"Driver {driver.name} missing category"
    
    def test_driver_categories_are_populated(self):
        """Test that driver categories contain drivers."""
        assert len(COAL_PRICE_DRIVERS) > 0
        assert len(TRANSPORTATION_DRIVERS) > 0
        assert len(HEAT_RATE_DRIVERS) > 0
        assert len(GENERATION_DRIVERS) > 0
        assert len(INVENTORY_DRIVERS) > 0
        assert len(ESCALATION_DRIVERS) > 0
    
    def test_calculation_order_respects_dependencies(self):
        """Test that calculated drivers come after their dependencies."""
        model = create_default_fuel_model()
        
        order = model.calculation_order
        
        # coal_price_blended depends on coal_price_eastern
        if "coal_price_blended" in order and "coal_price_eastern" in order:
            blended_idx = order.index("coal_price_blended")
            eastern_idx = order.index("coal_price_eastern")
            assert blended_idx > eastern_idx, "Blended price should come after eastern price"
        
        # heat_rate_effective depends on heat_rate_baseline
        if "heat_rate_effective" in order and "heat_rate_baseline" in order:
            effective_idx = order.index("heat_rate_effective")
            baseline_idx = order.index("heat_rate_baseline")
            assert effective_idx > baseline_idx, "Effective heat rate should come after baseline"
    
    def test_no_circular_dependencies(self):
        """Test that driver dependencies don't form cycles."""
        model = create_default_fuel_model()
        
        # This should not raise - if there are cycles, topological sort would fail
        order = model.calculation_order
        assert len(order) == len(model.drivers)
    
    def test_validate_dependencies(self):
        """Test dependency validation."""
        model = create_default_fuel_model()
        
        errors = model.validate_dependencies()
        assert len(errors) == 0, f"Dependency errors: {errors}"
    
    def test_calculated_drivers_have_calculations(self):
        """Test that calculated drivers have calculation functions."""
        for driver in ALL_DRIVERS:
            if driver.driver_type == DriverType.CALCULATED:
                assert driver.calculation is not None, \
                    f"Calculated driver {driver.name} missing calculation function"
    
    def test_coal_price_blended_calculation(self):
        """Test the blended coal price calculation."""
        model = create_default_fuel_model()
        
        # Set specific values
        model.set_driver_value("coal_price_eastern", 2025, None, Decimal("60"))
        model.set_driver_value("coal_price_ilb", 2025, None, Decimal("40"))
        model.set_driver_value("coal_price_prb", 2025, None, Decimal("20"))
        model.set_driver_value("coal_blend_eastern_pct", 2025, None, Decimal("50"))
        model.set_driver_value("coal_blend_ilb_pct", 2025, None, Decimal("50"))
        model.set_driver_value("coal_blend_prb_pct", 2025, None, Decimal("0"))
        
        blended = model.get_driver_value("coal_price_blended", 2025, 1)
        
        # (60 * 0.5 + 40 * 0.5 + 20 * 0) / 1.0 = 50
        assert blended == Decimal("50")
    
    def test_heat_rate_effective_calculation(self):
        """Test the effective heat rate calculation."""
        model = create_default_fuel_model()
        
        model.set_driver_value("heat_rate_baseline", 2025, None, Decimal("9850"))
        model.set_driver_value("heat_rate_suf_correction", 2025, None, Decimal("50"))
        model.set_driver_value("coal_blend_prb_pct", 2025, None, Decimal("10"))
        model.set_driver_value("heat_rate_prb_penalty", 2025, None, Decimal("100"))
        
        effective = model.get_driver_value("heat_rate_effective", 2025, 1)
        
        # 9850 + 50 + (10/100 * 100) = 9850 + 50 + 10 = 9910
        assert effective == Decimal("9910")


class TestCreateCalculation:
    """Tests for the create_calculation helper."""
    
    def test_create_simple_calculation(self):
        """Test creating a calculation function."""
        model = FuelModel()
        
        model.register_driver(Driver(name="a", driver_type=DriverType.INPUT, unit="", default_value=Decimal("10")))
        model.register_driver(Driver(name="b", driver_type=DriverType.INPUT, unit="", default_value=Decimal("5")))
        
        calc_func = create_calculation("a", "b", formula=lambda deps: deps["a"] + deps["b"])
        
        model.register_driver(Driver(
            name="c",
            driver_type=DriverType.CALCULATED,
            unit="",
            depends_on=["a", "b"],
            calculation=calc_func,
        ))
        
        result = model.get_driver_value("c", 2025, 1)
        assert result == Decimal("15")
