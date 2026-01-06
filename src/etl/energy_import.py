"""ETL pipeline for importing GLDetailsEnergy (fuel cost actuals).

Imports transactional fuel cost data including:
- Coal costs
- Fuel oil costs
- Reagent costs (limestone, urea, lime, mercury control)
- Byproduct sales/disposal (gypsum, ash)
"""

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Optional, Generator
import logging

from sqlalchemy.orm import Session

from src.models.actuals import EnergyActual
from src.etl.account_mapping import parse_gl_account, get_plant_id_from_code

logger = logging.getLogger(__name__)


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string from various formats."""
    if not date_str or date_str.strip() == "":
        return None
    
    # Try common formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    
    return None


def parse_amount(amount_str: str) -> Decimal:
    """Parse amount string to Decimal."""
    if not amount_str or amount_str.strip() == "":
        return Decimal("0")
    
    try:
        # Remove commas and handle negative numbers
        cleaned = amount_str.strip().replace(",", "")
        return Decimal(cleaned)
    except Exception:
        return Decimal("0")


def get_plant_id_from_budget(budget_entity: str) -> Optional[int]:
    """Get plant ID from budget entity string."""
    if not budget_entity:
        return None
    
    budget_lower = budget_entity.lower().strip()
    if budget_lower == "kyger":
        return 1
    elif budget_lower == "clifty":
        return 2
    # System and EO don't map to a specific plant
    return None


def row_to_energy_actual(row: Dict) -> EnergyActual:
    """Convert a CSV row to an EnergyActual model instance.
    
    Args:
        row: Dictionary from CSV reader
        
    Returns:
        EnergyActual instance
    """
    # Parse GL account for additional info
    gl_account = row.get("GXACCT", "").strip()
    parsed = parse_gl_account(gl_account)
    
    # Determine plant ID
    budget_entity = row.get("BUDGET", "").strip()
    plant_id = get_plant_id_from_budget(budget_entity)
    
    # If not from BUDGET field, try from GL account
    if plant_id is None and parsed:
        plant_id = get_plant_id_from_code(parsed.plant_code)
    
    # Parse transaction date
    trans_date = parse_date(row.get("X1TRANSDATE", ""))
    
    return EnergyActual(
        gl_detail_id=row.get("GLDetailExpenseID", "").strip() or None,
        journal=row.get("GXJRNL", "").strip() or None,
        period_yyyymm=row.get("YYYYMM", "").strip(),
        gl_account=gl_account,
        account_description=row.get("CTDESC", "").strip()[:100] if row.get("CTDESC") else None,
        plant_id=plant_id,
        budget_entity=budget_entity or None,
        amount=parse_amount(row.get("GXFAMT", "0")),
        debit_credit=row.get("GXDRCR", "").strip()[:1] or None,
        cost_group=row.get("GROUP", "").strip() or None,
        cost_type=row.get("TYPE", "").strip() or None,
        labor_nonlabor=row.get("LABOR-NONLABOR", "").strip() or None,
        description=row.get("GXDESC", "").strip()[:100] if row.get("GXDESC") else None,
        description2=row.get("GXDSC2", "").strip()[:200] if row.get("GXDSC2") else None,
        trans_date=trans_date.date() if trans_date else None,
        work_order=row.get("X1WORKORDER", "").strip()[:30] if row.get("X1WORKORDER") else None,
        po_number=row.get("X1PONUM", "").strip()[:30] if row.get("X1PONUM") else None,
        project_id=row.get("X1PROJECTID", "").strip()[:30] if row.get("X1PROJECTID") else None,
        project_desc=row.get("PROJ_DESC", "").strip()[:100] if row.get("PROJ_DESC") else None,
        vendor_id=row.get("X1VENDOR", "").strip()[:20] if row.get("X1VENDOR") else None,
        vendor_name=row.get("X1VENDORNAME", "").strip()[:100] if row.get("X1VENDORNAME") else None,
    )


def read_energy_csv(file_path: Path) -> Generator[Dict, None, None]:
    """Read GLDetailsEnergy CSV file and yield rows.
    
    Args:
        file_path: Path to CSV file
        
    Yields:
        Dictionary for each row
    """
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def import_energy_actuals(
    db: Session,
    file_path: Path,
    clear_existing: bool = False,
    period_filter: str = None,
) -> Dict:
    """Import energy actuals from GLDetailsEnergy CSV.
    
    Args:
        db: Database session
        file_path: Path to CSV file
        clear_existing: If True, delete existing records first
        period_filter: Optional YYYYMM to filter import
        
    Returns:
        Dictionary with import statistics
    """
    stats = {
        "total_rows": 0,
        "imported": 0,
        "skipped": 0,
        "errors": 0,
        "total_amount": Decimal("0"),
    }
    
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    logger.info(f"Importing energy actuals from {file_path}")
    
    # Optionally clear existing records
    if clear_existing:
        if period_filter:
            db.query(EnergyActual).filter(
                EnergyActual.period_yyyymm == period_filter
            ).delete()
        else:
            db.query(EnergyActual).delete()
        db.commit()
        logger.info("Cleared existing energy actuals")
    
    # Import rows in batches
    batch_size = 1000
    batch = []
    
    for row in read_energy_csv(file_path):
        stats["total_rows"] += 1
        
        # Apply period filter if specified
        if period_filter and row.get("YYYYMM", "").strip() != period_filter:
            stats["skipped"] += 1
            continue
        
        try:
            actual = row_to_energy_actual(row)
            batch.append(actual)
            stats["total_amount"] += actual.amount
            stats["imported"] += 1
            
            # Commit batch
            if len(batch) >= batch_size:
                db.bulk_save_objects(batch)
                db.commit()
                batch = []
                logger.info(f"Imported {stats['imported']} rows...")
                
        except Exception as e:
            stats["errors"] += 1
            logger.warning(f"Error importing row {stats['total_rows']}: {e}")
    
    # Final batch
    if batch:
        db.bulk_save_objects(batch)
        db.commit()
    
    logger.info(f"Import complete: {stats['imported']} rows, total amount: ${stats['total_amount']:,.2f}")
    return stats


def get_energy_summary_by_group(db: Session, period_yyyymm: str) -> List[Dict]:
    """Get summary of energy costs by cost group for a period.
    
    Args:
        db: Database session
        period_yyyymm: Period in YYYYMM format
        
    Returns:
        List of dictionaries with group summaries
    """
    from sqlalchemy import func
    
    results = db.query(
        EnergyActual.cost_group,
        EnergyActual.budget_entity,
        func.sum(EnergyActual.amount).label("total_amount"),
        func.count(EnergyActual.id).label("transaction_count"),
    ).filter(
        EnergyActual.period_yyyymm == period_yyyymm
    ).group_by(
        EnergyActual.cost_group,
        EnergyActual.budget_entity,
    ).order_by(
        EnergyActual.budget_entity,
        EnergyActual.cost_group,
    ).all()
    
    return [
        {
            "cost_group": r.cost_group,
            "plant": r.budget_entity,
            "total_amount": float(r.total_amount),
            "transaction_count": r.transaction_count,
        }
        for r in results
    ]

