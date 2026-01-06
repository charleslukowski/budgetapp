"""
Coal Contract API endpoints.

Provides CRUD operations for coal contracts and pricing, supporting:
- Contract management (supplier, terms, quantities)
- Monthly pricing schedules with escalation
- Uncommitted coal (spot market) pricing
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field
from datetime import datetime, date

from src.db.postgres import get_session
from src.models.coal_contract import (
    CoalContract,
    CoalDelivery,
    CoalContractPricing,
    UncommittedCoalPrice,
)
from src.models.plant import Plant


router = APIRouter(prefix="/api/coal-contracts", tags=["Coal Contracts"])


# =============================================================================
# Pydantic Models
# =============================================================================

class CoalContractResponse(BaseModel):
    """Response model for a coal contract."""
    id: int
    contract_id: str
    supplier: str
    plant_id: int
    start_date: date
    end_date: date
    is_active: bool
    annual_tons: float
    min_tons: Optional[float]
    max_tons: Optional[float]
    btu_per_lb: float
    so2_lb_per_mmbtu: Optional[float]
    ash_pct: Optional[float]
    moisture_pct: Optional[float]
    coal_price_per_ton: float
    barge_price_per_ton: float
    coal_region: Optional[str]
    delivered_cost_per_ton: float
    cost_per_mmbtu: float

    class Config:
        from_attributes = True


class CoalContractCreateRequest(BaseModel):
    """Request model for creating a coal contract."""
    contract_id: str
    supplier: str
    plant_id: int
    start_date: date
    end_date: date
    annual_tons: float = Field(gt=0)
    min_tons: Optional[float] = None
    max_tons: Optional[float] = None
    btu_per_lb: float = Field(gt=0, default=12500)
    so2_lb_per_mmbtu: Optional[float] = None
    ash_pct: Optional[float] = None
    moisture_pct: Optional[float] = None
    coal_price_per_ton: float = Field(gt=0)
    barge_price_per_ton: float = Field(ge=0, default=0)
    coal_region: Optional[str] = "NAPP"


class CoalContractUpdateRequest(BaseModel):
    """Request model for updating a coal contract."""
    supplier: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None
    annual_tons: Optional[float] = None
    min_tons: Optional[float] = None
    max_tons: Optional[float] = None
    btu_per_lb: Optional[float] = None
    so2_lb_per_mmbtu: Optional[float] = None
    ash_pct: Optional[float] = None
    moisture_pct: Optional[float] = None
    coal_price_per_ton: Optional[float] = None
    barge_price_per_ton: Optional[float] = None
    coal_region: Optional[str] = None


class ContractPricingItem(BaseModel):
    """A single monthly pricing item."""
    effective_month: str = Field(pattern=r"^\d{6}$", description="YYYYMM format")
    coal_price_per_ton: float = Field(gt=0)
    barge_price_per_ton: float = Field(ge=0, default=0)
    btu_per_lb: Optional[float] = None
    so2_lb_per_mmbtu: Optional[float] = None


class ContractPricingResponse(BaseModel):
    """Response for contract pricing."""
    id: int
    contract_id: int
    effective_month: str
    coal_price_per_ton: float
    barge_price_per_ton: float
    btu_per_lb: Optional[float]
    so2_lb_per_mmbtu: Optional[float]
    delivered_cost_per_ton: float

    class Config:
        from_attributes = True


class UncommittedPriceResponse(BaseModel):
    """Response for uncommitted coal price."""
    id: int
    plant_id: int
    year: int
    month: int
    price_per_ton: float
    barge_per_ton: float
    btu_per_lb: float
    source_name: str
    delivered_cost_per_ton: float

    class Config:
        from_attributes = True


class UncommittedPriceUpdateRequest(BaseModel):
    """Request for updating uncommitted coal price."""
    price_per_ton: float = Field(gt=0)
    barge_per_ton: float = Field(ge=0, default=0)
    btu_per_lb: float = Field(gt=0, default=12500)
    source_name: str = "NAPP Spot"


# =============================================================================
# Contract Endpoints
# =============================================================================

@router.get("/", response_model=List[CoalContractResponse])
async def list_contracts(
    plant_id: Optional[int] = None,
    supplier: Optional[str] = None,
    active_only: bool = False,
    year: Optional[int] = None,
):
    """List all coal contracts with optional filtering.
    
    Args:
        plant_id: Filter by plant
        supplier: Filter by supplier name (partial match)
        active_only: Only return active contracts
        year: Filter by contracts active during this year
    """
    with get_session() as db:
        query = db.query(CoalContract)
        
        if plant_id:
            query = query.filter(CoalContract.plant_id == plant_id)
        
        if supplier:
            query = query.filter(CoalContract.supplier.ilike(f"%{supplier}%"))
        
        if active_only:
            query = query.filter(CoalContract.is_active == True)
        
        if year:
            start = date(year, 1, 1)
            end = date(year, 12, 31)
            query = query.filter(
                CoalContract.start_date <= end,
                CoalContract.end_date >= start,
            )
        
        contracts = query.all()
        
        return [
            CoalContractResponse(
                id=c.id,
                contract_id=c.contract_id,
                supplier=c.supplier,
                plant_id=c.plant_id,
                start_date=c.start_date,
                end_date=c.end_date,
                is_active=c.is_active,
                annual_tons=float(c.annual_tons) if c.annual_tons else 0,
                min_tons=float(c.min_tons) if c.min_tons else None,
                max_tons=float(c.max_tons) if c.max_tons else None,
                btu_per_lb=float(c.btu_per_lb) if c.btu_per_lb else 12500,
                so2_lb_per_mmbtu=float(c.so2_lb_per_mmbtu) if c.so2_lb_per_mmbtu else None,
                ash_pct=float(c.ash_pct) if c.ash_pct else None,
                moisture_pct=float(c.moisture_pct) if c.moisture_pct else None,
                coal_price_per_ton=float(c.coal_price_per_ton) if c.coal_price_per_ton else 0,
                barge_price_per_ton=float(c.barge_price_per_ton) if c.barge_price_per_ton else 0,
                coal_region=c.coal_region,
                delivered_cost_per_ton=c.delivered_cost_per_ton,
                cost_per_mmbtu=c.cost_per_mmbtu,
            )
            for c in contracts
        ]


@router.get("/{contract_id}", response_model=CoalContractResponse)
async def get_contract(contract_id: int):
    """Get a specific contract by ID."""
    with get_session() as db:
        c = db.query(CoalContract).filter(CoalContract.id == contract_id).first()
        
        if not c:
            raise HTTPException(status_code=404, detail=f"Contract not found: {contract_id}")
        
        return CoalContractResponse(
            id=c.id,
            contract_id=c.contract_id,
            supplier=c.supplier,
            plant_id=c.plant_id,
            start_date=c.start_date,
            end_date=c.end_date,
            is_active=c.is_active,
            annual_tons=float(c.annual_tons) if c.annual_tons else 0,
            min_tons=float(c.min_tons) if c.min_tons else None,
            max_tons=float(c.max_tons) if c.max_tons else None,
            btu_per_lb=float(c.btu_per_lb) if c.btu_per_lb else 12500,
            so2_lb_per_mmbtu=float(c.so2_lb_per_mmbtu) if c.so2_lb_per_mmbtu else None,
            ash_pct=float(c.ash_pct) if c.ash_pct else None,
            moisture_pct=float(c.moisture_pct) if c.moisture_pct else None,
            coal_price_per_ton=float(c.coal_price_per_ton) if c.coal_price_per_ton else 0,
            barge_price_per_ton=float(c.barge_price_per_ton) if c.barge_price_per_ton else 0,
            coal_region=c.coal_region,
            delivered_cost_per_ton=c.delivered_cost_per_ton,
            cost_per_mmbtu=c.cost_per_mmbtu,
        )


@router.post("/", response_model=CoalContractResponse)
async def create_contract(request: CoalContractCreateRequest):
    """Create a new coal contract."""
    with get_session() as db:
        # Verify plant exists
        plant = db.query(Plant).filter(Plant.id == request.plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail=f"Plant not found: {request.plant_id}")
        
        # Check for duplicate contract_id
        existing = db.query(CoalContract).filter(
            CoalContract.contract_id == request.contract_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Contract ID already exists: {request.contract_id}")
        
        c = CoalContract(
            contract_id=request.contract_id,
            supplier=request.supplier,
            plant_id=request.plant_id,
            start_date=request.start_date,
            end_date=request.end_date,
            is_active=True,
            annual_tons=Decimal(str(request.annual_tons)),
            min_tons=Decimal(str(request.min_tons)) if request.min_tons else None,
            max_tons=Decimal(str(request.max_tons)) if request.max_tons else None,
            btu_per_lb=Decimal(str(request.btu_per_lb)),
            so2_lb_per_mmbtu=Decimal(str(request.so2_lb_per_mmbtu)) if request.so2_lb_per_mmbtu else None,
            ash_pct=Decimal(str(request.ash_pct)) if request.ash_pct else None,
            moisture_pct=Decimal(str(request.moisture_pct)) if request.moisture_pct else None,
            coal_price_per_ton=Decimal(str(request.coal_price_per_ton)),
            barge_price_per_ton=Decimal(str(request.barge_price_per_ton)),
            coal_region=request.coal_region,
        )
        
        db.add(c)
        db.commit()
        db.refresh(c)
        
        return CoalContractResponse(
            id=c.id,
            contract_id=c.contract_id,
            supplier=c.supplier,
            plant_id=c.plant_id,
            start_date=c.start_date,
            end_date=c.end_date,
            is_active=c.is_active,
            annual_tons=float(c.annual_tons),
            min_tons=float(c.min_tons) if c.min_tons else None,
            max_tons=float(c.max_tons) if c.max_tons else None,
            btu_per_lb=float(c.btu_per_lb),
            so2_lb_per_mmbtu=float(c.so2_lb_per_mmbtu) if c.so2_lb_per_mmbtu else None,
            ash_pct=float(c.ash_pct) if c.ash_pct else None,
            moisture_pct=float(c.moisture_pct) if c.moisture_pct else None,
            coal_price_per_ton=float(c.coal_price_per_ton),
            barge_price_per_ton=float(c.barge_price_per_ton),
            coal_region=c.coal_region,
            delivered_cost_per_ton=c.delivered_cost_per_ton,
            cost_per_mmbtu=c.cost_per_mmbtu,
        )


@router.put("/{contract_id}", response_model=CoalContractResponse)
async def update_contract(contract_id: int, request: CoalContractUpdateRequest):
    """Update an existing coal contract."""
    with get_session() as db:
        c = db.query(CoalContract).filter(CoalContract.id == contract_id).first()
        
        if not c:
            raise HTTPException(status_code=404, detail=f"Contract not found: {contract_id}")
        
        # Update fields if provided
        if request.supplier is not None:
            c.supplier = request.supplier
        if request.start_date is not None:
            c.start_date = request.start_date
        if request.end_date is not None:
            c.end_date = request.end_date
        if request.is_active is not None:
            c.is_active = request.is_active
        if request.annual_tons is not None:
            c.annual_tons = Decimal(str(request.annual_tons))
        if request.min_tons is not None:
            c.min_tons = Decimal(str(request.min_tons))
        if request.max_tons is not None:
            c.max_tons = Decimal(str(request.max_tons))
        if request.btu_per_lb is not None:
            c.btu_per_lb = Decimal(str(request.btu_per_lb))
        if request.so2_lb_per_mmbtu is not None:
            c.so2_lb_per_mmbtu = Decimal(str(request.so2_lb_per_mmbtu))
        if request.ash_pct is not None:
            c.ash_pct = Decimal(str(request.ash_pct))
        if request.moisture_pct is not None:
            c.moisture_pct = Decimal(str(request.moisture_pct))
        if request.coal_price_per_ton is not None:
            c.coal_price_per_ton = Decimal(str(request.coal_price_per_ton))
        if request.barge_price_per_ton is not None:
            c.barge_price_per_ton = Decimal(str(request.barge_price_per_ton))
        if request.coal_region is not None:
            c.coal_region = request.coal_region
        
        db.commit()
        db.refresh(c)
        
        return CoalContractResponse(
            id=c.id,
            contract_id=c.contract_id,
            supplier=c.supplier,
            plant_id=c.plant_id,
            start_date=c.start_date,
            end_date=c.end_date,
            is_active=c.is_active,
            annual_tons=float(c.annual_tons) if c.annual_tons else 0,
            min_tons=float(c.min_tons) if c.min_tons else None,
            max_tons=float(c.max_tons) if c.max_tons else None,
            btu_per_lb=float(c.btu_per_lb) if c.btu_per_lb else 12500,
            so2_lb_per_mmbtu=float(c.so2_lb_per_mmbtu) if c.so2_lb_per_mmbtu else None,
            ash_pct=float(c.ash_pct) if c.ash_pct else None,
            moisture_pct=float(c.moisture_pct) if c.moisture_pct else None,
            coal_price_per_ton=float(c.coal_price_per_ton) if c.coal_price_per_ton else 0,
            barge_price_per_ton=float(c.barge_price_per_ton) if c.barge_price_per_ton else 0,
            coal_region=c.coal_region,
            delivered_cost_per_ton=c.delivered_cost_per_ton,
            cost_per_mmbtu=c.cost_per_mmbtu,
        )


@router.delete("/{contract_id}")
async def delete_contract(contract_id: int):
    """Delete a coal contract and its pricing schedule."""
    with get_session() as db:
        c = db.query(CoalContract).filter(CoalContract.id == contract_id).first()
        
        if not c:
            raise HTTPException(status_code=404, detail=f"Contract not found: {contract_id}")
        
        # Delete related records
        db.query(CoalContractPricing).filter(
            CoalContractPricing.contract_id == contract_id
        ).delete()
        
        db.query(CoalDelivery).filter(
            CoalDelivery.contract_id == contract_id
        ).delete()
        
        db.delete(c)
        db.commit()
        
        return {"status": "deleted", "contract_id": contract_id}


# =============================================================================
# Contract Pricing Endpoints
# =============================================================================

@router.get("/{contract_id}/pricing", response_model=List[ContractPricingResponse])
async def get_contract_pricing(
    contract_id: int,
    year: Optional[int] = None,
):
    """Get monthly pricing schedule for a contract.
    
    Args:
        contract_id: Contract ID
        year: Optional year filter (YYYY)
    """
    with get_session() as db:
        # Verify contract exists
        c = db.query(CoalContract).filter(CoalContract.id == contract_id).first()
        if not c:
            raise HTTPException(status_code=404, detail=f"Contract not found: {contract_id}")
        
        query = db.query(CoalContractPricing).filter(
            CoalContractPricing.contract_id == contract_id
        )
        
        if year:
            query = query.filter(
                CoalContractPricing.effective_month.like(f"{year}%")
            )
        
        pricing = query.order_by(CoalContractPricing.effective_month).all()
        
        return [
            ContractPricingResponse(
                id=p.id,
                contract_id=p.contract_id,
                effective_month=p.effective_month,
                coal_price_per_ton=float(p.coal_price_per_ton) if p.coal_price_per_ton else 0,
                barge_price_per_ton=float(p.barge_price_per_ton) if p.barge_price_per_ton else 0,
                btu_per_lb=float(p.btu_per_lb) if p.btu_per_lb else None,
                so2_lb_per_mmbtu=float(p.so2_lb_per_mmbtu) if p.so2_lb_per_mmbtu else None,
                delivered_cost_per_ton=p.delivered_cost_per_ton,
            )
            for p in pricing
        ]


@router.put("/{contract_id}/pricing/{effective_month}", response_model=ContractPricingResponse)
async def update_contract_pricing(
    contract_id: int,
    effective_month: str,
    request: ContractPricingItem,
):
    """Update or create pricing for a specific month.
    
    Args:
        contract_id: Contract ID
        effective_month: Month in YYYYMM format
    """
    with get_session() as db:
        # Verify contract exists
        c = db.query(CoalContract).filter(CoalContract.id == contract_id).first()
        if not c:
            raise HTTPException(status_code=404, detail=f"Contract not found: {contract_id}")
        
        # Find or create pricing
        existing = db.query(CoalContractPricing).filter(
            CoalContractPricing.contract_id == contract_id,
            CoalContractPricing.effective_month == effective_month,
        ).first()
        
        if existing:
            existing.coal_price_per_ton = Decimal(str(request.coal_price_per_ton))
            existing.barge_price_per_ton = Decimal(str(request.barge_price_per_ton))
            if request.btu_per_lb:
                existing.btu_per_lb = Decimal(str(request.btu_per_lb))
            if request.so2_lb_per_mmbtu:
                existing.so2_lb_per_mmbtu = Decimal(str(request.so2_lb_per_mmbtu))
            p = existing
        else:
            p = CoalContractPricing(
                contract_id=contract_id,
                effective_month=effective_month,
                coal_price_per_ton=Decimal(str(request.coal_price_per_ton)),
                barge_price_per_ton=Decimal(str(request.barge_price_per_ton)),
                btu_per_lb=Decimal(str(request.btu_per_lb)) if request.btu_per_lb else None,
                so2_lb_per_mmbtu=Decimal(str(request.so2_lb_per_mmbtu)) if request.so2_lb_per_mmbtu else None,
            )
            db.add(p)
        
        db.commit()
        db.refresh(p)
        
        return ContractPricingResponse(
            id=p.id,
            contract_id=p.contract_id,
            effective_month=p.effective_month,
            coal_price_per_ton=float(p.coal_price_per_ton),
            barge_price_per_ton=float(p.barge_price_per_ton),
            btu_per_lb=float(p.btu_per_lb) if p.btu_per_lb else None,
            so2_lb_per_mmbtu=float(p.so2_lb_per_mmbtu) if p.so2_lb_per_mmbtu else None,
            delivered_cost_per_ton=p.delivered_cost_per_ton,
        )


@router.post("/{contract_id}/pricing/bulk")
async def bulk_update_contract_pricing(
    contract_id: int,
    pricing: List[ContractPricingItem],
):
    """Bulk update pricing for a contract.
    
    Accepts an array of monthly pricing items.
    """
    with get_session() as db:
        # Verify contract exists
        c = db.query(CoalContract).filter(CoalContract.id == contract_id).first()
        if not c:
            raise HTTPException(status_code=404, detail=f"Contract not found: {contract_id}")
        
        results = []
        for item in pricing:
            existing = db.query(CoalContractPricing).filter(
                CoalContractPricing.contract_id == contract_id,
                CoalContractPricing.effective_month == item.effective_month,
            ).first()
            
            if existing:
                existing.coal_price_per_ton = Decimal(str(item.coal_price_per_ton))
                existing.barge_price_per_ton = Decimal(str(item.barge_price_per_ton))
                if item.btu_per_lb:
                    existing.btu_per_lb = Decimal(str(item.btu_per_lb))
                if item.so2_lb_per_mmbtu:
                    existing.so2_lb_per_mmbtu = Decimal(str(item.so2_lb_per_mmbtu))
                results.append({"month": item.effective_month, "status": "updated"})
            else:
                p = CoalContractPricing(
                    contract_id=contract_id,
                    effective_month=item.effective_month,
                    coal_price_per_ton=Decimal(str(item.coal_price_per_ton)),
                    barge_price_per_ton=Decimal(str(item.barge_price_per_ton)),
                    btu_per_lb=Decimal(str(item.btu_per_lb)) if item.btu_per_lb else None,
                    so2_lb_per_mmbtu=Decimal(str(item.so2_lb_per_mmbtu)) if item.so2_lb_per_mmbtu else None,
                )
                db.add(p)
                results.append({"month": item.effective_month, "status": "created"})
        
        db.commit()
        
        return {
            "contract_id": contract_id,
            "updated_count": len(results),
            "results": results,
        }


# =============================================================================
# Uncommitted Coal Price Endpoints
# =============================================================================

@router.get("/uncommitted/{plant_id}/{year}")
async def get_uncommitted_prices(
    plant_id: int,
    year: int,
):
    """Get uncommitted coal prices for a plant and year.
    
    Returns monthly spot market pricing assumptions for forecasting.
    """
    with get_session() as db:
        # Verify plant exists
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail=f"Plant not found: {plant_id}")
        
        prices = db.query(UncommittedCoalPrice).filter(
            UncommittedCoalPrice.plant_id == plant_id,
            UncommittedCoalPrice.year == year,
        ).order_by(UncommittedCoalPrice.month).all()
        
        # Build result with defaults for missing months
        result = {"plant_id": plant_id, "year": year, "months": {}}
        
        price_by_month = {p.month: p for p in prices}
        
        for month in range(1, 13):
            if month in price_by_month:
                p = price_by_month[month]
                result["months"][month] = {
                    "price_per_ton": float(p.price_per_ton),
                    "barge_per_ton": float(p.barge_per_ton),
                    "btu_per_lb": float(p.btu_per_lb),
                    "source_name": p.source_name,
                    "delivered_cost_per_ton": p.delivered_cost_per_ton,
                }
            else:
                # Default values
                result["months"][month] = {
                    "price_per_ton": None,
                    "barge_per_ton": None,
                    "btu_per_lb": None,
                    "source_name": None,
                    "delivered_cost_per_ton": None,
                }
        
        return result


@router.put("/uncommitted/{plant_id}/{year}/{month}", response_model=UncommittedPriceResponse)
async def update_uncommitted_price(
    plant_id: int,
    year: int,
    month: int,
    request: UncommittedPriceUpdateRequest,
):
    """Update uncommitted coal price for a specific month."""
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be 1-12")
    
    with get_session() as db:
        # Verify plant exists
        plant = db.query(Plant).filter(Plant.id == plant_id).first()
        if not plant:
            raise HTTPException(status_code=404, detail=f"Plant not found: {plant_id}")
        
        # Find or create
        existing = db.query(UncommittedCoalPrice).filter(
            UncommittedCoalPrice.plant_id == plant_id,
            UncommittedCoalPrice.year == year,
            UncommittedCoalPrice.month == month,
        ).first()
        
        if existing:
            existing.price_per_ton = Decimal(str(request.price_per_ton))
            existing.barge_per_ton = Decimal(str(request.barge_per_ton))
            existing.btu_per_lb = Decimal(str(request.btu_per_lb))
            existing.source_name = request.source_name
            p = existing
        else:
            p = UncommittedCoalPrice(
                plant_id=plant_id,
                year=year,
                month=month,
                price_per_ton=Decimal(str(request.price_per_ton)),
                barge_per_ton=Decimal(str(request.barge_per_ton)),
                btu_per_lb=Decimal(str(request.btu_per_lb)),
                source_name=request.source_name,
            )
            db.add(p)
        
        db.commit()
        db.refresh(p)
        
        return UncommittedPriceResponse(
            id=p.id,
            plant_id=p.plant_id,
            year=p.year,
            month=p.month,
            price_per_ton=float(p.price_per_ton),
            barge_per_ton=float(p.barge_per_ton),
            btu_per_lb=float(p.btu_per_lb),
            source_name=p.source_name,
            delivered_cost_per_ton=p.delivered_cost_per_ton,
        )


# =============================================================================
# Coal Supply Summary Endpoint
# =============================================================================

@router.get("/supply/{plant_id}/{year}/{month}")
async def get_coal_supply_breakdown(
    plant_id: int,
    year: int,
    month: int,
):
    """Get coal supply breakdown for a plant/month.
    
    Returns:
    - Contracted coal with pricing
    - Uncommitted coal pricing
    - Blended pricing if applicable
    """
    with get_session() as db:
        # Get active contracts for this plant and period
        period_start = date(year, month, 1)
        period_end = date(year, month, 28)  # Approximate end
        
        contracts = db.query(CoalContract).filter(
            CoalContract.plant_id == plant_id,
            CoalContract.is_active == True,
            CoalContract.start_date <= period_end,
            CoalContract.end_date >= period_start,
        ).all()
        
        # Get uncommitted pricing
        uncommitted = db.query(UncommittedCoalPrice).filter(
            UncommittedCoalPrice.plant_id == plant_id,
            UncommittedCoalPrice.year == year,
            UncommittedCoalPrice.month == month,
        ).first()
        
        # Build response
        period_str = f"{year}{month:02d}"
        
        contract_supply = []
        for c in contracts:
            # Check for period-specific pricing
            pricing = db.query(CoalContractPricing).filter(
                CoalContractPricing.contract_id == c.id,
                CoalContractPricing.effective_month == period_str,
            ).first()
            
            if pricing:
                coal_price = float(pricing.coal_price_per_ton)
                barge_price = float(pricing.barge_price_per_ton)
                btu = float(pricing.btu_per_lb) if pricing.btu_per_lb else float(c.btu_per_lb)
            else:
                coal_price = float(c.coal_price_per_ton)
                barge_price = float(c.barge_price_per_ton)
                btu = float(c.btu_per_lb)
            
            contract_supply.append({
                "contract_id": c.contract_id,
                "supplier": c.supplier,
                "annual_tons": float(c.annual_tons),
                "monthly_tons": float(c.annual_tons) / 12,  # Simple monthly allocation
                "coal_price_per_ton": coal_price,
                "barge_price_per_ton": barge_price,
                "delivered_cost_per_ton": coal_price + barge_price,
                "btu_per_lb": btu,
                "coal_region": c.coal_region,
            })
        
        uncommitted_supply = None
        if uncommitted:
            uncommitted_supply = {
                "price_per_ton": float(uncommitted.price_per_ton),
                "barge_per_ton": float(uncommitted.barge_per_ton),
                "delivered_cost_per_ton": uncommitted.delivered_cost_per_ton,
                "btu_per_lb": float(uncommitted.btu_per_lb),
                "source_name": uncommitted.source_name,
            }
        
        return {
            "plant_id": plant_id,
            "year": year,
            "month": month,
            "contracted": contract_supply,
            "uncommitted": uncommitted_supply,
            "total_contracted_monthly_tons": sum(c["monthly_tons"] for c in contract_supply),
        }

