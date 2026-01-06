"""
Pydantic schemas for API responses.
"""

from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal


class MonthlyAmount(BaseModel):
    """Monthly financial data."""
    month: int
    actual: Decimal = Decimal("0")
    budget: Decimal = Decimal("0")
    forecast: Decimal = Decimal("0")
    variance: Decimal = Decimal("0")


class DepartmentSummary(BaseModel):
    """Department summary with monthly breakdown."""
    dept_code: str
    dept_name: str
    plant_code: str
    is_outage: bool = False
    months: List[MonthlyAmount] = []
    ytd_actual: Decimal = Decimal("0")
    ytd_budget: Decimal = Decimal("0")
    ytd_variance: Decimal = Decimal("0")
    year_end_projection: Decimal = Decimal("0")


class PlantSummary(BaseModel):
    """Plant-level summary."""
    plant_code: str
    plant_name: str
    departments: List[DepartmentSummary] = []
    total_actual: Decimal = Decimal("0")
    total_budget: Decimal = Decimal("0")
    total_variance: Decimal = Decimal("0")


class CorporateSummary(BaseModel):
    """Corporate-level summary with plants."""
    year: int
    current_month: int
    plants: List[PlantSummary] = []
    grand_total_actual: Decimal = Decimal("0")
    grand_total_budget: Decimal = Decimal("0")
    grand_total_variance: Decimal = Decimal("0")


class Transaction(BaseModel):
    """GL Transaction detail."""
    id: int
    gxacct: str
    account_desc: Optional[str] = None
    txyear: int
    txmnth: int
    gxfamt: Decimal
    gxdrcr: str
    gxpjno: Optional[str] = None
    gxshut: Optional[str] = None
    gxdesc: Optional[str] = None
    dept_code: str
    outage_group: Optional[str] = None
    plant_code: str


class TransactionList(BaseModel):
    """Paginated list of transactions."""
    transactions: List[Transaction]
    total: int
    page: int
    page_size: int


class TransactionFilter(BaseModel):
    """Filter parameters for transactions."""
    year: Optional[int] = None
    month: Optional[int] = None
    plant_code: Optional[str] = None
    dept_code: Optional[str] = None
    outage_group: Optional[str] = None
    account: Optional[str] = None
    page: int = 1
    page_size: int = 100

