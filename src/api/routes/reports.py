"""Report generation API routes."""

from datetime import datetime
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional

from src.database import get_db
from src.models import Scenario
from src.reports.excel_generator import generate_sponsor_report

router = APIRouter()


@router.get("/sponsor/{scenario_id}")
def generate_sponsor_excel_report(
    scenario_id: int,
    years: int = Query(default=2, ge=1, le=16, description="Number of years to include"),
    include_monthly: bool = Query(default=True, description="Include monthly detail for first 2 years"),
    db: Session = Depends(get_db),
):
    """
    Generate Excel report for sponsors.
    
    - years: Number of years to include (1-16, default 2)
    - include_monthly: Include monthly breakdown for first 2 years
    """
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    # Generate the Excel report
    excel_buffer = generate_sponsor_report(
        db=db,
        scenario_id=scenario_id,
        years=years,
        include_monthly=include_monthly,
    )
    
    # Create filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"OVEC_Forecast_{scenario.name.replace(' ', '_')}_{timestamp}.xlsx"
    
    # Return as downloadable file
    return StreamingResponse(
        excel_buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/comparison")
def generate_comparison_report(
    scenario_ids: str = Query(..., description="Comma-separated scenario IDs"),
    year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Generate comparison report between multiple scenarios."""
    ids = [int(x.strip()) for x in scenario_ids.split(",")]
    
    # Validate scenarios exist
    scenarios = db.query(Scenario).filter(Scenario.id.in_(ids)).all()
    if len(scenarios) != len(ids):
        raise HTTPException(status_code=404, detail="One or more scenarios not found")
    
    # TODO: Implement comparison report
    return {"message": "Comparison report generation not yet implemented", "scenarios": ids}

