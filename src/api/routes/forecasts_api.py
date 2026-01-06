"""API endpoints for saving and retrieving department forecasts."""

from typing import List, Dict, Optional
from decimal import Decimal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from src.db.postgres import get_engine, get_session
from src.models.funding import DepartmentForecast

router = APIRouter(prefix="/api/forecasts", tags=["forecasts"])


class ForecastData(BaseModel):
    """Request model for forecast data."""
    dept_code: str
    months: List[float]  # 12 monthly values


class ForecastSaveRequest(BaseModel):
    """Request model for saving forecasts."""
    plant_code: str
    year: int
    forecasts: List[ForecastData]
    updated_by: Optional[str] = None


class ForecastResponse(BaseModel):
    """Response model for forecast data."""
    dept_code: str
    months: List[float]
    total: float


@router.get("/{plant_code}/{year}")
async def get_forecasts(plant_code: str, year: int) -> Dict:
    """Get all saved forecasts for a plant and year."""
    
    engine = get_engine()
    
    with engine.connect() as conn:
        query = text("""
            SELECT 
                dept_code,
                jan, feb, mar, apr, may, jun,
                jul, aug, sep, oct, nov, dec,
                total,
                updated_at,
                updated_by
            FROM department_forecasts
            WHERE plant_code = :plant_code AND budget_year = :year
            ORDER BY dept_code
        """)
        result = conn.execute(query, {"plant_code": plant_code, "year": year})
        rows = result.fetchall()
    
    forecasts = []
    for row in rows:
        months = [float(row[i]) if row[i] else 0 for i in range(1, 13)]
        forecasts.append({
            "dept_code": row[0],
            "months": months,
            "total": float(row[13]) if row[13] else 0,
            "updated_at": row[14].isoformat() if row[14] else None,
            "updated_by": row[15]
        })
    
    return {
        "plant_code": plant_code,
        "year": year,
        "forecasts": forecasts,
        "count": len(forecasts)
    }


@router.post("/{plant_code}/{year}")
async def save_forecasts(plant_code: str, year: int, request: ForecastSaveRequest) -> Dict:
    """Save forecast data for multiple departments."""
    
    if request.plant_code != plant_code or request.year != year:
        raise HTTPException(status_code=400, detail="Plant code or year mismatch")
    
    session = get_session()
    saved_count = 0
    
    try:
        for forecast_data in request.forecasts:
            if len(forecast_data.months) != 12:
                raise HTTPException(status_code=400, detail=f"Expected 12 months for {forecast_data.dept_code}")
            
            # Check if forecast exists
            existing = session.query(DepartmentForecast).filter(
                DepartmentForecast.plant_code == plant_code,
                DepartmentForecast.dept_code == forecast_data.dept_code,
                DepartmentForecast.budget_year == year
            ).first()
            
            if existing:
                # Update existing
                existing.jan = Decimal(str(forecast_data.months[0]))
                existing.feb = Decimal(str(forecast_data.months[1]))
                existing.mar = Decimal(str(forecast_data.months[2]))
                existing.apr = Decimal(str(forecast_data.months[3]))
                existing.may = Decimal(str(forecast_data.months[4]))
                existing.jun = Decimal(str(forecast_data.months[5]))
                existing.jul = Decimal(str(forecast_data.months[6]))
                existing.aug = Decimal(str(forecast_data.months[7]))
                existing.sep = Decimal(str(forecast_data.months[8]))
                existing.oct = Decimal(str(forecast_data.months[9]))
                existing.nov = Decimal(str(forecast_data.months[10]))
                existing.dec = Decimal(str(forecast_data.months[11]))
                existing.total = Decimal(str(sum(forecast_data.months)))
                existing.updated_by = request.updated_by
            else:
                # Create new
                new_forecast = DepartmentForecast(
                    plant_code=plant_code,
                    dept_code=forecast_data.dept_code,
                    budget_year=year,
                    jan=Decimal(str(forecast_data.months[0])),
                    feb=Decimal(str(forecast_data.months[1])),
                    mar=Decimal(str(forecast_data.months[2])),
                    apr=Decimal(str(forecast_data.months[3])),
                    may=Decimal(str(forecast_data.months[4])),
                    jun=Decimal(str(forecast_data.months[5])),
                    jul=Decimal(str(forecast_data.months[6])),
                    aug=Decimal(str(forecast_data.months[7])),
                    sep=Decimal(str(forecast_data.months[8])),
                    oct=Decimal(str(forecast_data.months[9])),
                    nov=Decimal(str(forecast_data.months[10])),
                    dec=Decimal(str(forecast_data.months[11])),
                    total=Decimal(str(sum(forecast_data.months))),
                    updated_by=request.updated_by
                )
                session.add(new_forecast)
            
            saved_count += 1
        
        session.commit()
        
        return {
            "success": True,
            "message": f"Saved {saved_count} forecasts",
            "plant_code": plant_code,
            "year": year,
            "count": saved_count
        }
    
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        session.close()


@router.delete("/{plant_code}/{year}/{dept_code}")
async def delete_forecast(plant_code: str, year: int, dept_code: str) -> Dict:
    """Delete a specific forecast."""
    
    session = get_session()
    
    try:
        deleted = session.query(DepartmentForecast).filter(
            DepartmentForecast.plant_code == plant_code,
            DepartmentForecast.dept_code == dept_code,
            DepartmentForecast.budget_year == year
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

