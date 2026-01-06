"""
GL Transaction model for actuals from Infinium.
"""

from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, Index
from sqlalchemy.sql import func
from src.db.postgres import Base


class GLTransaction(Base):
    """GL Transaction from Infinium GLCUFA.GLPTX1."""
    
    __tablename__ = 'gl_transactions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Key identifiers
    gxjrnl = Column(Numeric(7, 0))
    gxacct = Column(String(36), index=True)
    gxco = Column(String(3))
    
    # Time dimensions
    txyear = Column(Integer, index=True)
    txmnth = Column(Integer, index=True)
    thedat = Column(Date)
    th8dat = Column(Numeric(8, 0))
    
    # Amount
    gxfamt = Column(Numeric(17, 2))
    gxdrcr = Column(String(1))
    
    # Descriptions
    ctdesc = Column(String(30))
    gxdesc = Column(String(30))
    gxdsc2 = Column(String(140))
    
    # Source/Reference
    thsrc = Column(String(10))
    thref = Column(String(10))
    
    # Vendor
    gxvndnum = Column(String(12))
    gxvndn = Column(String(64))
    
    # Project
    gxpjco = Column(String(5))
    gxpjno = Column(String(10))
    phdesc = Column(String(30))
    gxpjdept = Column(String(3))
    gxpjdesc = Column(String(50))
    
    # WBS
    gxpwbs = Column(String(24))
    wbdesc = Column(String(30))
    gxwbs = Column(String(29))
    wbssub01 = Column(String(8))
    wbssub02 = Column(String(3))
    
    # Equipment
    gxeqfc = Column(String(3))
    gxequn = Column(String(12))
    gxeqos = Column(String(6))
    gxeqsc = Column(String(12))
    gxeqcl = Column(String(6))
    gxeqty = Column(String(70))
    gxeqnum = Column(String(15))
    gxeqct = Column(String(6))
    gxeqcnum = Column(String(15))
    gxeqdv = Column(String(20))
    gxeqar = Column(String(8))
    gxeqnm = Column(String(65))
    
    # Invoice/PO subsegments
    invsub01 = Column(String(3))
    invsub02 = Column(String(21))
    invsub03 = Column(String(4))
    posub01 = Column(String(2))
    posub02 = Column(String(8))
    posub03 = Column(String(3))
    posub04 = Column(String(5))
    posub05 = Column(String(8))
    cnsub01 = Column(String(2))
    cnsub02 = Column(String(8))
    cnsub03 = Column(String(5))
    cnsub04 = Column(String(12))
    
    # Outage/Shutdown
    gxshut = Column(String(12), index=True)  # Outage alias e.g. K0125P01
    
    # Other reference fields
    gxpref = Column(String(12))
    gxrfty = Column(String(2))
    gxrfnum = Column(String(15))
    gxplan = Column(String(8))
    gxctid = Column(String(10))
    gxwotd = Column(String(20))
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    
    # Composite index for common queries
    __table_args__ = (
        Index('ix_gl_year_month_acct', 'txyear', 'txmnth', 'gxacct'),
    )
    
    def __repr__(self):
        return f"<GLTransaction {self.gxjrnl} {self.gxacct} {self.gxfamt}>"

