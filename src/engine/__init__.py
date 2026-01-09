# Forecast calculation engine

from src.engine.depreciation import (
    DepreciationScheduleRow,
    generate_depreciation_schedule,
    calculate_total_depreciation_by_period,
    import_depreciation_to_forecast,
    project_future_depreciation,
    generate_cash_flow_comparison,
)

__all__ = [
    # Depreciation
    "DepreciationScheduleRow",
    "generate_depreciation_schedule",
    "calculate_total_depreciation_by_period",
    "import_depreciation_to_forecast",
    "project_future_depreciation",
    "generate_cash_flow_comparison",
]
