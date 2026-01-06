"""Sponsor report generation module.

Generates monthly Excel reports for sponsors in the format of 2025mthlybillable,
including:
- Generation (MWh)
- Fuel costs with $/MWhr
- O&M costs with $/MWhr
- Capital/depreciation
- Total power cost $/MWhr
"""

from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from calendar import month_name
import logging

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill, NamedStyle
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from src.engine.fuel_model import FuelCostSummary, calculate_annual_fuel_costs, FuelModelInputs
from src.engine.generation import create_kyger_params, create_clifty_params
from src.reports.variance_report import generate_variance_report, get_ytd_variance_summary

logger = logging.getLogger(__name__)


# Style definitions
HEADER_FONT = Font(bold=True, size=12)
SECTION_FONT = Font(bold=True, size=11)
CURRENCY_FORMAT = '"$"#,##0'
CURRENCY_DECIMAL_FORMAT = '"$"#,##0.00'
PERCENT_FORMAT = '0.0%'
NUMBER_FORMAT = '#,##0'
RATE_FORMAT = '"$"#,##0.00"/MWhr"'

HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
SECTION_FILL = PatternFill(start_color="D9E2F3", end_color="D9E2F3", fill_type="solid")
TOTAL_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")

THIN_BORDER = Border(
    left=Side(style='thin'),
    right=Side(style='thin'),
    top=Side(style='thin'),
    bottom=Side(style='thin')
)


def create_sponsor_workbook() -> Workbook:
    """Create a new workbook with styles."""
    wb = Workbook()
    return wb


def add_header_row(ws, row: int, headers: List[str]):
    """Add a header row with styling."""
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal='center')
        cell.border = THIN_BORDER


def add_section_row(ws, row: int, label: str, num_cols: int):
    """Add a section header row."""
    cell = ws.cell(row=row, column=1, value=label)
    cell.font = SECTION_FONT
    cell.fill = SECTION_FILL
    for col in range(1, num_cols + 1):
        ws.cell(row=row, column=col).fill = SECTION_FILL
        ws.cell(row=row, column=col).border = THIN_BORDER


def add_data_row(
    ws,
    row: int,
    label: str,
    values: List,
    format_type: str = "currency",
    is_total: bool = False,
):
    """Add a data row with values.
    
    Args:
        ws: Worksheet
        row: Row number
        label: Row label
        values: List of values (one per column)
        format_type: currency, number, percent, rate
        is_total: Whether this is a total row
    """
    cell = ws.cell(row=row, column=1, value=label)
    if is_total:
        cell.font = Font(bold=True)
        cell.fill = TOTAL_FILL
    cell.border = THIN_BORDER
    
    for col, value in enumerate(values, start=2):
        cell = ws.cell(row=row, column=col, value=value if value else 0)
        cell.border = THIN_BORDER
        cell.alignment = Alignment(horizontal='right')
        
        if is_total:
            cell.fill = TOTAL_FILL
            cell.font = Font(bold=True)
        
        if format_type == "currency":
            cell.number_format = CURRENCY_FORMAT
        elif format_type == "currency_decimal":
            cell.number_format = CURRENCY_DECIMAL_FORMAT
        elif format_type == "number":
            cell.number_format = NUMBER_FORMAT
        elif format_type == "percent":
            cell.number_format = PERCENT_FORMAT
        elif format_type == "rate":
            cell.number_format = RATE_FORMAT


def generate_monthly_summary_sheet(
    ws,
    year: int,
    fuel_costs: List[FuelCostSummary],
    expense_variance: Dict,
):
    """Generate monthly summary sheet.
    
    Args:
        ws: Worksheet
        year: Year
        fuel_costs: List of monthly fuel cost summaries
        expense_variance: Expense variance data
    """
    ws.title = "Monthly Summary"
    
    # Headers
    headers = ["Category"] + [month_name[m][:3] for m in range(1, 13)] + ["Total", "$/MWhr"]
    add_header_row(ws, 1, headers)
    
    current_row = 2
    
    # Generation section
    add_section_row(ws, current_row, "GENERATION", len(headers))
    current_row += 1
    
    mwh_values = [float(fc.net_delivered_mwh) for fc in fuel_costs]
    total_mwh = sum(mwh_values)
    add_data_row(ws, current_row, "Delivered MWh", mwh_values + [total_mwh, ""], "number", is_total=True)
    current_row += 1
    
    cap_factors = [float(fc.capacity_factor * 100) for fc in fuel_costs]
    avg_cap_factor = sum(cap_factors) / len(cap_factors) if cap_factors else 0
    add_data_row(ws, current_row, "Capacity Factor %", cap_factors + [avg_cap_factor, ""], "number")
    current_row += 2
    
    # Fuel costs section
    add_section_row(ws, current_row, "FUEL COSTS", len(headers))
    current_row += 1
    
    # Coal
    coal_values = [float(fc.coal_cost) for fc in fuel_costs]
    total_coal = sum(coal_values)
    coal_per_mwh = total_coal / total_mwh if total_mwh > 0 else 0
    add_data_row(ws, current_row, "Coal Cost", coal_values + [total_coal, coal_per_mwh], "currency")
    current_row += 1
    
    # Consumables
    consumable_values = [float(fc.consumables_cost) for fc in fuel_costs]
    total_consumables = sum(consumable_values)
    consumables_per_mwh = total_consumables / total_mwh if total_mwh > 0 else 0
    add_data_row(ws, current_row, "Reagent Costs", consumable_values + [total_consumables, consumables_per_mwh], "currency")
    current_row += 1
    
    # Byproducts (negative = revenue)
    byproduct_values = [float(fc.byproduct_net_cost) for fc in fuel_costs]
    total_byproducts = sum(byproduct_values)
    byproducts_per_mwh = total_byproducts / total_mwh if total_mwh > 0 else 0
    add_data_row(ws, current_row, "Byproducts (Net)", byproduct_values + [total_byproducts, byproducts_per_mwh], "currency")
    current_row += 1
    
    # Total fuel
    fuel_values = [float(fc.total_fuel_cost) for fc in fuel_costs]
    total_fuel = sum(fuel_values)
    fuel_per_mwh = total_fuel / total_mwh if total_mwh > 0 else 0
    add_data_row(ws, current_row, "Total Fuel Cost", fuel_values + [total_fuel, fuel_per_mwh], "currency", is_total=True)
    current_row += 2
    
    # O&M section (placeholder - would come from variance report)
    add_section_row(ws, current_row, "OPERATING COSTS", len(headers))
    current_row += 1
    
    # Placeholder O&M values
    om_values = [0] * 12
    add_data_row(ws, current_row, "Maintenance", om_values + [0, 0], "currency")
    current_row += 1
    add_data_row(ws, current_row, "Operations", om_values + [0, 0], "currency")
    current_row += 1
    add_data_row(ws, current_row, "Environmental", om_values + [0, 0], "currency")
    current_row += 1
    add_data_row(ws, current_row, "Total O&M", om_values + [0, 0], "currency", is_total=True)
    current_row += 2
    
    # Total power cost
    add_section_row(ws, current_row, "TOTAL POWER COST", len(headers))
    current_row += 1
    add_data_row(ws, current_row, "Total Power Cost", fuel_values + [total_fuel, fuel_per_mwh], "currency", is_total=True)
    current_row += 1
    add_data_row(ws, current_row, "Power Cost $/MWhr", 
                 [float(fc.fuel_cost_per_mwh) for fc in fuel_costs] + [fuel_per_mwh, ""], 
                 "currency_decimal", is_total=True)
    
    # Set column widths
    ws.column_dimensions['A'].width = 25
    for col in range(2, 16):
        ws.column_dimensions[get_column_letter(col)].width = 12


def generate_fuel_detail_sheet(
    ws,
    year: int,
    fuel_costs: List[FuelCostSummary],
):
    """Generate fuel cost detail sheet."""
    ws.title = "Fuel Detail"
    
    headers = ["Metric"] + [month_name[m][:3] for m in range(1, 13)] + ["Total/Avg"]
    add_header_row(ws, 1, headers)
    
    current_row = 2
    
    # Coal consumption
    add_section_row(ws, current_row, "COAL CONSUMPTION", len(headers))
    current_row += 1
    
    tons_values = [float(fc.coal_tons_consumed) for fc in fuel_costs]
    add_data_row(ws, current_row, "Tons Consumed", tons_values + [sum(tons_values)], "number")
    current_row += 1
    
    mmbtu_values = [float(fc.coal_mmbtu_consumed) for fc in fuel_costs]
    add_data_row(ws, current_row, "MMBtu Consumed", mmbtu_values + [sum(mmbtu_values)], "number")
    current_row += 1
    
    hr_values = [float(fc.heat_rate) for fc in fuel_costs]
    add_data_row(ws, current_row, "Heat Rate (BTU/kWh)", hr_values + [sum(hr_values)/12], "number")
    current_row += 2
    
    # Coal costs
    add_section_row(ws, current_row, "COAL COSTS", len(headers))
    current_row += 1
    
    coal_values = [float(fc.coal_cost) for fc in fuel_costs]
    add_data_row(ws, current_row, "Coal Cost ($)", coal_values + [sum(coal_values)], "currency")
    current_row += 1
    
    cost_per_ton = [float(fc.coal_cost_per_ton) for fc in fuel_costs]
    add_data_row(ws, current_row, "Cost per Ton", cost_per_ton + [sum(cost_per_ton)/12], "currency_decimal")
    current_row += 1
    
    cost_per_mmbtu = [float(fc.coal_cost_per_mmbtu) for fc in fuel_costs]
    add_data_row(ws, current_row, "Cost per MMBtu", cost_per_mmbtu + [sum(cost_per_mmbtu)/12], "currency_decimal")
    current_row += 2
    
    # Consumables
    add_section_row(ws, current_row, "CONSUMABLES", len(headers))
    current_row += 1
    
    urea_values = [float(fc.urea_cost) for fc in fuel_costs]
    add_data_row(ws, current_row, "Urea", urea_values + [sum(urea_values)], "currency")
    current_row += 1
    
    limestone_values = [float(fc.limestone_cost) for fc in fuel_costs]
    add_data_row(ws, current_row, "Limestone", limestone_values + [sum(limestone_values)], "currency")
    current_row += 1
    
    other_values = [float(fc.other_reagent_cost) for fc in fuel_costs]
    add_data_row(ws, current_row, "Other Reagents", other_values + [sum(other_values)], "currency")
    current_row += 1
    
    total_consumables = [float(fc.consumables_cost) for fc in fuel_costs]
    add_data_row(ws, current_row, "Total Consumables", total_consumables + [sum(total_consumables)], "currency", is_total=True)
    current_row += 2
    
    # Byproducts
    add_section_row(ws, current_row, "BYPRODUCTS", len(headers))
    current_row += 1
    
    ash_values = [float(fc.ash_net_cost) for fc in fuel_costs]
    add_data_row(ws, current_row, "Ash (Net)", ash_values + [sum(ash_values)], "currency")
    current_row += 1
    
    gypsum_values = [float(fc.gypsum_net_cost) for fc in fuel_costs]
    add_data_row(ws, current_row, "Gypsum (Net)", gypsum_values + [sum(gypsum_values)], "currency")
    current_row += 1
    
    byproduct_total = [float(fc.byproduct_net_cost) for fc in fuel_costs]
    add_data_row(ws, current_row, "Total Byproducts", byproduct_total + [sum(byproduct_total)], "currency", is_total=True)
    
    # Set column widths
    ws.column_dimensions['A'].width = 25
    for col in range(2, 15):
        ws.column_dimensions[get_column_letter(col)].width = 12


def generate_sponsor_report(
    db: Session,
    year: int,
    output_path: Path,
    plant_id: int = None,
) -> Path:
    """Generate complete sponsor report workbook.
    
    Args:
        db: Database session
        year: Year for report
        output_path: Path to save the Excel file
        plant_id: Optional plant ID (None = system total)
        
    Returns:
        Path to generated file
    """
    logger.info(f"Generating sponsor report for {year}")
    
    # Create workbook
    wb = create_sponsor_workbook()
    
    # Calculate fuel costs
    if plant_id == 1:
        inputs = FuelModelInputs(plant_params=create_kyger_params())
        fuel_costs = calculate_annual_fuel_costs(db, 1, year, inputs)
        plant_name = "Kyger Creek"
    elif plant_id == 2:
        inputs = FuelModelInputs(plant_params=create_clifty_params())
        fuel_costs = calculate_annual_fuel_costs(db, 2, year, inputs)
        plant_name = "Clifty Creek"
    else:
        # System - combine both plants
        kyger_inputs = FuelModelInputs(plant_params=create_kyger_params())
        clifty_inputs = FuelModelInputs(plant_params=create_clifty_params())
        kyger_costs = calculate_annual_fuel_costs(db, 1, year, kyger_inputs)
        clifty_costs = calculate_annual_fuel_costs(db, 2, year, clifty_inputs)
        
        # Combine costs
        fuel_costs = []
        for k, c in zip(kyger_costs, clifty_costs):
            combined = FuelCostSummary(
                period_year=k.period_year,
                period_month=k.period_month,
                plant_name="System",
                net_delivered_mwh=k.net_delivered_mwh + c.net_delivered_mwh,
                capacity_factor=(k.capacity_factor + c.capacity_factor) / 2,
                coal_tons_consumed=k.coal_tons_consumed + c.coal_tons_consumed,
                coal_mmbtu_consumed=k.coal_mmbtu_consumed + c.coal_mmbtu_consumed,
                heat_rate=(k.heat_rate + c.heat_rate) / 2,
                coal_cost=k.coal_cost + c.coal_cost,
                coal_cost_per_ton=(k.coal_cost_per_ton + c.coal_cost_per_ton) / 2,
                coal_cost_per_mmbtu=(k.coal_cost_per_mmbtu + c.coal_cost_per_mmbtu) / 2,
                consumables_cost=k.consumables_cost + c.consumables_cost,
                urea_cost=k.urea_cost + c.urea_cost,
                limestone_cost=k.limestone_cost + c.limestone_cost,
                other_reagent_cost=k.other_reagent_cost + c.other_reagent_cost,
                byproduct_net_cost=k.byproduct_net_cost + c.byproduct_net_cost,
                ash_net_cost=k.ash_net_cost + c.ash_net_cost,
                gypsum_net_cost=k.gypsum_net_cost + c.gypsum_net_cost,
                total_fuel_cost=k.total_fuel_cost + c.total_fuel_cost,
            )
            total_mwh = combined.net_delivered_mwh
            if total_mwh > 0:
                combined.fuel_cost_per_mwh = combined.total_fuel_cost / total_mwh
            fuel_costs.append(combined)
        plant_name = "System"
    
    # Get variance data
    expense_variance = get_ytd_variance_summary(db, year, 12, plant_id)
    
    # Generate sheets
    ws_summary = wb.active
    generate_monthly_summary_sheet(ws_summary, year, fuel_costs, expense_variance)
    
    ws_detail = wb.create_sheet()
    generate_fuel_detail_sheet(ws_detail, year, fuel_costs)
    
    # Add title sheet
    ws_title = wb.create_sheet("Cover", 0)
    ws_title["A1"] = f"OVEC Power Cost Report"
    ws_title["A1"].font = Font(bold=True, size=16)
    ws_title["A3"] = f"Plant: {plant_name}"
    ws_title["A4"] = f"Year: {year}"
    ws_title["A5"] = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    ws_title.column_dimensions['A'].width = 40
    
    # Save workbook
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    
    logger.info(f"Sponsor report saved to {output_path}")
    return output_path


def generate_all_sponsor_reports(
    db: Session,
    year: int,
    output_dir: Path,
) -> List[Path]:
    """Generate sponsor reports for all plants and system.
    
    Args:
        db: Database session
        year: Year for reports
        output_dir: Directory to save reports
        
    Returns:
        List of generated file paths
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    reports = []
    
    # System report
    system_path = output_dir / f"OVEC_Power_Cost_{year}_System.xlsx"
    reports.append(generate_sponsor_report(db, year, system_path))
    
    # Kyger report
    kyger_path = output_dir / f"OVEC_Power_Cost_{year}_Kyger.xlsx"
    reports.append(generate_sponsor_report(db, year, kyger_path, plant_id=1))
    
    # Clifty report
    clifty_path = output_dir / f"OVEC_Power_Cost_{year}_Clifty.xlsx"
    reports.append(generate_sponsor_report(db, year, clifty_path, plant_id=2))
    
    return reports

