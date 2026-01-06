"""Generation calculation module.

Calculates MWh generation based on:
- Unit capacity (MW)
- Hours in period
- Availability/capacity factor
- FGD auxiliary load
- Use factor (lack of sales)
- GSU transformer losses
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Dict, Optional
from calendar import monthrange
import logging

logger = logging.getLogger(__name__)

# Ozone season months (May through September) - Unit 6 curtailed during this period
OZONE_SEASON_MONTHS = {5, 6, 7, 8, 9}


def is_ozone_season(month: int) -> bool:
    """Check if a month is in ozone season."""
    return month in OZONE_SEASON_MONTHS


@dataclass
class UseFactorParams:
    """Use factor configuration matching Excel 'Use Factor Input' sheet.
    
    This supports the two-tier approach:
    - Base use factor: Applied to all units normally
    - Ozone use factor for non-SCR: Applied to units without SCR during ozone season
    
    The Excel model has separate rows:
    - "Use factor without NOx Allowance" (rows 3-4): For normal operations
    - "Use factor with NOx Allowance" (rows 9-10): For Unit 6 during ozone season
    """
    # Base use factor for all units during non-ozone or SCR-equipped units always
    base_use_factor: Decimal = Decimal("0.85")
    
    # Use factor for non-SCR units during ozone season (typically 0 = offline)
    ozone_use_factor_non_scr: Decimal = Decimal("0")
    
    # Monthly overrides: Dict of (month, unit_number) -> use_factor
    # This allows for specific unit/month combinations from Excel inputs
    monthly_unit_overrides: Dict = field(default_factory=dict)
    
    def get_use_factor(self, unit_number: int, month: int, has_scr: bool) -> Decimal:
        """Get the use factor for a specific unit and month.
        
        Priority:
        1. Monthly unit override (if specified)
        2. Ozone season non-SCR factor (if applicable)
        3. Base use factor
        """
        # Check for specific override
        override_key = (month, unit_number)
        if override_key in self.monthly_unit_overrides:
            return self.monthly_unit_overrides[override_key]
        
        # Apply ozone season logic for non-SCR units
        if not has_scr and is_ozone_season(month):
            return self.ozone_use_factor_non_scr
        
        return self.base_use_factor


@dataclass
class UnitParams:
    """Parameters for a generating unit."""
    unit_number: int
    capacity_mw: Decimal = Decimal("205")  # Net MW capacity
    min_load_mw: Decimal = Decimal("80")   # Minimum load MW
    is_available: bool = True
    availability_factor: Decimal = Decimal("1.0")  # 0-1
    
    # SCR configuration for NOx control
    has_scr: bool = True  # Default True (most units have SCR)
    nox_lb_per_mmbtu_uncontrolled: Decimal = Decimal("0.60")  # Uncontrolled NOx emission rate
    scr_removal_efficiency: Decimal = Decimal("0.90")  # 90% removal when SCR equipped
    
    def available_capacity(self) -> Decimal:
        """Calculate available capacity considering availability."""
        if not self.is_available:
            return Decimal("0")
        return self.capacity_mw * self.availability_factor
    
    def effective_nox_lb_per_mmbtu(self) -> Decimal:
        """Get effective NOx emission rate considering SCR status."""
        if self.has_scr:
            return self.nox_lb_per_mmbtu_uncontrolled * (Decimal("1") - self.scr_removal_efficiency)
        return self.nox_lb_per_mmbtu_uncontrolled


@dataclass
class PlantParams:
    """Parameters for a plant."""
    plant_name: str
    units: List[UnitParams] = field(default_factory=list)
    fgd_aux_load_mw: Decimal = Decimal("25")  # FGD auxiliary load
    bioreactor_aux_load_mw: Decimal = Decimal("6")  # Bioreactor load
    gsu_loss_pct: Decimal = Decimal("0.005545")  # GSU transformer losses
    reserve_mw: Decimal = Decimal("10")  # System regulating reserve
    
    @property
    def total_capacity_mw(self) -> Decimal:
        """Total plant capacity."""
        return sum(u.capacity_mw for u in self.units)
    
    @property
    def available_capacity_mw(self) -> Decimal:
        """Total available capacity."""
        return sum(u.available_capacity() for u in self.units)
    
    def get_scr_units(self) -> List[UnitParams]:
        """Get list of units with SCR installed."""
        return [u for u in self.units if u.has_scr]
    
    def get_non_scr_units(self) -> List[UnitParams]:
        """Get list of units without SCR."""
        return [u for u in self.units if not u.has_scr]


@dataclass
class UnitGenerationResult:
    """Result of generation calculation for a single unit."""
    unit_number: int
    has_scr: bool
    
    # Generation values
    capacity_mw: Decimal = Decimal("0")
    gross_mwh: Decimal = Decimal("0")
    net_mwh: Decimal = Decimal("0")
    
    # Use factor for this unit
    use_factor: Decimal = Decimal("1.0")
    
    # Curtailment status (True during ozone if no SCR)
    is_curtailed: bool = False
    
    # Coal burn allocation (for emissions)
    mmbtu_consumed: Decimal = Decimal("0")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "unit_number": self.unit_number,
            "has_scr": self.has_scr,
            "capacity_mw": float(self.capacity_mw),
            "gross_mwh": float(self.gross_mwh),
            "net_mwh": float(self.net_mwh),
            "use_factor": float(self.use_factor),
            "is_curtailed": self.is_curtailed,
            "mmbtu_consumed": float(self.mmbtu_consumed),
        }


@dataclass
class GenerationResult:
    """Result of generation calculation."""
    period_year: int
    period_month: int
    plant_name: str
    
    # Gross generation
    hours_in_period: int = 0
    gross_mwh_available: Decimal = Decimal("0")
    
    # Deductions
    fgd_aux_mwh: Decimal = Decimal("0")
    bioreactor_aux_mwh: Decimal = Decimal("0")
    gsu_loss_mwh: Decimal = Decimal("0")
    reserve_mwh: Decimal = Decimal("0")
    lack_of_sales_mwh: Decimal = Decimal("0")
    
    # Net generation
    net_mwh_available: Decimal = Decimal("0")
    net_delivered_mwh: Decimal = Decimal("0")
    
    # Factors
    capacity_factor: Decimal = Decimal("0")
    use_factor: Decimal = Decimal("1.0")
    
    # Unit-level breakdown
    unit_results: List[UnitGenerationResult] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "period": f"{self.period_year}-{self.period_month:02d}",
            "plant": self.plant_name,
            "hours_in_period": self.hours_in_period,
            "gross_mwh_available": float(self.gross_mwh_available),
            "fgd_aux_mwh": float(self.fgd_aux_mwh),
            "bioreactor_aux_mwh": float(self.bioreactor_aux_mwh),
            "gsu_loss_mwh": float(self.gsu_loss_mwh),
            "reserve_mwh": float(self.reserve_mwh),
            "lack_of_sales_mwh": float(self.lack_of_sales_mwh),
            "net_mwh_available": float(self.net_mwh_available),
            "net_delivered_mwh": float(self.net_delivered_mwh),
            "capacity_factor": float(self.capacity_factor),
            "use_factor": float(self.use_factor),
            "unit_results": [u.to_dict() for u in self.unit_results],
        }
    
    def get_unit_result(self, unit_number: int) -> Optional[UnitGenerationResult]:
        """Get generation result for a specific unit."""
        for u in self.unit_results:
            if u.unit_number == unit_number:
                return u
        return None


def get_hours_in_month(year: int, month: int) -> int:
    """Get hours in a specific month."""
    days = monthrange(year, month)[1]
    return days * 24


def get_hours_in_year(year: int) -> int:
    """Get hours in a year (accounting for leap year)."""
    # Check if leap year
    if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
        return 8784
    return 8760


def get_unit_use_factor(
    unit: UnitParams,
    month: int,
    base_use_factor: Decimal,
    ozone_use_factor: Decimal = Decimal("0"),
) -> Decimal:
    """Get use factor for a unit, considering ozone season restrictions.
    
    During ozone season (May-Sep), units without SCR (like Clifty Unit 6)
    must be curtailed or operate at reduced capacity due to NOx limits.
    
    Args:
        unit: Unit parameters
        month: Month (1-12)
        base_use_factor: Normal use factor for the unit
        ozone_use_factor: Use factor during ozone season for non-SCR units
                         (default 0 = unit offline)
        
    Returns:
        Effective use factor for the unit
    """
    if not unit.has_scr and is_ozone_season(month):
        return ozone_use_factor  # Unit curtailed/off during ozone season
    return base_use_factor


def get_unit_use_factors_for_plant(
    plant: PlantParams,
    month: int,
    base_use_factor: Decimal = Decimal("0.85"),
    ozone_use_factor_non_scr: Decimal = Decimal("0"),
) -> Dict[int, Decimal]:
    """Get use factors for all units in a plant.
    
    Args:
        plant: Plant parameters
        month: Month (1-12)
        base_use_factor: Normal use factor for all units
        ozone_use_factor_non_scr: Use factor for non-SCR units during ozone season
        
    Returns:
        Dict of unit_number -> use_factor
    """
    use_factors = {}
    for unit in plant.units:
        use_factors[unit.unit_number] = get_unit_use_factor(
            unit, month, base_use_factor, ozone_use_factor_non_scr
        )
    return use_factors


def create_kyger_params() -> PlantParams:
    """Create default parameters for Kyger Creek.
    
    All Kyger Creek units have SCR (Selective Catalytic Reduction) installed.
    """
    units = [UnitParams(
        unit_number=i,
        capacity_mw=Decimal("205"),
        has_scr=True,  # All Kyger units have SCR
    ) for i in range(1, 6)]
    return PlantParams(
        plant_name="Kyger Creek",
        units=units,
        fgd_aux_load_mw=Decimal("25"),
        bioreactor_aux_load_mw=Decimal("6"),
        gsu_loss_pct=Decimal("0.005545"),
        reserve_mw=Decimal("10"),
    )


def create_clifty_params() -> PlantParams:
    """Create default parameters for Clifty Creek.
    
    Note: Unit 6 does not have an SCR (Selective Catalytic Reduction)
    and has tight NOx limits during ozone season (May-Sep).
    
    Capacity: 217 MW per unit (nameplate). Excel uses 205 MW "Net Maximum Capacity"
    but applies use factor differently (as "Lack of Sales" deduction).
    """
    units = []
    for i in range(1, 7):
        # Unit 6 does not have SCR - uncontrolled NOx emissions
        has_scr = (i != 6)
        units.append(UnitParams(
            unit_number=i,
            capacity_mw=Decimal("217"),  # Nameplate capacity
            has_scr=has_scr,
        ))
    return PlantParams(
        plant_name="Clifty Creek",
        units=units,
        fgd_aux_load_mw=Decimal("30"),
        bioreactor_aux_load_mw=Decimal("0"),
        gsu_loss_pct=Decimal("0.005545"),
        reserve_mw=Decimal("10"),
    )


def calculate_generation(
    plant: PlantParams,
    year: int,
    month: int,
    use_factor: Decimal = Decimal("1.0"),
    unit_availability: Dict[int, Decimal] = None,
    unit_use_factors: Dict[int, Decimal] = None,
) -> GenerationResult:
    """Calculate generation for a plant in a period.
    
    Args:
        plant: Plant parameters
        year: Year
        month: Month (1-12)
        use_factor: Default use factor (0-1), represents portion of available generation sold
        unit_availability: Optional dict of unit number -> availability factor
        unit_use_factors: Optional dict of unit number -> use factor (overrides default)
        
    Returns:
        GenerationResult with all calculations
    """
    result = GenerationResult(
        period_year=year,
        period_month=month,
        plant_name=plant.plant_name,
        use_factor=use_factor,
    )
    
    # Apply unit availability if provided
    if unit_availability:
        for unit in plant.units:
            if unit.unit_number in unit_availability:
                unit.availability_factor = unit_availability[unit.unit_number]
    
    # Calculate hours in period
    result.hours_in_period = get_hours_in_month(year, month)
    
    # Calculate unit-level generation
    for unit in plant.units:
        # Get unit-specific use factor or use default
        unit_uf = use_factor
        if unit_use_factors and unit.unit_number in unit_use_factors:
            unit_uf = unit_use_factors[unit.unit_number]
        
        # Calculate unit gross MWh
        unit_gross_mwh = unit.available_capacity() * result.hours_in_period
        
        # Calculate unit net MWh (apply use factor)
        unit_net_mwh = unit_gross_mwh * unit_uf
        
        # Determine if unit is curtailed (use factor = 0 during operation period)
        is_curtailed = (unit_uf == Decimal("0")) and unit.is_available
        
        unit_result = UnitGenerationResult(
            unit_number=unit.unit_number,
            has_scr=unit.has_scr,
            capacity_mw=unit.capacity_mw,
            gross_mwh=unit_gross_mwh,
            net_mwh=unit_net_mwh,
            use_factor=unit_uf,
            is_curtailed=is_curtailed,
        )
        result.unit_results.append(unit_result)
    
    # Calculate plant-level gross MWh available (before deductions)
    result.gross_mwh_available = sum(u.gross_mwh for u in result.unit_results)
    
    # Calculate FGD auxiliary load
    # FGD aux is proportional to generation
    fgd_ratio = plant.fgd_aux_load_mw / plant.total_capacity_mw if plant.total_capacity_mw else Decimal("0")
    result.fgd_aux_mwh = result.gross_mwh_available * fgd_ratio
    
    # Calculate bioreactor auxiliary load
    result.bioreactor_aux_mwh = plant.bioreactor_aux_load_mw * result.hours_in_period / Decimal("24")  # Daily MW to monthly MWh
    
    # Net MWh available (after aux loads)
    result.net_mwh_available = result.gross_mwh_available - result.fgd_aux_mwh - result.bioreactor_aux_mwh
    
    # Calculate GSU transformer losses
    result.gsu_loss_mwh = result.net_mwh_available * plant.gsu_loss_pct
    
    # Calculate reserve
    result.reserve_mwh = plant.reserve_mw * result.hours_in_period
    
    # Calculate lack of sales based on unit-level use factors
    total_net_mwh_with_uf = sum(u.net_mwh for u in result.unit_results)
    result.lack_of_sales_mwh = result.gross_mwh_available - total_net_mwh_with_uf
    
    # Net delivered MWh
    result.net_delivered_mwh = (
        total_net_mwh_with_uf
        - result.fgd_aux_mwh
        - result.bioreactor_aux_mwh
        - result.gsu_loss_mwh
        - result.reserve_mwh
    )
    
    # Calculate capacity factor
    max_possible = plant.total_capacity_mw * result.hours_in_period
    if max_possible > 0:
        result.capacity_factor = result.net_delivered_mwh / max_possible
    
    return result


def calculate_annual_generation(
    plant: PlantParams,
    year: int,
    monthly_use_factors: Dict[int, Decimal] = None,
) -> List[GenerationResult]:
    """Calculate generation for all months in a year.
    
    Args:
        plant: Plant parameters
        year: Year
        monthly_use_factors: Optional dict of month -> use factor
        
    Returns:
        List of GenerationResult for each month
    """
    results = []
    
    for month in range(1, 13):
        use_factor = Decimal("0.85")  # Default use factor
        if monthly_use_factors and month in monthly_use_factors:
            use_factor = monthly_use_factors[month]
        
        result = calculate_generation(plant, year, month, use_factor)
        results.append(result)
    
    return results


def summarize_annual_generation(results: List[GenerationResult]) -> Dict:
    """Summarize annual generation from monthly results.
    
    Args:
        results: List of monthly GenerationResult
        
    Returns:
        Dictionary with annual totals
    """
    if not results:
        return {}
    
    return {
        "plant": results[0].plant_name,
        "year": results[0].period_year,
        "total_hours": sum(r.hours_in_period for r in results),
        "gross_mwh": float(sum(r.gross_mwh_available for r in results)),
        "fgd_aux_mwh": float(sum(r.fgd_aux_mwh for r in results)),
        "bioreactor_aux_mwh": float(sum(r.bioreactor_aux_mwh for r in results)),
        "net_mwh_available": float(sum(r.net_mwh_available for r in results)),
        "gsu_loss_mwh": float(sum(r.gsu_loss_mwh for r in results)),
        "reserve_mwh": float(sum(r.reserve_mwh for r in results)),
        "lack_of_sales_mwh": float(sum(r.lack_of_sales_mwh for r in results)),
        "net_delivered_mwh": float(sum(r.net_delivered_mwh for r in results)),
        "avg_capacity_factor": float(sum(r.capacity_factor for r in results) / len(results)),
        "avg_use_factor": float(sum(r.use_factor for r in results) / len(results)),
    }


def get_system_generation(
    year: int,
    monthly_use_factors: Dict[str, Dict[int, Decimal]] = None,
) -> Dict:
    """Calculate combined system generation for both plants.
    
    Args:
        year: Year
        monthly_use_factors: Optional dict of plant name -> month -> use factor
        
    Returns:
        Dictionary with system totals
    """
    kyger = create_kyger_params()
    clifty = create_clifty_params()
    
    kyger_factors = monthly_use_factors.get("Kyger Creek", {}) if monthly_use_factors else {}
    clifty_factors = monthly_use_factors.get("Clifty Creek", {}) if monthly_use_factors else {}
    
    kyger_results = calculate_annual_generation(kyger, year, kyger_factors)
    clifty_results = calculate_annual_generation(clifty, year, clifty_factors)
    
    kyger_summary = summarize_annual_generation(kyger_results)
    clifty_summary = summarize_annual_generation(clifty_results)
    
    return {
        "year": year,
        "kyger": kyger_summary,
        "clifty": clifty_summary,
        "system": {
            "total_capacity_mw": float(kyger.total_capacity_mw + clifty.total_capacity_mw),
            "gross_mwh": kyger_summary.get("gross_mwh", 0) + clifty_summary.get("gross_mwh", 0),
            "net_delivered_mwh": kyger_summary.get("net_delivered_mwh", 0) + clifty_summary.get("net_delivered_mwh", 0),
        },
    }


# =============================================================================
# Database-Integrated Generation Calculation
# =============================================================================

def calculate_generation_with_outages(
    plant: PlantParams,
    year: int,
    month: int,
    use_factor: Decimal = Decimal("0.85"),
    unit_availability: Dict[int, Decimal] = None,
    unit_use_factors: Dict[int, Decimal] = None,
    db_session=None,
    plant_id: Optional[int] = None,
) -> GenerationResult:
    """Calculate generation with outage data from database.
    
    This is the primary entry point for calculating generation with
    database-driven outage factors. It:
    1. Loads outage data from the database if db_session and plant_id provided
    2. Converts outages to availability factors
    3. Calls the standard calculate_generation function
    
    Args:
        plant: Plant parameters
        year: Year
        month: Month (1-12)
        use_factor: Default use factor (0-1)
        unit_availability: Optional explicit availability overrides
        unit_use_factors: Optional unit-specific use factors
        db_session: Optional database session for loading outage data
        plant_id: Optional plant ID for database lookup
        
    Returns:
        GenerationResult with all calculations
    """
    # Load availability from database if session provided
    if db_session is not None and plant_id is not None:
        from src.models.unit_outage import build_unit_availability_from_db
        
        num_units = len(plant.units)
        db_availability = build_unit_availability_from_db(
            db_session, plant_id, year, month, num_units
        )
        
        # Merge with explicit overrides (explicit takes precedence)
        if unit_availability:
            db_availability.update(unit_availability)
        unit_availability = db_availability
    
    # Call standard calculation
    return calculate_generation(
        plant=plant,
        year=year,
        month=month,
        use_factor=use_factor,
        unit_availability=unit_availability,
        unit_use_factors=unit_use_factors,
    )


def calculate_annual_generation_with_outages(
    plant: PlantParams,
    year: int,
    monthly_use_factors: Dict[int, Decimal] = None,
    db_session=None,
    plant_id: Optional[int] = None,
) -> List[GenerationResult]:
    """Calculate annual generation with outage data from database.
    
    Args:
        plant: Plant parameters
        year: Year
        monthly_use_factors: Optional dict of month -> use factor
        db_session: Optional database session for loading outage data
        plant_id: Optional plant ID for database lookup
        
    Returns:
        List of GenerationResult for each month
    """
    results = []
    
    for month in range(1, 13):
        use_factor = Decimal("0.85")  # Default use factor
        if monthly_use_factors and month in monthly_use_factors:
            use_factor = monthly_use_factors[month]
        
        result = calculate_generation_with_outages(
            plant=plant,
            year=year,
            month=month,
            use_factor=use_factor,
            db_session=db_session,
            plant_id=plant_id,
        )
        results.append(result)
    
    return results


def get_plant_efor_summary(
    db_session,
    plant_id: int,
    year: int,
) -> Dict:
    """Get EFOR and availability summary for a plant/year.
    
    Returns both monthly and annual EFOR and availability metrics.
    This is useful for scenario analysis and reporting.
    """
    from src.models.unit_outage import (
        get_unit_outages_for_year,
        calculate_unit_availability,
        calculate_plant_availability,
    )
    
    # Determine number of units
    num_units = 5 if plant_id == 1 else 6  # Kyger: 5, Clifty: 6
    unit_capacities = {i: Decimal("205") for i in range(1, num_units + 1)}
    
    # Get all outages for the year
    outages = get_unit_outages_for_year(db_session, plant_id, year)
    
    # Calculate monthly metrics
    monthly_metrics = {}
    for month in range(1, 13):
        month_outages = [o for o in outages if o.month == month]
        plant_metrics = calculate_plant_availability(month_outages, year, month, unit_capacities)
        
        monthly_metrics[month] = {
            "availability": float(plant_metrics["weighted_availability"]),
            "efor": float(plant_metrics["weighted_efor"]),
            "outage_days": float(plant_metrics["total_outage_days"]),
        }
    
    # Calculate annual averages
    total_outage_days = sum(m["outage_days"] for m in monthly_metrics.values())
    avg_availability = sum(m["availability"] for m in monthly_metrics.values()) / 12
    avg_efor = sum(m["efor"] for m in monthly_metrics.values()) / 12
    
    return {
        "plant_id": plant_id,
        "year": year,
        "monthly": monthly_metrics,
        "annual": {
            "avg_availability": avg_availability,
            "avg_efor": avg_efor,
            "total_outage_days": total_outage_days,
        }
    }

