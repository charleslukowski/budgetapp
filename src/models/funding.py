"""Models for budget app features: forecasts, variance explanations, and funding changes."""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Numeric, DateTime, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from src.db.postgres import Base


class SubmissionStatus(str, enum.Enum):
    """Status of budget submission."""
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class DepartmentForecast(Base):
    """Department-level monthly forecast values entered by users."""
    
    __tablename__ = "department_forecasts"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Key fields
    plant_code = Column(String(10), nullable=False, index=True)
    dept_code = Column(String(30), nullable=False, index=True)
    budget_year = Column(Integer, nullable=False, index=True)
    
    # Monthly forecast amounts
    jan = Column(Numeric(18, 2), default=Decimal("0"))
    feb = Column(Numeric(18, 2), default=Decimal("0"))
    mar = Column(Numeric(18, 2), default=Decimal("0"))
    apr = Column(Numeric(18, 2), default=Decimal("0"))
    may = Column(Numeric(18, 2), default=Decimal("0"))
    jun = Column(Numeric(18, 2), default=Decimal("0"))
    jul = Column(Numeric(18, 2), default=Decimal("0"))
    aug = Column(Numeric(18, 2), default=Decimal("0"))
    sep = Column(Numeric(18, 2), default=Decimal("0"))
    oct = Column(Numeric(18, 2), default=Decimal("0"))
    nov = Column(Numeric(18, 2), default=Decimal("0"))
    dec = Column(Numeric(18, 2), default=Decimal("0"))
    total = Column(Numeric(18, 2), default=Decimal("0"))
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    updated_by = Column(String(100), nullable=True)
    
    def __repr__(self):
        return f"<DepartmentForecast({self.plant_code}/{self.dept_code}/{self.budget_year})>"
    
    def get_monthly_amounts(self):
        """Return dictionary of monthly amounts."""
        return {
            1: self.jan, 2: self.feb, 3: self.mar, 4: self.apr,
            5: self.may, 6: self.jun, 7: self.jul, 8: self.aug,
            9: self.sep, 10: self.oct, 11: self.nov, 12: self.dec,
        }
    
    def set_monthly_amount(self, month: int, amount: Decimal):
        """Set amount for a specific month (1-12)."""
        month_map = {
            1: 'jan', 2: 'feb', 3: 'mar', 4: 'apr',
            5: 'may', 6: 'jun', 7: 'jul', 8: 'aug',
            9: 'sep', 10: 'oct', 11: 'nov', 12: 'dec',
        }
        if month in month_map:
            setattr(self, month_map[month], amount)
    
    def calculate_total(self):
        """Recalculate total from monthly values."""
        self.total = sum([
            self.jan or 0, self.feb or 0, self.mar or 0, self.apr or 0,
            self.may or 0, self.jun or 0, self.jul or 0, self.aug or 0,
            self.sep or 0, self.oct or 0, self.nov or 0, self.dec or 0,
        ])


class VarianceExplanation(Base):
    """Explanations for budget variances by department and period."""
    
    __tablename__ = "variance_explanations"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Key fields
    plant_code = Column(String(10), nullable=False, index=True)
    dept_code = Column(String(30), nullable=False, index=True)
    budget_year = Column(Integer, nullable=False, index=True)
    period_month = Column(Integer, nullable=False)  # 1-12 for monthly, 0 for YTD
    
    # Explanation
    explanation = Column(Text, nullable=True)
    variance_amount = Column(Numeric(18, 2), nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(String(100), nullable=True)
    
    def __repr__(self):
        return f"<VarianceExplanation({self.plant_code}/{self.dept_code}/{self.budget_year}/M{self.period_month})>"


class ChangeType(str, enum.Enum):
    """Type of funding change."""
    AMENDMENT = "amendment"
    REALLOCATION = "reallocation"


class ChangeStatus(str, enum.Enum):
    """Status of funding change request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class FundingChange(Base):
    """Budget amendments and reallocations."""
    
    __tablename__ = "funding_changes"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Key fields
    plant_code = Column(String(10), nullable=False, index=True)
    budget_year = Column(Integer, nullable=False, index=True)
    change_type = Column(String(20), nullable=False, index=True)  # 'amendment' or 'reallocation'
    status = Column(String(20), nullable=False, default='pending', index=True)
    
    # For amendments: single department/account change
    department = Column(String(30), nullable=True)
    account = Column(String(50), nullable=True)
    amount = Column(Numeric(18, 2), nullable=True)
    
    # For reallocations: from/to details
    from_department = Column(String(30), nullable=True)
    from_account = Column(String(50), nullable=True)
    to_department = Column(String(30), nullable=True)
    to_account = Column(String(50), nullable=True)
    reallocation_amount = Column(Numeric(18, 2), nullable=True)
    
    # Common fields
    reason = Column(Text, nullable=True)
    requested_by = Column(String(100), nullable=True)
    approved_by = Column(String(100), nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    approved_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<FundingChange({self.change_type}/{self.status}/{self.id})>"
    
    @property
    def display_amount(self):
        """Get the relevant amount for display."""
        if self.change_type == 'amendment':
            return self.amount
        else:
            return self.reallocation_amount
    
    @property
    def display_department(self):
        """Get the relevant department for display."""
        if self.change_type == 'amendment':
            return self.department
        else:
            return f"{self.from_department} → {self.to_department}"


class BudgetSubmission(Base):
    """Tracks budget entry status per department."""
    
    __tablename__ = "budget_submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Key fields
    plant_code = Column(String(10), nullable=False, index=True)
    dept_code = Column(String(30), nullable=False, index=True)
    budget_year = Column(Integer, nullable=False, index=True)
    
    # Status
    status = Column(String(20), nullable=False, default='draft', index=True)
    
    # Submission tracking
    submitted_at = Column(DateTime, nullable=True)
    submitted_by = Column(String(100), nullable=True)
    
    # Approval tracking
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(String(100), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    entries = relationship("BudgetEntry", back_populates="submission", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<BudgetSubmission({self.plant_code}/{self.dept_code}/{self.budget_year} - {self.status})>"
    
    @property
    def is_editable(self):
        """Check if budget can still be edited."""
        return self.status in ['draft', 'rejected']
    
    @property
    def can_submit(self):
        """Check if budget can be submitted."""
        return self.status in ['draft', 'rejected']
    
    @property
    def can_approve(self):
        """Check if budget can be approved."""
        return self.status == 'submitted'


class BudgetEntry(Base):
    """Monthly budget values during entry phase."""
    
    __tablename__ = "budget_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Link to submission
    submission_id = Column(Integer, ForeignKey('budget_submissions.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Key fields (denormalized for easier querying)
    plant_code = Column(String(10), nullable=False, index=True)
    dept_code = Column(String(30), nullable=False, index=True)
    budget_year = Column(Integer, nullable=False, index=True)
    
    # Account info
    account_code = Column(String(50), nullable=True)
    account_name = Column(String(100), nullable=True)
    line_description = Column(String(500), nullable=True)
    
    # Monthly amounts
    jan = Column(Numeric(18, 2), default=Decimal("0"))
    feb = Column(Numeric(18, 2), default=Decimal("0"))
    mar = Column(Numeric(18, 2), default=Decimal("0"))
    apr = Column(Numeric(18, 2), default=Decimal("0"))
    may = Column(Numeric(18, 2), default=Decimal("0"))
    jun = Column(Numeric(18, 2), default=Decimal("0"))
    jul = Column(Numeric(18, 2), default=Decimal("0"))
    aug = Column(Numeric(18, 2), default=Decimal("0"))
    sep = Column(Numeric(18, 2), default=Decimal("0"))
    oct = Column(Numeric(18, 2), default=Decimal("0"))
    nov = Column(Numeric(18, 2), default=Decimal("0"))
    dec = Column(Numeric(18, 2), default=Decimal("0"))
    total = Column(Numeric(18, 2), default=Decimal("0"))
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    submission = relationship("BudgetSubmission", back_populates="entries")
    
    def __repr__(self):
        return f"<BudgetEntry({self.dept_code}/{self.account_code} - ${self.total})>"
    
    def get_monthly_amounts(self):
        """Return list of monthly amounts."""
        return [
            self.jan or 0, self.feb or 0, self.mar or 0, self.apr or 0,
            self.may or 0, self.jun or 0, self.jul or 0, self.aug or 0,
            self.sep or 0, self.oct or 0, self.nov or 0, self.dec or 0,
        ]
    
    def calculate_total(self):
        """Recalculate total from monthly values."""
        self.total = sum(self.get_monthly_amounts())

