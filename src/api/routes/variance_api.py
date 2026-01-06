"""API endpoints for saving and retrieving variance explanations."""

from typing import List, Dict, Optional
from decimal import Decimal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from src.db.postgres import get_engine, get_session
from src.models.funding import VarianceExplanation

router = APIRouter(prefix="/api/variance", tags=["variance"])


class ExplanationData(BaseModel):
    """Request model for a single explanation."""
    dept_code: str
    period_month: int  # 0 for YTD, 1-12 for monthly
    explanation: str
    variance_amount: Optional[float] = None


class ExplanationsSaveRequest(BaseModel):
    """Request model for saving multiple explanations."""
    plant_code: str
    year: int
    explanations: List[ExplanationData]
    created_by: Optional[str] = None


@router.get("/explanations/{plant_code}/{year}")
async def get_explanations(plant_code: str, year: int, month: Optional[int] = None) -> Dict:
    """Get all variance explanations for a plant and year."""
    
    engine = get_engine()
    
    with engine.connect() as conn:
        if month is not None:
            query = text("""
                SELECT 
                    dept_code,
                    period_month,
                    explanation,
                    variance_amount,
                    created_by,
                    updated_at
                FROM variance_explanations
                WHERE plant_code = :plant_code 
                  AND budget_year = :year
                  AND period_month = :month
                ORDER BY dept_code
            """)
            result = conn.execute(query, {"plant_code": plant_code, "year": year, "month": month})
        else:
            query = text("""
                SELECT 
                    dept_code,
                    period_month,
                    explanation,
                    variance_amount,
                    created_by,
                    updated_at
                FROM variance_explanations
                WHERE plant_code = :plant_code AND budget_year = :year
                ORDER BY dept_code, period_month
            """)
            result = conn.execute(query, {"plant_code": plant_code, "year": year})
        
        rows = result.fetchall()
    
    explanations = []
    for row in rows:
        explanations.append({
            "dept_code": row[0],
            "period_month": row[1],
            "explanation": row[2],
            "variance_amount": float(row[3]) if row[3] else None,
            "created_by": row[4],
            "updated_at": row[5].isoformat() if row[5] else None
        })
    
    return {
        "plant_code": plant_code,
        "year": year,
        "month": month,
        "explanations": explanations,
        "count": len(explanations)
    }


@router.post("/explanations/{plant_code}/{year}")
async def save_explanations(plant_code: str, year: int, request: ExplanationsSaveRequest) -> Dict:
    """Save variance explanations for multiple departments."""
    
    if request.plant_code != plant_code or request.year != year:
        raise HTTPException(status_code=400, detail="Plant code or year mismatch")
    
    session = get_session()
    saved_count = 0
    
    try:
        for expl_data in request.explanations:
            # Check if explanation exists
            existing = session.query(VarianceExplanation).filter(
                VarianceExplanation.plant_code == plant_code,
                VarianceExplanation.dept_code == expl_data.dept_code,
                VarianceExplanation.budget_year == year,
                VarianceExplanation.period_month == expl_data.period_month
            ).first()
            
            if existing:
                # Update existing
                existing.explanation = expl_data.explanation
                if expl_data.variance_amount is not None:
                    existing.variance_amount = Decimal(str(expl_data.variance_amount))
            else:
                # Create new
                new_expl = VarianceExplanation(
                    plant_code=plant_code,
                    dept_code=expl_data.dept_code,
                    budget_year=year,
                    period_month=expl_data.period_month,
                    explanation=expl_data.explanation,
                    variance_amount=Decimal(str(expl_data.variance_amount)) if expl_data.variance_amount else None,
                    created_by=request.created_by
                )
                session.add(new_expl)
            
            saved_count += 1
        
        session.commit()
        
        return {
            "success": True,
            "message": f"Saved {saved_count} explanations",
            "plant_code": plant_code,
            "year": year,
            "count": saved_count
        }
    
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        session.close()


@router.delete("/explanations/{plant_code}/{year}/{dept_code}")
async def delete_explanation(plant_code: str, year: int, dept_code: str, month: int = 0) -> Dict:
    """Delete a specific explanation."""
    
    session = get_session()
    
    try:
        deleted = session.query(VarianceExplanation).filter(
            VarianceExplanation.plant_code == plant_code,
            VarianceExplanation.dept_code == dept_code,
            VarianceExplanation.budget_year == year,
            VarianceExplanation.period_month == month
        ).delete()
        
        session.commit()
        
        return {
            "success": True,
            "deleted": deleted > 0
        }
    
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        session.close()

