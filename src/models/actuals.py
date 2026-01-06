"""Actuals model - stores actual cost transactions from GL system."""

from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Date, Boolean
from sqlalchemy.orm import relationship

from src.database import Base


class EnergyActual(Base):
    """Actual energy/fuel cost transactions from GLDetailsEnergy."""
    
    __tablename__ = "energy_actuals"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Source identifiers
    gl_detail_id = Column(String(20), nullable=True)  # GLDetailExpenseID
    journal = Column(String(20), nullable=True)  # GXJRNL
    
    # Period
    period_yyyymm = Column(String(6), nullable=False, index=True)  # YYYYMM
    period_id = Column(Integer, ForeignKey("periods.id"), nullable=True)
    
    # Account information
    gl_account = Column(String(50), nullable=False, index=True)  # GXACCT
    account_description = Column(String(100))  # CTDESC
    
    # Plant
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=True)
    budget_entity = Column(String(20))  # BUDGET field (Kyger, Clifty, System)
    
    # Amount
    amount = Column(Numeric(18, 2), nullable=False)  # GXFAMT
    debit_credit = Column(String(1))  # GXDRCR (D/C)
    
    # Classification
    cost_group = Column(String(20), index=True)  # GROUP (FPC703, FPC705, etc.)
    cost_type = Column(String(20))  # TYPE (NONOUTAGE, PLANNED, UNPLANNED)
    labor_nonlabor = Column(String(20))  # LABOR-NONLABOR
    
    # Transaction details
    description = Column(String(100))  # GXDESC
    description2 = Column(String(200))  # GXDSC2
    trans_date = Column(Date, nullable=True)  # X1TRANSDATE
    
    # Work order/project reference
    work_order = Column(String(30))  # X1WORKORDER
    po_number = Column(String(30))  # X1PONUM
    project_id = Column(String(30))  # X1PROJECTID
    project_desc = Column(String(100))  # PROJ_DESC
    
    # Vendor
    vendor_id = Column(String(20))  # X1VENDOR
    vendor_name = Column(String(100))  # X1VENDORNAME
    
    # Relationships
    period = relationship("Period")
    plant = relationship("Plant")
    
    def __repr__(self):
        return f"<EnergyActual(period={self.period_yyyymm}, account={self.gl_account}, amount={self.amount})>"


class ExpenseActual(Base):
    """Actual O&M expense transactions from GLDetailsExpense."""
    
    __tablename__ = "expense_actuals"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Source identifiers
    gl_detail_id = Column(String(20), nullable=True)
    journal = Column(String(20), nullable=True)
    
    # Period
    period_yyyymm = Column(String(6), nullable=False, index=True)
    period_id = Column(Integer, ForeignKey("periods.id"), nullable=True)
    
    # Account information
    gl_account = Column(String(50), nullable=False, index=True)
    account_description = Column(String(100))
    
    # Plant
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=True)
    budget_entity = Column(String(20))
    
    # Amount
    amount = Column(Numeric(18, 2), nullable=False)
    debit_credit = Column(String(1))
    
    # Classification
    department = Column(String(30), index=True)  # GROUP field (MAINT, OPER, PLANNED-01, etc.)
    cost_type = Column(String(20))  # TYPE (NONOUTAGE, PLANNED, UNPLANNED)
    labor_nonlabor = Column(String(20))
    outage_unit = Column(String(10))  # OUTAGE UNIT
    
    # Transaction details
    description = Column(String(100))
    description2 = Column(String(200))
    trans_date = Column(Date, nullable=True)
    
    # Work order/project reference
    work_order = Column(String(30))
    po_number = Column(String(30))
    project_id = Column(String(30))
    project_desc = Column(String(100))
    
    # Vendor
    vendor_id = Column(String(20))
    vendor_name = Column(String(100))
    
    # Location
    location = Column(String(30))  # LOCATION
    location_desc = Column(String(100))  # LOC_DESC
    
    # Relationships
    period = relationship("Period")
    plant = relationship("Plant")
    
    def __repr__(self):
        return f"<ExpenseActual(period={self.period_yyyymm}, dept={self.department}, amount={self.amount})>"


class BudgetLine(Base):
    """Budget line items from PTProd_AcctGL_Budget."""
    
    __tablename__ = "budget_lines"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Source identifiers
    budget_history_link = Column(String(20))  # BudgetHistoryLink
    budget_key = Column(String(100), index=True)  # KEY
    budget_number = Column(String(20))  # Budget#
    
    # Account information
    full_account = Column(String(50), nullable=False, index=True)  # FullAccount
    account_code = Column(String(50))  # Account
    account_description = Column(String(100))  # AcctDesc
    line_description = Column(String(500))  # Description
    
    # Plant/Entity
    budget_entity = Column(String(20), index=True)  # BUDGET (Kyger, Clifty, EO, System)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=True)
    
    # Department
    department = Column(String(30), index=True)  # Dept
    
    # Labor indicator
    labor_nonlabor = Column(String(5))  # L/N
    
    # Budget year
    budget_year = Column(Integer, nullable=False, index=True)  # BudgetYear
    
    # Monthly amounts
    jan = Column(Numeric(18, 2), default=0)
    feb = Column(Numeric(18, 2), default=0)
    mar = Column(Numeric(18, 2), default=0)
    apr = Column(Numeric(18, 2), default=0)
    may = Column(Numeric(18, 2), default=0)
    jun = Column(Numeric(18, 2), default=0)
    jul = Column(Numeric(18, 2), default=0)
    aug = Column(Numeric(18, 2), default=0)
    sep = Column(Numeric(18, 2), default=0)
    oct = Column(Numeric(18, 2), default=0)
    nov = Column(Numeric(18, 2), default=0)
    dec = Column(Numeric(18, 2), default=0)
    total = Column(Numeric(18, 2), default=0)
    
    # Out-year projections
    year_plus_1 = Column(Numeric(18, 2), default=0)  # BudgetYear+1
    year_plus_2 = Column(Numeric(18, 2), default=0)  # BudgetYear+2
    year_plus_3 = Column(Numeric(18, 2), default=0)  # BudgetYear+3
    year_plus_4 = Column(Numeric(18, 2), default=0)  # BudgetYear+4
    
    # Ranking/Priority
    ranking = Column(String(20))  # Ranking
    ranking_priority = Column(Integer, nullable=True)
    ranking_category = Column(String(30), nullable=True)
    
    # Comments
    comments = Column(String(500))  # Comments
    
    # Import metadata
    import_date = Column(Date)  # ImportDate
    
    # Relationships
    plant = relationship("Plant")
    
    def __repr__(self):
        return f"<BudgetLine(entity={self.budget_entity}, account={self.full_account}, total={self.total})>"
    
    def get_monthly_amounts(self):
        """Return dictionary of monthly amounts."""
        return {
            1: self.jan, 2: self.feb, 3: self.mar, 4: self.apr,
            5: self.may, 6: self.jun, 7: self.jul, 8: self.aug,
            9: self.sep, 10: self.oct, 11: self.nov, 12: self.dec,
        }


class CoalInventory(Base):
    """Coal inventory and consumption from Aligne exports."""
    
    __tablename__ = "coal_inventory"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Period
    period_yyyymm = Column(String(6), nullable=False, index=True)
    period_id = Column(Integer, ForeignKey("periods.id"), nullable=True)
    
    # Plant (company_id: 1=Kyger, 2=Clifty)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    
    # Coal quantities (tons)
    purchased_tons = Column(Numeric(18, 2), default=0)
    consumed_tons = Column(Numeric(18, 2), default=0)
    inventory_adjustment = Column(Numeric(18, 2), default=0)
    ending_inventory_tons = Column(Numeric(18, 2), default=0)
    
    # Relationships
    period = relationship("Period")
    plant = relationship("Plant")
    
    def __repr__(self):
        return f"<CoalInventory(period={self.period_yyyymm}, plant_id={self.plant_id}, consumed={self.consumed_tons})>"


class CoalStartingInventory(Base):
    """January 1st starting inventory for coal supply calculations.
    
    This value is imported from the Excel fuel model and represents
    the beginning inventory on January 1st for forecasting purposes.
    """
    
    __tablename__ = "coal_starting_inventory"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Year and Plant
    year = Column(Integer, nullable=False, index=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    
    # Starting inventory on January 1st (tons)
    beginning_inventory_tons = Column(Numeric(18, 2), nullable=False)
    
    # Optional: source/notes
    source = Column(String(100), nullable=True)  # e.g., "Excel Model 2025"
    
    # Relationships
    plant = relationship("Plant")
    
    def __repr__(self):
        return f"<CoalStartingInventory(year={self.year}, plant_id={self.plant_id}, tons={self.beginning_inventory_tons})>"
