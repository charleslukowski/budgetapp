"""
SQLAlchemy models for mapping tables.
"""

from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ProjectMapping(Base):
    """Maps project numbers to department codes."""
    __tablename__ = 'project_mappings'

    id = Column(Integer, primary_key=True)
    project_number = Column(String(20), nullable=False, unique=True, index=True)
    txn_count = Column(Integer)
    dept_code = Column(String(20), nullable=False)

    def __repr__(self):
        return f"<ProjectMapping(project_number='{self.project_number}', dept_code='{self.dept_code}')>"


class AccountDeptMapping(Base):
    """Maps account CTUF01 codes to department codes (fallback)."""
    __tablename__ = 'account_dept_mappings'

    id = Column(Integer, primary_key=True)
    ctuf01 = Column(String(20), nullable=False, unique=True, index=True)
    account_count = Column(Integer)
    dept_code = Column(String(20), nullable=False)

    def __repr__(self):
        return f"<AccountDeptMapping(ctuf01='{self.ctuf01}', dept_code='{self.dept_code}')>"

