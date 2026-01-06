"""Coal Contract model - stores coal supply contracts."""

from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Date, Boolean
from sqlalchemy.orm import relationship

from src.database import Base


class CoalContract(Base):
    """Coal supply contract."""
    
    __tablename__ = "coal_contracts"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Contract identification
    contract_id = Column(String(50), nullable=False, unique=True, index=True)
    supplier = Column(String(100), nullable=False)
    
    # Plant assignment
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    
    # Contract terms
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Annual quantities
    annual_tons = Column(Numeric(18, 2), nullable=False)
    min_tons = Column(Numeric(18, 2), nullable=True)  # Minimum take
    max_tons = Column(Numeric(18, 2), nullable=True)  # Maximum take
    
    # Coal quality
    btu_per_lb = Column(Numeric(10, 2), nullable=False)  # Heat content
    so2_lb_per_mmbtu = Column(Numeric(8, 4), nullable=True)  # SO2 content
    ash_pct = Column(Numeric(6, 4), nullable=True)  # Ash percentage
    moisture_pct = Column(Numeric(6, 4), nullable=True)  # Moisture percentage
    
    # Pricing
    coal_price_per_ton = Column(Numeric(10, 2), nullable=False)  # FOB mine
    barge_price_per_ton = Column(Numeric(10, 2), default=0)  # Transportation
    
    # Coal type
    coal_region = Column(String(50))  # NAPP, ILB, PRB, etc.
    
    # Relationships
    plant = relationship("Plant")
    deliveries = relationship("CoalDelivery", back_populates="contract")
    
    def __repr__(self):
        return f"<CoalContract(id='{self.contract_id}', supplier='{self.supplier}')>"
    
    @property
    def delivered_cost_per_ton(self) -> float:
        """Total delivered cost per ton."""
        return float(self.coal_price_per_ton + (self.barge_price_per_ton or 0))
    
    @property
    def cost_per_mmbtu(self) -> float:
        """Cost per MMBtu."""
        mmbtu_per_ton = float(self.btu_per_lb) * 2000 / 1_000_000
        if mmbtu_per_ton > 0:
            return self.delivered_cost_per_ton / mmbtu_per_ton
        return 0


class CoalDelivery(Base):
    """Monthly coal delivery from a contract."""
    
    __tablename__ = "coal_deliveries"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Contract reference
    contract_id = Column(Integer, ForeignKey("coal_contracts.id"), nullable=False)
    
    # Period
    period_id = Column(Integer, ForeignKey("periods.id"), nullable=True)
    period_yyyymm = Column(String(6), nullable=False, index=True)
    
    # Quantities
    scheduled_tons = Column(Numeric(18, 2), default=0)
    actual_tons = Column(Numeric(18, 2), default=0)
    
    # Actual quality (may differ from contract)
    actual_btu_per_lb = Column(Numeric(10, 2), nullable=True)
    actual_so2 = Column(Numeric(8, 4), nullable=True)
    actual_ash = Column(Numeric(6, 4), nullable=True)
    
    # Actual pricing
    actual_coal_price = Column(Numeric(10, 2), nullable=True)
    actual_barge_price = Column(Numeric(10, 2), nullable=True)
    
    # Relationships
    contract = relationship("CoalContract", back_populates="deliveries")
    period = relationship("Period")
    
    def __repr__(self):
        return f"<CoalDelivery(contract={self.contract_id}, period={self.period_yyyymm}, tons={self.actual_tons})>"


class CoalContractPricing(Base):
    """Monthly pricing for a coal contract.
    
    Allows contract pricing to vary by month, handling:
    - Price escalation clauses
    - Seasonal price adjustments
    - Quality adjustments over time
    """
    
    __tablename__ = "coal_contract_pricing"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Contract reference
    contract_id = Column(Integer, ForeignKey("coal_contracts.id"), nullable=False, index=True)
    
    # Effective period (YYYYMM format)
    effective_month = Column(String(6), nullable=False, index=True)
    
    # Pricing for this period
    coal_price_per_ton = Column(Numeric(10, 2), nullable=False)
    barge_price_per_ton = Column(Numeric(10, 2), default=0)
    
    # Quality for this period (may vary with blending)
    btu_per_lb = Column(Numeric(10, 2), nullable=True)  # NULL = use contract default
    so2_lb_per_mmbtu = Column(Numeric(8, 4), nullable=True)
    
    # Relationships
    contract = relationship("CoalContract", backref="pricing_schedule")
    
    def __repr__(self):
        return f"<CoalContractPricing(contract_id={self.contract_id}, month={self.effective_month}, price={self.coal_price_per_ton})>"
    
    @property
    def delivered_cost_per_ton(self) -> float:
        """Total delivered cost per ton."""
        return float(self.coal_price_per_ton + (self.barge_price_per_ton or 0))
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "contract_id": self.contract_id,
            "effective_month": self.effective_month,
            "coal_price_per_ton": float(self.coal_price_per_ton) if self.coal_price_per_ton else 0,
            "barge_price_per_ton": float(self.barge_price_per_ton) if self.barge_price_per_ton else 0,
            "btu_per_lb": float(self.btu_per_lb) if self.btu_per_lb else None,
            "so2_lb_per_mmbtu": float(self.so2_lb_per_mmbtu) if self.so2_lb_per_mmbtu else None,
            "delivered_cost_per_ton": self.delivered_cost_per_ton,
        }


class UncommittedCoalPrice(Base):
    """Spot market pricing for uncommitted coal.
    
    Used when burn exceeds contracted supply.
    Stores expected market prices for forecasting.
    """
    
    __tablename__ = "uncommitted_coal_prices"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Plant
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False, index=True)
    
    # Period
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False)  # 1-12
    
    # Pricing
    price_per_ton = Column(Numeric(10, 2), nullable=False)
    barge_per_ton = Column(Numeric(10, 2), default=0)
    
    # Quality assumptions
    btu_per_lb = Column(Numeric(10, 2), nullable=False, default=12500)
    
    # Source/market reference
    source_name = Column(String(50), default="NAPP Spot")  # NAPP Spot, ILB Spot
    
    # Relationships
    plant = relationship("Plant")
    
    def __repr__(self):
        return f"<UncommittedCoalPrice(plant_id={self.plant_id}, {self.year}-{self.month:02d}, price={self.price_per_ton})>"
    
    @property
    def period_yyyymm(self) -> str:
        """Return period as YYYYMM string."""
        return f"{self.year}{self.month:02d}"
    
    @property
    def delivered_cost_per_ton(self) -> float:
        """Total delivered cost per ton."""
        return float(self.price_per_ton + (self.barge_per_ton or 0))
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "plant_id": self.plant_id,
            "year": self.year,
            "month": self.month,
            "price_per_ton": float(self.price_per_ton) if self.price_per_ton else 0,
            "barge_per_ton": float(self.barge_per_ton) if self.barge_per_ton else 0,
            "btu_per_lb": float(self.btu_per_lb) if self.btu_per_lb else 12500,
            "source_name": self.source_name,
            "delivered_cost_per_ton": self.delivered_cost_per_ton,
        }


class UncommittedCoal(Base):
    """Uncommitted (spot market) coal purchases - actual consumption.
    
    Note: Use UncommittedCoalPrice for forecasting pricing assumptions.
    This table stores actual uncommitted coal purchases/consumption.
    """
    
    __tablename__ = "uncommitted_coal"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Plant
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    
    # Period
    period_yyyymm = Column(String(6), nullable=False, index=True)
    period_id = Column(Integer, ForeignKey("periods.id"), nullable=True)
    
    # Quantities
    tons = Column(Numeric(18, 2), default=0)
    
    # Quality (assumed)
    btu_per_lb = Column(Numeric(10, 2), nullable=False)
    so2_lb_per_mmbtu = Column(Numeric(8, 4), nullable=True)
    
    # Market pricing
    market_price_per_ton = Column(Numeric(10, 2), nullable=False)
    barge_price_per_ton = Column(Numeric(10, 2), default=0)
    
    # Source
    coal_region = Column(String(50))  # NAPP, ILB, etc.
    
    # Relationships
    plant = relationship("Plant")
    period = relationship("Period")
    
    def __repr__(self):
        return f"<UncommittedCoal(plant_id={self.plant_id}, period={self.period_yyyymm}, tons={self.tons})>"

