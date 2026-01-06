"""Tests for database models."""

import pytest
from decimal import Decimal

from src.models import Plant, Period, CostCategory, Scenario, Forecast
from src.models.period import Granularity
from src.models.cost_category import CostSection
from src.models.scenario import ScenarioType, ScenarioStatus


class TestPlant:
    """Tests for Plant model."""
    
    def test_max_annual_generation(self):
        """Test max annual generation calculation."""
        plant = Plant(
            name="Test Plant",
            short_name="Test",
            capacity_mw=1000,
            unit_count=5,
            unit_capacity_mw=200,
        )
        
        assert plant.max_annual_generation_mwh == 1000 * 8760
    
    def test_generation_at_capacity_factor(self):
        """Test generation at specific capacity factor."""
        plant = Plant(
            name="Test Plant",
            short_name="Test",
            capacity_mw=1000,
            unit_count=5,
            unit_capacity_mw=200,
        )
        
        # 70% capacity factor
        expected = 1000 * 8760 * 0.70
        assert plant.generation_at_capacity_factor(0.70) == expected


class TestPeriod:
    """Tests for Period model."""
    
    def test_monthly_display_name(self):
        """Test monthly period display name."""
        period = Period(
            year=2025,
            month=3,
            granularity=Granularity.MONTHLY,
        )
        
        assert period.display_name == "Mar 2025"
    
    def test_annual_display_name(self):
        """Test annual period display name."""
        period = Period(
            year=2025,
            granularity=Granularity.ANNUAL,
        )
        
        assert period.display_name == "2025"
    
    def test_hours_in_monthly_period(self):
        """Test hours calculation for monthly period."""
        # March has 31 days
        period = Period(
            year=2025,
            month=3,
            granularity=Granularity.MONTHLY,
        )
        
        assert period.hours_in_period == 31 * 24
    
    def test_hours_in_annual_period(self):
        """Test hours calculation for annual period."""
        period = Period(
            year=2025,
            granularity=Granularity.ANNUAL,
        )
        
        assert period.hours_in_period == 8760


class TestForecast:
    """Tests for Forecast model."""
    
    def test_cost_per_mwh_calculation(self):
        """Test $/MWhr calculation."""
        forecast = Forecast(
            generation_mwh=Decimal("100000"),
            cost_dollars=Decimal("5000000"),
        )
        
        expected = Decimal("5000000") / Decimal("100000")  # $50/MWhr
        assert forecast.cost_per_mwh == expected
    
    def test_cost_per_mwh_zero_generation(self):
        """Test $/MWhr with zero generation."""
        forecast = Forecast(
            generation_mwh=Decimal("0"),
            cost_dollars=Decimal("5000000"),
        )
        
        assert forecast.cost_per_mwh is None
    
    def test_cost_per_mwh_no_cost(self):
        """Test $/MWhr with no cost."""
        forecast = Forecast(
            generation_mwh=Decimal("100000"),
            cost_dollars=None,
        )
        
        assert forecast.cost_per_mwh is None

