"""Coal burn calculation module.

Calculates coal consumption based on:
- MWh generation
- Heat rate (BTU/kWh)
- Coal BTU content
- PRB blend percentage
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Dict, Optional
import logging

from src.engine.generation import GenerationResult

logger = logging.getLogger(__name__)


# Constants
BTU_PER_LB = Decimal("1000000")  # 1 MMBtu = 1,000,000 BTU
LBS_PER_TON = Decimal("2000")


@dataclass
class CoalQuality:
    """Coal quality parameters."""
    name: str
    btu_per_lb: Decimal = Decimal("12000")  # BTU/lb
    so2_lb_per_mmbtu: Decimal = Decimal("5.0")  # lb SO2 per MMBtu
    ash_pct: Decimal = Decimal("0.09")  # Ash content percentage
    moisture_pct: Decimal = Decimal("0.05")  # Moisture content
    
    @property
    def btu_per_ton(self) -> Decimal:
        """BTU per ton of coal."""
        return self.btu_per_lb * LBS_PER_TON
    
    @property
    def mmbtu_per_ton(self) -> Decimal:
        """MMBtu per ton of coal."""
        return self.btu_per_ton / BTU_PER_LB


@dataclass
class HeatRateParams:
    """Heat rate parameters for a unit or plant.
    
    Supports heat rate curve calculation based on load level:
    - At full load (100%): uses baseline_heat_rate
    - At min load (typically 40%): uses min_load_heat_rate
    - At intermediate loads: linear interpolation
    """
    baseline_heat_rate: Decimal = Decimal("9850")  # BTU/kWh at full load
    min_load_heat_rate: Decimal = Decimal("10500")  # BTU/kWh at min load
    min_load_level: Decimal = Decimal("0.40")  # Min load as fraction of capacity
    suf_correction: Decimal = Decimal("0")  # SUF (Startup/Fuel) correction
    prb_blend_pct: Decimal = Decimal("0")  # PRB coal blend percentage
    prb_heat_rate_penalty: Decimal = Decimal("100")  # Additional BTU/kWh per % PRB
    
    @property
    def effective_heat_rate(self) -> Decimal:
        """Calculate effective heat rate at full load with corrections."""
        base = self.baseline_heat_rate + self.suf_correction
        prb_penalty = self.prb_blend_pct * self.prb_heat_rate_penalty
        return base + prb_penalty
    
    def heat_rate_at_load(self, capacity_factor: Decimal) -> Decimal:
        """Calculate heat rate at a given capacity factor (load level).
        
        Uses linear interpolation between min load and full load heat rates.
        
        Args:
            capacity_factor: Operating capacity factor (0-1)
            
        Returns:
            Interpolated heat rate in BTU/kWh
        """
        # Clamp capacity factor
        if capacity_factor <= self.min_load_level:
            # At or below min load, use min load heat rate
            base = self.min_load_heat_rate
        elif capacity_factor >= Decimal("1.0"):
            # At or above full load, use baseline
            base = self.baseline_heat_rate
        else:
            # Linear interpolation between min load and full load
            load_range = Decimal("1.0") - self.min_load_level
            load_position = (capacity_factor - self.min_load_level) / load_range
            # Higher load = lower heat rate (better efficiency)
            heat_rate_range = self.min_load_heat_rate - self.baseline_heat_rate
            base = self.min_load_heat_rate - (heat_rate_range * load_position)
        
        # Apply corrections
        base = base + self.suf_correction
        prb_penalty = self.prb_blend_pct * self.prb_heat_rate_penalty
        
        return base + prb_penalty


def calculate_effective_heat_rate(
    baseline: Decimal,
    min_load_rate: Decimal,
    capacity_factor: Decimal,
    suf_correction: Decimal = Decimal("0"),
    prb_adjustment: Decimal = Decimal("0"),
    min_load_level: Decimal = Decimal("0.40"),
) -> Decimal:
    """Calculate heat rate based on operating conditions.
    
    This is a standalone function for calculating effective heat rate
    with load-based curve interpolation.
    
    Args:
        baseline: Baseline heat rate at full load (BTU/kWh)
        min_load_rate: Heat rate at minimum load (BTU/kWh)
        capacity_factor: Operating capacity factor (0-1)
        suf_correction: Startup/shutdown correction (BTU/kWh)
        prb_adjustment: PRB blend adjustment (BTU/kWh)
        min_load_level: Minimum load level as fraction (default 0.40)
        
    Returns:
        Effective heat rate in BTU/kWh
    """
    params = HeatRateParams(
        baseline_heat_rate=baseline,
        min_load_heat_rate=min_load_rate,
        min_load_level=min_load_level,
        suf_correction=suf_correction,
        prb_blend_pct=Decimal("0"),  # prb_adjustment is already in BTU/kWh
    )
    
    base_rate = params.heat_rate_at_load(capacity_factor)
    return base_rate + prb_adjustment


def build_heat_rate_params_from_db(db, plant_id: int, year: int, month: int, unit_number: int = None):
    """Build HeatRateParams from database values.
    
    Args:
        db: Database session
        plant_id: Plant ID (1=Kyger, 2=Clifty)
        year: Year
        month: Month
        unit_number: Optional unit number for unit-level override
        
    Returns:
        HeatRateParams populated from database or defaults
    """
    from src.models.heat_rate import get_heat_rate_for_month
    
    hr_data = get_heat_rate_for_month(db, plant_id, year, month, unit_number)
    
    return HeatRateParams(
        baseline_heat_rate=hr_data["baseline_heat_rate"],
        min_load_heat_rate=hr_data["min_load_heat_rate"] or Decimal("10500"),
        suf_correction=hr_data["suf_correction"],
        prb_blend_pct=Decimal("0"),  # PRB handled separately
    )


@dataclass
class CoalBurnResult:
    """Result of coal burn calculation."""
    period_year: int
    period_month: int
    plant_name: str
    
    # Generation input
    net_mwh: Decimal = Decimal("0")
    
    # Heat rate
    heat_rate_btu_kwh: Decimal = Decimal("0")
    
    # Energy consumed
    mmbtu_consumed: Decimal = Decimal("0")
    
    # Coal consumed
    coal_quality_btu_lb: Decimal = Decimal("0")
    tons_consumed: Decimal = Decimal("0")
    
    # Emissions basis
    so2_lbs_produced: Decimal = Decimal("0")
    ash_tons_produced: Decimal = Decimal("0")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "period": f"{self.period_year}-{self.period_month:02d}",
            "plant": self.plant_name,
            "net_mwh": float(self.net_mwh),
            "heat_rate_btu_kwh": float(self.heat_rate_btu_kwh),
            "mmbtu_consumed": float(self.mmbtu_consumed),
            "coal_quality_btu_lb": float(self.coal_quality_btu_lb),
            "tons_consumed": float(self.tons_consumed),
            "so2_lbs_produced": float(self.so2_lbs_produced),
            "ash_tons_produced": float(self.ash_tons_produced),
        }


def create_napp_coal() -> CoalQuality:
    """Create Northern Appalachian coal quality."""
    return CoalQuality(
        name="Northern Appalachian",
        btu_per_lb=Decimal("12600"),
        so2_lb_per_mmbtu=Decimal("5.2"),
        ash_pct=Decimal("0.093"),
        moisture_pct=Decimal("0.05"),
    )


def create_ilb_coal() -> CoalQuality:
    """Create Illinois Basin coal quality."""
    return CoalQuality(
        name="Illinois Basin",
        btu_per_lb=Decimal("11400"),
        so2_lb_per_mmbtu=Decimal("4.5"),
        ash_pct=Decimal("0.095"),
        moisture_pct=Decimal("0.12"),
    )


def create_prb_coal() -> CoalQuality:
    """Create Powder River Basin coal quality."""
    return CoalQuality(
        name="PRB",
        btu_per_lb=Decimal("8800"),
        so2_lb_per_mmbtu=Decimal("0.8"),
        ash_pct=Decimal("0.05"),
        moisture_pct=Decimal("0.28"),
    )


def blend_coal_quality(
    coals: List[CoalQuality],
    percentages: List[Decimal],
) -> CoalQuality:
    """Blend multiple coal qualities by percentage.
    
    Args:
        coals: List of coal quality objects
        percentages: List of blend percentages (should sum to 1.0)
        
    Returns:
        Blended coal quality
    """
    if len(coals) != len(percentages):
        raise ValueError("Coals and percentages must have same length")
    
    total_pct = sum(percentages)
    if abs(total_pct - Decimal("1.0")) > Decimal("0.001"):
        logger.warning(f"Blend percentages sum to {total_pct}, normalizing")
        percentages = [p / total_pct for p in percentages]
    
    blended = CoalQuality(name="Blend")
    blended.btu_per_lb = sum(c.btu_per_lb * p for c, p in zip(coals, percentages))
    blended.so2_lb_per_mmbtu = sum(c.so2_lb_per_mmbtu * p for c, p in zip(coals, percentages))
    blended.ash_pct = sum(c.ash_pct * p for c, p in zip(coals, percentages))
    blended.moisture_pct = sum(c.moisture_pct * p for c, p in zip(coals, percentages))
    
    return blended


def calculate_coal_burn(
    generation: GenerationResult,
    heat_rate: HeatRateParams,
    coal: CoalQuality,
) -> CoalBurnResult:
    """Calculate coal consumption for a generation period.
    
    Args:
        generation: Generation result with MWh
        heat_rate: Heat rate parameters
        coal: Coal quality parameters
        
    Returns:
        CoalBurnResult with consumption calculations
    """
    result = CoalBurnResult(
        period_year=generation.period_year,
        period_month=generation.period_month,
        plant_name=generation.plant_name,
        net_mwh=generation.net_delivered_mwh,
        heat_rate_btu_kwh=heat_rate.effective_heat_rate,
        coal_quality_btu_lb=coal.btu_per_lb,
    )
    
    # Calculate MMBtu consumed
    # MWh * 1000 kWh/MWh * BTU/kWh / 1,000,000 BTU/MMBtu = MMBtu
    result.mmbtu_consumed = (
        result.net_mwh * Decimal("1000") * result.heat_rate_btu_kwh / BTU_PER_LB
    )
    
    # Calculate tons consumed
    # MMBtu / (BTU/lb / 1,000,000) / 2000 lb/ton = tons
    if coal.mmbtu_per_ton > 0:
        result.tons_consumed = result.mmbtu_consumed / coal.mmbtu_per_ton
    
    # Calculate SO2 produced (before FGD removal)
    result.so2_lbs_produced = result.mmbtu_consumed * coal.so2_lb_per_mmbtu
    
    # Calculate ash produced
    result.ash_tons_produced = result.tons_consumed * coal.ash_pct
    
    return result


def calculate_annual_coal_burn(
    generation_results: List[GenerationResult],
    heat_rate: HeatRateParams,
    coal: CoalQuality,
) -> List[CoalBurnResult]:
    """Calculate coal burn for a full year.
    
    Args:
        generation_results: List of monthly generation results
        heat_rate: Heat rate parameters
        coal: Coal quality
        
    Returns:
        List of monthly coal burn results
    """
    return [
        calculate_coal_burn(gen, heat_rate, coal)
        for gen in generation_results
    ]


def summarize_annual_coal_burn(results: List[CoalBurnResult]) -> Dict:
    """Summarize annual coal consumption.
    
    Args:
        results: List of monthly CoalBurnResult
        
    Returns:
        Dictionary with annual totals
    """
    if not results:
        return {}
    
    total_mwh = sum(r.net_mwh for r in results)
    total_mmbtu = sum(r.mmbtu_consumed for r in results)
    total_tons = sum(r.tons_consumed for r in results)
    
    # Calculate weighted average heat rate
    if total_mwh > 0:
        avg_heat_rate = (total_mmbtu * BTU_PER_LB) / (total_mwh * Decimal("1000"))
    else:
        avg_heat_rate = Decimal("0")
    
    return {
        "plant": results[0].plant_name,
        "year": results[0].period_year,
        "total_mwh": float(total_mwh),
        "total_mmbtu": float(total_mmbtu),
        "total_tons_consumed": float(total_tons),
        "avg_heat_rate_btu_kwh": float(avg_heat_rate),
        "total_so2_lbs": float(sum(r.so2_lbs_produced for r in results)),
        "total_ash_tons": float(sum(r.ash_tons_produced for r in results)),
        "monthly_avg_tons": float(total_tons / Decimal("12")),
    }


@dataclass
class UnitHeatRate:
    """Heat rate for a specific unit."""
    unit_number: int
    baseline: Decimal = Decimal("9850")
    suf_correction: Decimal = Decimal("0")
    prb_blend_pct: Decimal = Decimal("0")
    
    def effective_rate(self) -> Decimal:
        """Calculate effective heat rate."""
        return self.baseline + self.suf_correction


def calculate_plant_coal_burn_by_unit(
    plant_name: str,
    year: int,
    month: int,
    unit_mwh: Dict[int, Decimal],
    unit_heat_rates: Dict[int, UnitHeatRate],
    coal: CoalQuality,
) -> Dict:
    """Calculate coal burn with unit-level detail.
    
    Args:
        plant_name: Plant name
        year: Year
        month: Month
        unit_mwh: Dict of unit number -> MWh generated
        unit_heat_rates: Dict of unit number -> heat rate params
        coal: Coal quality
        
    Returns:
        Dictionary with per-unit and total coal burn
    """
    unit_results = {}
    total_mwh = Decimal("0")
    total_mmbtu = Decimal("0")
    total_tons = Decimal("0")
    
    for unit_num, mwh in unit_mwh.items():
        hr = unit_heat_rates.get(unit_num, UnitHeatRate(unit_number=unit_num))
        
        # Calculate MMBtu for this unit
        mmbtu = mwh * Decimal("1000") * hr.effective_rate() / BTU_PER_LB
        
        # Calculate tons for this unit
        tons = mmbtu / coal.mmbtu_per_ton if coal.mmbtu_per_ton > 0 else Decimal("0")
        
        unit_results[unit_num] = {
            "mwh": float(mwh),
            "heat_rate": float(hr.effective_rate()),
            "mmbtu": float(mmbtu),
            "tons": float(tons),
        }
        
        total_mwh += mwh
        total_mmbtu += mmbtu
        total_tons += tons
    
    return {
        "plant": plant_name,
        "period": f"{year}-{month:02d}",
        "units": unit_results,
        "total_mwh": float(total_mwh),
        "total_mmbtu": float(total_mmbtu),
        "total_tons": float(total_tons),
        "coal_quality_btu_lb": float(coal.btu_per_lb),
    }

