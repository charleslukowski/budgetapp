"""
Fuel model import API endpoints.

Provides endpoints for importing fuel model inputs from Excel files:
- Use factors
- Heat rates
- Coal contracts
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from pathlib import Path
import tempfile
import os

from src.db.postgres import get_session
from src.etl.fuel_inputs_import import (
    import_use_factors_from_excel,
    import_heat_rates_from_excel,
    import_coal_contracts_from_excel,
    import_all_fuel_inputs,
)


router = APIRouter(prefix="/api/import", tags=["Import"])


@router.post("/use-factors/{plant_id}/{year}")
async def upload_use_factors(
    plant_id: int,
    year: int,
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Form("Use Factor Input"),
):
    """Import use factors from an uploaded Excel file.
    
    Args:
        plant_id: Plant ID (1=Kyger, 2=Clifty)
        year: Year to import for
        file: Excel file to import
        sheet_name: Name of sheet containing use factors
        
    Returns:
        Import results including count and any errors
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File must be an Excel file (.xlsx or .xls)")
    
    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        with get_session() as db:
            result = import_use_factors_from_excel(
                db,
                file_path=tmp_path,
                plant_id=plant_id,
                year=year,
                sheet_name=sheet_name,
            )
            
            if result["errors"]:
                return {
                    "status": "partial",
                    "message": f"Imported {result['months_imported']} months with {len(result['errors'])} errors",
                    "months_imported": result["months_imported"],
                    "errors": result["errors"],
                }
            
            return {
                "status": "success",
                "message": f"Successfully imported {result['months_imported']} months of use factors",
                "months_imported": result["months_imported"],
            }
    finally:
        os.unlink(tmp_path)


@router.post("/heat-rates/{plant_id}/{year}")
async def upload_heat_rates(
    plant_id: int,
    year: int,
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Form("Heat Rate"),
):
    """Import heat rates from an uploaded Excel file.
    
    Args:
        plant_id: Plant ID (1=Kyger, 2=Clifty)
        year: Year to import for
        file: Excel file to import
        sheet_name: Name of sheet containing heat rates
        
    Returns:
        Import results including count and any errors
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File must be an Excel file (.xlsx or .xls)")
    
    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        with get_session() as db:
            result = import_heat_rates_from_excel(
                db,
                file_path=tmp_path,
                plant_id=plant_id,
                year=year,
                sheet_name=sheet_name,
            )
            
            if result["errors"]:
                return {
                    "status": "partial",
                    "message": f"Imported {result['months_imported']} months with {len(result['errors'])} errors",
                    "months_imported": result["months_imported"],
                    "errors": result["errors"],
                }
            
            return {
                "status": "success",
                "message": f"Successfully imported {result['months_imported']} months of heat rates",
                "months_imported": result["months_imported"],
            }
    finally:
        os.unlink(tmp_path)


@router.post("/coal-contracts")
async def upload_coal_contracts(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Form("Coal Contracts Annual View"),
):
    """Import coal contracts from an uploaded Excel file.
    
    Args:
        file: Excel file to import
        sheet_name: Name of sheet containing contracts
        
    Returns:
        Import results including count and any errors
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File must be an Excel file (.xlsx or .xls)")
    
    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        with get_session() as db:
            result = import_coal_contracts_from_excel(
                db,
                file_path=tmp_path,
                sheet_name=sheet_name,
            )
            
            total_processed = result["contracts_imported"] + result["contracts_updated"]
            
            if result["errors"]:
                return {
                    "status": "partial",
                    "message": f"Processed {total_processed} contracts with {len(result['errors'])} errors",
                    "contracts_imported": result["contracts_imported"],
                    "contracts_updated": result["contracts_updated"],
                    "errors": result["errors"],
                }
            
            return {
                "status": "success",
                "message": f"Successfully processed {total_processed} contracts",
                "contracts_imported": result["contracts_imported"],
                "contracts_updated": result["contracts_updated"],
            }
    finally:
        os.unlink(tmp_path)


@router.post("/fuel-model/{year}")
async def upload_full_fuel_model(
    year: int,
    file: UploadFile = File(...),
):
    """Import all fuel model inputs from a single Excel file.
    
    Attempts to import:
    - Use factors for both plants
    - Heat rates for both plants
    - Coal contracts
    
    Args:
        year: Year to import for
        file: Excel file to import
        
    Returns:
        Combined import results for all components
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File must be an Excel file (.xlsx or .xls)")
    
    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        with get_session() as db:
            result = import_all_fuel_inputs(
                db,
                file_path=tmp_path,
                year=year,
            )
            
            summary = result["summary"]
            
            # Collect all errors
            all_errors = []
            for key in ["use_factors", "heat_rates"]:
                if key in result:
                    for plant, plant_result in result[key].items():
                        if plant_result.get("errors"):
                            all_errors.extend([f"{key}/{plant}: {e}" for e in plant_result["errors"]])
            if result["contracts"].get("errors"):
                all_errors.extend([f"contracts: {e}" for e in result["contracts"]["errors"]])
            
            status = "success" if not all_errors else "partial"
            
            return {
                "status": status,
                "message": (
                    f"Imported {summary['use_factors_imported']} use factors, "
                    f"{summary['heat_rates_imported']} heat rates, "
                    f"{summary['contracts_imported']} new + {summary['contracts_updated']} updated contracts"
                ),
                "summary": summary,
                "errors": all_errors if all_errors else None,
            }
    finally:
        os.unlink(tmp_path)

