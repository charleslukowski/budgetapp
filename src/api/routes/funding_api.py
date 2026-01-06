"""API endpoints for budget amendments and reallocations."""

from typing import List, Dict, Optional
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from src.db.postgres import get_engine, get_session
from src.models.funding import FundingChange

router = APIRouter(prefix="/api/funding", tags=["funding"])


class AmendmentCreate(BaseModel):
    """Request model for creating an amendment."""
    plant_code: str
    year: int
    department: str
    account: Optional[str] = None
    amount: float
    reason: str
    requested_by: Optional[str] = None


class ReallocationCreate(BaseModel):
    """Request model for creating a reallocation."""
    plant_code: str
    year: int
    from_department: str
    from_account: Optional[str] = None
    to_department: str
    to_account: Optional[str] = None
    amount: float
    reason: str
    requested_by: Optional[str] = None


class StatusUpdate(BaseModel):
    """Request model for updating status."""
    status: str  # 'approved' or 'rejected'
    approved_by: Optional[str] = None


@router.get("/changes/{plant_code}/{year}")
async def get_funding_changes(
    plant_code: str, 
    year: int, 
    change_type: Optional[str] = None,
    status: Optional[str] = None
) -> Dict:
    """Get all funding changes for a plant and year."""
    
    engine = get_engine()
    
    with engine.connect() as conn:
        query = """
            SELECT 
                id,
                change_type,
                status,
                department,
                account,
                amount,
                from_department,
                from_account,
                to_department,
                to_account,
                reallocation_amount,
                reason,
                requested_by,
                approved_by,
                created_at,
                approved_at
            FROM funding_changes
            WHERE plant_code = :plant_code AND budget_year = :year
        """
        params = {"plant_code": plant_code, "year": year}
        
        if change_type:
            query += " AND change_type = :change_type"
            params["change_type"] = change_type
        
        if status:
            query += " AND status = :status"
            params["status"] = status
        
        query += " ORDER BY created_at DESC"
        
        result = conn.execute(text(query), params)
        rows = result.fetchall()
    
    changes = []
    for row in rows:
        changes.append({
            "id": row[0],
            "change_type": row[1],
            "status": row[2],
            "department": row[3],
            "account": row[4],
            "amount": float(row[5]) if row[5] else None,
            "from_department": row[6],
            "from_account": row[7],
            "to_department": row[8],
            "to_account": row[9],
            "reallocation_amount": float(row[10]) if row[10] else None,
            "reason": row[11],
            "requested_by": row[12],
            "approved_by": row[13],
            "created_at": row[14].isoformat() if row[14] else None,
            "approved_at": row[15].isoformat() if row[15] else None
        })
    
    # Calculate totals
    amendment_total = sum(c["amount"] or 0 for c in changes if c["change_type"] == "amendment" and c["status"] == "approved")
    reallocation_total = sum(c["reallocation_amount"] or 0 for c in changes if c["change_type"] == "reallocation" and c["status"] == "approved")
    
    return {
        "plant_code": plant_code,
        "year": year,
        "changes": changes,
        "count": len(changes),
        "amendment_total": amendment_total,
        "reallocation_total": reallocation_total
    }


@router.post("/amendments")
async def create_amendment(request: AmendmentCreate) -> Dict:
    """Create a new budget amendment."""
    
    session = get_session()
    
    try:
        new_change = FundingChange(
            plant_code=request.plant_code,
            budget_year=request.year,
            change_type="amendment",
            status="pending",
            department=request.department,
            account=request.account,
            amount=Decimal(str(request.amount)),
            reason=request.reason,
            requested_by=request.requested_by
        )
        session.add(new_change)
        session.commit()
        
        return {
            "success": True,
            "id": new_change.id,
            "message": "Amendment created successfully"
        }
    
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        session.close()


@router.post("/reallocations")
async def create_reallocation(request: ReallocationCreate) -> Dict:
    """Create a new budget reallocation."""
    
    session = get_session()
    
    try:
        new_change = FundingChange(
            plant_code=request.plant_code,
            budget_year=request.year,
            change_type="reallocation",
            status="pending",
            from_department=request.from_department,
            from_account=request.from_account,
            to_department=request.to_department,
            to_account=request.to_account,
            reallocation_amount=Decimal(str(request.amount)),
            reason=request.reason,
            requested_by=request.requested_by
        )
        session.add(new_change)
        session.commit()
        
        return {
            "success": True,
            "id": new_change.id,
            "message": "Reallocation created successfully"
        }
    
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        session.close()


@router.put("/changes/{change_id}/status")
async def update_status(change_id: int, request: StatusUpdate) -> Dict:
    """Update the status of a funding change (approve/reject)."""
    
    if request.status not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Status must be 'approved' or 'rejected'")
    
    session = get_session()
    
    try:
        change = session.query(FundingChange).filter(FundingChange.id == change_id).first()
        
        if not change:
            raise HTTPException(status_code=404, detail="Funding change not found")
        
        change.status = request.status
        change.approved_by = request.approved_by
        
        if request.status == "approved":
            change.approved_at = datetime.now()
        
        session.commit()
        
        return {
            "success": True,
            "id": change_id,
            "status": request.status,
            "message": f"Status updated to {request.status}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        session.close()


@router.delete("/changes/{change_id}")
async def delete_funding_change(change_id: int) -> Dict:
    """Delete a funding change (only if pending)."""
    
    session = get_session()
    
    try:
        change = session.query(FundingChange).filter(FundingChange.id == change_id).first()
        
        if not change:
            raise HTTPException(status_code=404, detail="Funding change not found")
        
        if change.status != "pending":
            raise HTTPException(status_code=400, detail="Can only delete pending changes")
        
        session.delete(change)
        session.commit()
        
        return {
            "success": True,
            "message": "Funding change deleted"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        session.close()

