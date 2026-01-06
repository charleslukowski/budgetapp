"""GL Account parsing and mapping utilities.

Parses GL account strings like '003-1-20-401-10-350-501-110-4' into components
and maps them to internal cost categories.

GL Account Structure:
    Position 1: Company code (003)
    Position 2: Plant (1=Kyger, 2=Clifty)
    Position 3: Entity (20, 21)
    Position 4: Account type (401)
    Position 5: Cost type (10=Energy, 20=O&M)
    Position 6: Department (350=Fuel Handling, 320=Maint)
    Position 7: FERC account (501, 512, etc.)
    Position 8: Sub-account (110, 274, etc.)
    Position 9: Labor indicator (4=Non-labor, 5=Labor)
"""

from dataclasses import dataclass
from typing import Optional, Dict, List
from enum import Enum


class PlantCode(str, Enum):
    """Plant codes from GL account."""
    KYGER = "1"
    CLIFTY = "2"


class CostTypeCode(str, Enum):
    """Cost type codes from GL account."""
    ENERGY = "10"
    OM = "20"


@dataclass
class ParsedGLAccount:
    """Parsed components of a GL account string."""
    
    raw_account: str
    company_code: str
    plant_code: str
    entity_code: str
    account_type: str
    cost_type_code: str
    department_code: str
    ferc_account: str
    sub_account: str
    labor_indicator: str
    
    @property
    def is_kyger(self) -> bool:
        """True if this is a Kyger Creek account."""
        return self.plant_code == PlantCode.KYGER.value
    
    @property
    def is_clifty(self) -> bool:
        """True if this is a Clifty Creek account."""
        return self.plant_code == PlantCode.CLIFTY.value
    
    @property
    def is_energy(self) -> bool:
        """True if this is an energy/fuel account."""
        return self.cost_type_code == CostTypeCode.ENERGY.value
    
    @property
    def is_om(self) -> bool:
        """True if this is an O&M account."""
        return self.cost_type_code == CostTypeCode.OM.value
    
    @property
    def is_labor(self) -> bool:
        """True if this is a labor account."""
        return self.labor_indicator == "5"
    
    @property
    def plant_name(self) -> Optional[str]:
        """Return plant name based on code."""
        if self.is_kyger:
            return "Kyger Creek"
        elif self.is_clifty:
            return "Clifty Creek"
        return None


def parse_gl_account(account_string: str) -> Optional[ParsedGLAccount]:
    """Parse a GL account string into its components.
    
    Args:
        account_string: GL account like '003-1-20-401-10-350-501-110-4'
        
    Returns:
        ParsedGLAccount with all components, or None if parsing fails
    """
    if not account_string:
        return None
    
    # Clean the account string
    account_string = account_string.strip()
    
    # Split by hyphen
    parts = account_string.split("-")
    
    if len(parts) < 9:
        # Try to handle incomplete accounts
        while len(parts) < 9:
            parts.append("")
    
    return ParsedGLAccount(
        raw_account=account_string,
        company_code=parts[0],
        plant_code=parts[1],
        entity_code=parts[2],
        account_type=parts[3],
        cost_type_code=parts[4],
        department_code=parts[5],
        ferc_account=parts[6],
        sub_account=parts[7],
        labor_indicator=parts[8] if len(parts) > 8 else "",
    )


# FERC Account Descriptions (commonly used in OVEC)
FERC_ACCOUNTS: Dict[str, str] = {
    # Energy/Fuel accounts (50x)
    "501": "Fuel",
    "502": "Steam Expenses",
    "503": "Steam from Other Sources",
    "506": "Miscellaneous Steam Power Expenses",
    
    # Production plant accounts (51x)
    "510": "Maintenance Supervision and Engineering",
    "511": "Maintenance of Structures",
    "512": "Maintenance of Boiler Plant",
    "513": "Maintenance of Electric Plant",
    "514": "Maintenance of Misc Steam Plant",
    
    # Electric plant accounts (52x-53x)
    "524": "Rent",
    "528": "Property Insurance",
    
    # Transmission accounts (56x-57x)
    "560": "Operation Supervision and Engineering",
    "561": "Load Dispatching",
    "562": "Station Expenses",
    "563": "Overhead Line Expenses",
    "566": "Miscellaneous Transmission Expenses",
    "568": "Maintenance Supervision and Engineering",
    "569": "Maintenance of Structures",
    "570": "Maintenance of Station Equipment",
    "571": "Maintenance of Overhead Lines",
    
    # Administrative accounts (92x-93x)
    "920": "Administrative and General Salaries",
    "921": "Office Supplies and Expenses",
    "923": "Outside Services Employed",
    "924": "Property Insurance",
    "925": "Injuries and Damages",
    "926": "Employee Pensions and Benefits",
    "928": "Regulatory Commission Expenses",
    "930": "Miscellaneous General Expenses",
    "931": "Rents",
    "935": "Maintenance of General Plant",
}


# Department code descriptions
DEPARTMENT_CODES: Dict[str, Dict] = {
    "MAINT": {"name": "Maintenance", "is_outage": False},
    "OPER": {"name": "Operations", "is_outage": False},
    "ENV": {"name": "Environmental", "is_outage": False},
    "IC": {"name": "Instrumentation & Controls", "is_outage": False},
    "LA": {"name": "Lab/Analytical", "is_outage": False},
    "TECH": {"name": "Technical Services", "is_outage": False},
    "SAFETY": {"name": "Safety", "is_outage": False},
    "CHEM": {"name": "Chemistry", "is_outage": False},
    "YARD": {"name": "Yard/Fuel Handling", "is_outage": False},
    "SUPPORT": {"name": "Support Services", "is_outage": False},
    "M&S": {"name": "Materials & Supplies", "is_outage": False},
    "MGT": {"name": "Management", "is_outage": False},
    "OUTAGE": {"name": "Outage (General)", "is_outage": True},
    "UNPLANNED": {"name": "Unplanned Outage", "is_outage": True},
    "PLANNED-01": {"name": "Planned Outage - Unit 1", "is_outage": True, "unit": 1},
    "PLANNED-02": {"name": "Planned Outage - Unit 2", "is_outage": True, "unit": 2},
    "PLANNED-03": {"name": "Planned Outage - Unit 3", "is_outage": True, "unit": 3},
    "PLANNED-04": {"name": "Planned Outage - Unit 4", "is_outage": True, "unit": 4},
    "PLANNED-05": {"name": "Planned Outage - Unit 5", "is_outage": True, "unit": 5},
    "PLANNED-06": {"name": "Planned Outage - Unit 6", "is_outage": True, "unit": 6},
    "PLANNED-12": {"name": "Planned Outage - Unit 12", "is_outage": True, "unit": 12},
    "PLANNED-13": {"name": "Planned Outage - Unit 13", "is_outage": True, "unit": 13},
    "PLANNED-35": {"name": "Planned Outage - Unit 35", "is_outage": True, "unit": 35},
    "PLANNED-46": {"name": "Planned Outage - Unit 46", "is_outage": True, "unit": 46},
}


# Energy cost group codes (from GLDetailsEnergy)
ENERGY_COST_GROUPS: Dict[str, str] = {
    "FPC703": "Coal and Fuel Oil",
    "FPC7035": "Fuel Oil (Kyger specific)",
    "FPC705": "Reagents (Limestone, Urea, Lime, Mercury)",
    "FCP703": "Byproduct Disposal",
}


# Budget ranking codes (priority classification)
BUDGET_RANKINGS: Dict[str, Dict] = {
    "1-Base": {"priority": 1, "category": "Base", "description": "Base operating requirements"},
    "1B Base Co": {"priority": 1, "category": "Base", "description": "Base contractor work"},
    "1R Reliabi": {"priority": 1, "category": "Reliability", "description": "Reliability required"},
    "1-Reliabil": {"priority": 1, "category": "Reliability", "description": "Reliability required"},
    "1-Safety": {"priority": 1, "category": "Safety", "description": "Safety required"},
    "1S Safety": {"priority": 1, "category": "Safety", "description": "Safety required"},
    "1E Environ": {"priority": 1, "category": "Environmental", "description": "Environmental compliance"},
    "1-Environm": {"priority": 1, "category": "Environmental", "description": "Environmental compliance"},
    "1C Circula": {"priority": 1, "category": "Circulating", "description": "Circulating water system"},
    "1-Circular": {"priority": 1, "category": "Circulating", "description": "Circulating water system"},
    "1H Heat Ra": {"priority": 1, "category": "Heat Rate", "description": "Heat rate improvement"},
}


def get_plant_id_from_code(plant_code: str) -> Optional[int]:
    """Get the database plant ID from the GL account plant code.
    
    Args:
        plant_code: "1" for Kyger, "2" for Clifty
        
    Returns:
        Plant ID (1 or 2) or None if invalid
    """
    if plant_code == "1":
        return 1  # Kyger Creek
    elif plant_code == "2":
        return 2  # Clifty Creek
    return None


def get_ferc_description(ferc_code: str) -> str:
    """Get the FERC account description."""
    return FERC_ACCOUNTS.get(ferc_code, f"FERC {ferc_code}")


def get_department_info(dept_code: str) -> Dict:
    """Get department information from code."""
    return DEPARTMENT_CODES.get(dept_code, {"name": dept_code, "is_outage": False})


def determine_cost_section(parsed: ParsedGLAccount) -> str:
    """Determine the cost section (Fuel, Operating, Non-Operating, Capital).
    
    Args:
        parsed: Parsed GL account
        
    Returns:
        Cost section string
    """
    if parsed.is_energy:
        return "fuel"
    
    ferc = parsed.ferc_account
    
    # Administrative accounts (920-935) are typically non-operating
    if ferc.startswith("92") or ferc.startswith("93"):
        return "non_operating"
    
    # Production and transmission accounts are operating
    return "operating"


def map_to_cost_category(parsed: ParsedGLAccount, ferc_desc: str = None) -> Dict:
    """Map a parsed GL account to internal cost category information.
    
    Args:
        parsed: Parsed GL account
        ferc_desc: Optional FERC description override
        
    Returns:
        Dictionary with cost category information
    """
    if ferc_desc is None:
        ferc_desc = get_ferc_description(parsed.ferc_account)
    
    section = determine_cost_section(parsed)
    
    return {
        "section": section,
        "ferc_account": parsed.ferc_account,
        "ferc_description": ferc_desc,
        "is_labor": parsed.is_labor,
        "is_energy": parsed.is_energy,
        "plant_name": parsed.plant_name,
        "department": parsed.department_code,
    }


def parse_budget_key(budget_key: str) -> Dict:
    """Parse a Budget KEY field like 'KygerMAINT003-1-20-401-20-320-512-274-4'.
    
    Args:
        budget_key: The KEY field from PTProd_AcctGL_Budget.csv
        
    Returns:
        Dictionary with plant, department, and parsed account
    """
    # Extract plant prefix (Kyger, Clifty, EO, System)
    plant_prefix = None
    dept = None
    account_start = 0
    
    # Known plant prefixes
    for prefix in ["Kyger", "Clifty", "EO", "System"]:
        if budget_key.startswith(prefix):
            plant_prefix = prefix
            remaining = budget_key[len(prefix):]
            break
    else:
        remaining = budget_key
    
    # Find where the account number starts (003-)
    account_pos = remaining.find("003-")
    if account_pos > 0:
        dept = remaining[:account_pos]
        account_string = remaining[account_pos:]
    elif account_pos == 0:
        account_string = remaining
    else:
        account_string = remaining
    
    parsed_account = parse_gl_account(account_string)
    
    return {
        "plant_prefix": plant_prefix,
        "department": dept,
        "account_string": account_string,
        "parsed": parsed_account,
    }


# Sub-account descriptions for fuel-related accounts
FUEL_SUB_ACCOUNTS: Dict[str, str] = {
    "110": "Fuel Cost Delivered Coal",
    "120": "Fuel Cost Delivered Oil",
    "200": "Sale of Bottom Ash",
    "207": "Sale of Gypsum",
    "305": "Gypsum Disposal Costs",
    "500": "Miscellaneous Reagent Costs",
    "510": "Limestone Costs",
    "530": "Hydrated Lime Costs",
    "540": "Urea Costs",
}


def get_fuel_category_from_sub_account(sub_account: str) -> str:
    """Get the fuel cost category from sub-account code."""
    return FUEL_SUB_ACCOUNTS.get(sub_account, f"Fuel Sub-Account {sub_account}")


def build_account_mapping_from_csv_row(row: Dict) -> Dict:
    """Build a GL account mapping from a CSV row.
    
    Args:
        row: Dictionary from CSV row with FullAccount, AcctDesc, etc.
        
    Returns:
        Dictionary ready for GLAccountMapping creation
    """
    full_account = row.get("FullAccount", row.get("GXACCT", ""))
    parsed = parse_gl_account(full_account)
    
    if not parsed:
        return None
    
    return {
        "gl_account": full_account,
        "company_code": parsed.company_code,
        "plant_code": parsed.plant_code,
        "entity_code": parsed.entity_code,
        "account_type": parsed.account_type,
        "cost_type_code": parsed.cost_type_code,
        "department_code": parsed.department_code,
        "ferc_account": parsed.ferc_account,
        "sub_account": parsed.sub_account,
        "labor_indicator": parsed.labor_indicator,
        "plant_id": get_plant_id_from_code(parsed.plant_code),
        "account_description": row.get("AcctDesc", row.get("CTDESC", "")),
        "is_energy_account": parsed.is_energy,
        "is_labor": parsed.is_labor,
    }

