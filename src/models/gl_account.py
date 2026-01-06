"""
GL Account model for account master from Infinium.
"""

from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.sql import func
from src.db.postgres import Base


class GLAccount(Base):
    """GL Account from Infinium GLDBFA.GLPCT."""
    
    __tablename__ = 'gl_accounts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Key fields
    ctacct = Column(String(36), unique=True, index=True)  # Account number
    ctdesc = Column(String(30))  # Description
    ctco = Column(String(3))  # Company
    
    # Status
    ctactv = Column(String(1))  # Active flag
    ctmors = Column(String(1))  # M=Main, S=Sub
    
    # User fields (used for categorization)
    ctuf01 = Column(String(10))  # e.g., FPC100, FPC250
    ctuf02 = Column(String(10))  # e.g., ASSET
    ctuf03 = Column(String(10))
    ctuf04 = Column(String(10))
    
    # Segment breakout (from CTRC fields)
    ctrc01 = Column(String(3))   # Company segment
    ctrc02 = Column(String(8))   # Plant segment
    ctrc03 = Column(String(8))   # Location segment
    ctrc04 = Column(String(8))   # FERC segment
    ctrc05 = Column(String(8))   # Sub segment
    ctrc06 = Column(String(8))   # Department segment
    ctrc07 = Column(String(8))   # Detail segment
    ctrc08 = Column(String(8))   # Sub-detail segment
    ctrc09 = Column(String(8))   # Labor type segment
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<GLAccount {self.ctacct} {self.ctdesc}>"
