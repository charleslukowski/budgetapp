"""API endpoints for budget entry and approval workflow."""

from typing import List, Dict, Optional
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from src.db.postgres import get_engine, get_session
from src.models.funding import BudgetSubmission, BudgetEntry, DepartmentForecast

router = APIRouter(prefix="/api/budget-entry", tags=["budget-entry"])


class BudgetLineData(BaseModel):
    """Request model for a single budget line."""
    account_code: Optional[str] = None
    account_name: Optional[str] = None
    line_description: Optional[str] = None
    months: List[float]  # 12 monthly values
    notes: Optional[str] = None


class BudgetEntrySaveRequest(BaseModel):
    """Request model for saving budget entries."""
    plant_code: str
    dept_code: str
    year: int
    entries: List[BudgetLineData]
    updated_by: Optional[str] = None


class SubmitRequest(BaseModel):
    """Request model for submitting budget."""
    submitted_by: Optional[str] = None


class ApprovalRequest(BaseModel):
    """Request model for approving/rejecting budget."""
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None


@router.get("/{plant_code}/{year}")
async def get_budget_entries(plant_code: str, year: int, dept_code: Optional[str] = None) -> Dict:
    """Get budget entries for a plant/year, optionally filtered by department."""
    
    engine = get_engine()
    
    with engine.connect() as conn:
        # Get submissions
        sub_query = """
            SELECT id, plant_code, dept_code, budget_year, status,
                   submitted_at, submitted_by, approved_at, approved_by, rejection_reason
            FROM budget_submissions
            WHERE plant_code = :plant_code AND budget_year = :year
        """
        params = {"plant_code": plant_code, "year": year}
        
        if dept_code:
            sub_query += " AND dept_code = :dept_code"
            params["dept_code"] = dept_code
        
        sub_query += " ORDER BY dept_code"
        
        sub_result = conn.execute(text(sub_query), params)
        submissions = sub_result.fetchall()
        
        # Get entries for each submission
        result_data = []
        for sub in submissions:
            entry_query = text("""
                SELECT id, account_code, account_name, line_description,
                       jan, feb, mar, apr, may, jun, jul, aug, sep, oct, nov, dec, total, notes
                FROM budget_entries
                WHERE submission_id = :submission_id
                ORDER BY account_code
            """)
            entry_result = conn.execute(entry_query, {"submission_id": sub[0]})
            entries = entry_result.fetchall()
            
            entry_list = []
            for entry in entries:
                months = [float(entry[i]) if entry[i] else 0 for i in range(4, 16)]
                entry_list.append({
                    "id": entry[0],
                    "account_code": entry[1],
                    "account_name": entry[2],
                    "line_description": entry[3],
                    "months": months,
                    "total": float(entry[16]) if entry[16] else 0,
                    "notes": entry[17]
                })
            
            result_data.append({
                "submission_id": sub[0],
                "plant_code": sub[1],
                "dept_code": sub[2],
                "budget_year": sub[3],
                "status": sub[4],
                "submitted_at": sub[5].isoformat() if sub[5] else None,
                "submitted_by": sub[6],
                "approved_at": sub[7].isoformat() if sub[7] else None,
                "approved_by": sub[8],
                "rejection_reason": sub[9],
                "entries": entry_list,
                "total": sum(e["total"] for e in entry_list)
            })
    
    return {
        "plant_code": plant_code,
        "year": year,
        "dept_code": dept_code,
        "submissions": result_data,
        "count": len(result_data)
    }


@router.post("/{plant_code}/{year}")
async def save_budget_entries(plant_code: str, year: int, request: BudgetEntrySaveRequest) -> Dict:
    """Save budget entries (creates or updates draft)."""
    
    if request.plant_code != plant_code or request.year != year:
        raise HTTPException(status_code=400, detail="Plant code or year mismatch")
    
    session = get_session()
    
    try:
        # Find or create submission
        submission = session.query(BudgetSubmission).filter(
            BudgetSubmission.plant_code == plant_code,
            BudgetSubmission.dept_code == request.dept_code,
            BudgetSubmission.budget_year == year
        ).first()
        
        if submission:
            # Check if editable
            if submission.status not in ['draft', 'rejected']:
                raise HTTPException(status_code=400, detail=f"Budget is {submission.status} and cannot be edited")
            
            # If rejected, reset to draft
            if submission.status == 'rejected':
                submission.status = 'draft'
                submission.rejection_reason = None
        else:
            # Create new submission
            submission = BudgetSubmission(
                plant_code=plant_code,
                dept_code=request.dept_code,
                budget_year=year,
                status='draft'
            )
            session.add(submission)
            session.flush()  # Get the ID
        
        # Delete existing entries and recreate
        session.query(BudgetEntry).filter(
            BudgetEntry.submission_id == submission.id
        ).delete()
        
        # Add new entries
        for entry_data in request.entries:
            if len(entry_data.months) != 12:
                raise HTTPException(status_code=400, detail="Expected 12 months per entry")
            
            entry = BudgetEntry(
                submission_id=submission.id,
                plant_code=plant_code,
                dept_code=request.dept_code,
                budget_year=year,
                account_code=entry_data.account_code,
                account_name=entry_data.account_name,
                line_description=entry_data.line_description,
                jan=Decimal(str(entry_data.months[0])),
                feb=Decimal(str(entry_data.months[1])),
                mar=Decimal(str(entry_data.months[2])),
                apr=Decimal(str(entry_data.months[3])),
                may=Decimal(str(entry_data.months[4])),
                jun=Decimal(str(entry_data.months[5])),
                jul=Decimal(str(entry_data.months[6])),
                aug=Decimal(str(entry_data.months[7])),
                sep=Decimal(str(entry_data.months[8])),
                oct=Decimal(str(entry_data.months[9])),
                nov=Decimal(str(entry_data.months[10])),
                dec=Decimal(str(entry_data.months[11])),
                total=Decimal(str(sum(entry_data.months))),
                notes=entry_data.notes
            )
            session.add(entry)
        
        session.commit()
        
        return {
            "success": True,
            "submission_id": submission.id,
            "status": submission.status,
            "message": f"Saved {len(request.entries)} budget entries"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/{plant_code}/{year}/submit")
async def submit_budget(plant_code: str, year: int, dept_code: str, request: SubmitRequest) -> Dict:
    """Submit budget for approval."""
    
    session = get_session()
    
    try:
        submission = session.query(BudgetSubmission).filter(
            BudgetSubmission.plant_code == plant_code,
            BudgetSubmission.dept_code == dept_code,
            BudgetSubmission.budget_year == year
        ).first()
        
        if not submission:
            raise HTTPException(status_code=404, detail="Budget submission not found")
        
        if submission.status not in ['draft', 'rejected']:
            raise HTTPException(status_code=400, detail=f"Budget is {submission.status} and cannot be submitted")
        
        submission.status = 'submitted'
        submission.submitted_at = datetime.now()
        submission.submitted_by = request.submitted_by
        submission.rejection_reason = None
        
        session.commit()
        
        return {
            "success": True,
            "submission_id": submission.id,
            "status": "submitted",
            "message": "Budget submitted for approval"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/submissions/{plant_code}/{year}")
async def get_submissions(plant_code: str, year: int, status: Optional[str] = None) -> Dict:
    """Get all budget submissions for manager view."""
    
    engine = get_engine()
    
    with engine.connect() as conn:
        query = """
            SELECT s.id, s.plant_code, s.dept_code, s.budget_year, s.status,
                   s.submitted_at, s.submitted_by, s.approved_at, s.approved_by, s.rejection_reason,
                   COALESCE(SUM(e.total), 0) as total_budget,
                   COUNT(e.id) as entry_count
            FROM budget_submissions s
            LEFT JOIN budget_entries e ON e.submission_id = s.id
            WHERE s.plant_code = :plant_code AND s.budget_year = :year
        """
        params = {"plant_code": plant_code, "year": year}
        
        if status:
            query += " AND s.status = :status"
            params["status"] = status
        
        query += " GROUP BY s.id ORDER BY s.dept_code"
        
        result = conn.execute(text(query), params)
        rows = result.fetchall()
    
    submissions = []
    for row in rows:
        submissions.append({
            "id": row[0],
            "plant_code": row[1],
            "dept_code": row[2],
            "budget_year": row[3],
            "status": row[4],
            "submitted_at": row[5].isoformat() if row[5] else None,
            "submitted_by": row[6],
            "approved_at": row[7].isoformat() if row[7] else None,
            "approved_by": row[8],
            "rejection_reason": row[9],
            "total_budget": float(row[10]) if row[10] else 0,
            "entry_count": row[11]
        })
    
    # Summary stats
    total_budget = sum(s["total_budget"] for s in submissions)
    by_status = {}
    for s in submissions:
        by_status[s["status"]] = by_status.get(s["status"], 0) + 1
    
    return {
        "plant_code": plant_code,
        "year": year,
        "submissions": submissions,
        "count": len(submissions),
        "total_budget": total_budget,
        "by_status": by_status
    }


@router.post("/submissions/{submission_id}/approve")
async def approve_budget(submission_id: int, request: ApprovalRequest) -> Dict:
    """Approve a budget submission and copy to forecast."""
    
    session = get_session()
    
    try:
        submission = session.query(BudgetSubmission).filter(
            BudgetSubmission.id == submission_id
        ).first()
        
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        
        if submission.status != 'submitted':
            raise HTTPException(status_code=400, detail=f"Budget is {submission.status}, can only approve submitted budgets")
        
        # Update submission status
        submission.status = 'approved'
        submission.approved_at = datetime.now()
        submission.approved_by = request.approved_by
        
        # Copy budget entries to department forecast
        # First, delete any existing forecast for this dept/year
        session.query(DepartmentForecast).filter(
            DepartmentForecast.plant_code == submission.plant_code,
            DepartmentForecast.dept_code == submission.dept_code,
            DepartmentForecast.budget_year == submission.budget_year
        ).delete()
        
        # Get total of all entries for this submission
        entries = session.query(BudgetEntry).filter(
            BudgetEntry.submission_id == submission.id
        ).all()
        
        # Aggregate entries into single forecast row
        forecast = DepartmentForecast(
            plant_code=submission.plant_code,
            dept_code=submission.dept_code,
            budget_year=submission.budget_year,
            jan=sum(Decimal(str(e.jan or 0)) for e in entries),
            feb=sum(Decimal(str(e.feb or 0)) for e in entries),
            mar=sum(Decimal(str(e.mar or 0)) for e in entries),
            apr=sum(Decimal(str(e.apr or 0)) for e in entries),
            may=sum(Decimal(str(e.may or 0)) for e in entries),
            jun=sum(Decimal(str(e.jun or 0)) for e in entries),
            jul=sum(Decimal(str(e.jul or 0)) for e in entries),
            aug=sum(Decimal(str(e.aug or 0)) for e in entries),
            sep=sum(Decimal(str(e.sep or 0)) for e in entries),
            oct=sum(Decimal(str(e.oct or 0)) for e in entries),
            nov=sum(Decimal(str(e.nov or 0)) for e in entries),
            dec=sum(Decimal(str(e.dec or 0)) for e in entries),
            updated_by=request.approved_by
        )
        forecast.total = sum([
            forecast.jan or 0, forecast.feb or 0, forecast.mar or 0, forecast.apr or 0,
            forecast.may or 0, forecast.jun or 0, forecast.jul or 0, forecast.aug or 0,
            forecast.sep or 0, forecast.oct or 0, forecast.nov or 0, forecast.dec or 0,
        ])
        
        session.add(forecast)
        session.commit()
        
        return {
            "success": True,
            "submission_id": submission_id,
            "status": "approved",
            "message": "Budget approved and copied to forecast",
            "forecast_total": float(forecast.total)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/submissions/{submission_id}/reject")
async def reject_budget(submission_id: int, request: ApprovalRequest) -> Dict:
    """Reject a budget submission."""
    
    session = get_session()
    
    try:
        submission = session.query(BudgetSubmission).filter(
            BudgetSubmission.id == submission_id
        ).first()
        
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        
        if submission.status != 'submitted':
            raise HTTPException(status_code=400, detail=f"Budget is {submission.status}, can only reject submitted budgets")
        
        submission.status = 'rejected'
        submission.approved_by = request.approved_by  # Person who rejected
        submission.rejection_reason = request.rejection_reason
        
        session.commit()
        
        return {
            "success": True,
            "submission_id": submission_id,
            "status": "rejected",
            "message": "Budget rejected"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()

