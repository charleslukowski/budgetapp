"""ETL pipeline for importing GLDetailsExpense (O&M cost actuals).

Imports transactional O&M expense data including:
- Maintenance costs
- Operations costs
- Environmental costs
- Outage costs (planned and unplanned)
"""

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Optional, Generator
import logging

from sqlalchemy.orm import Session

from src.models.actuals import ExpenseActual
from src.etl.account_mapping import parse_gl_account, get_plant_id_from_code

logger = logging.getLogger(__name__)


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string from various formats."""
    if not date_str or date_str.strip() == "":
        return None
    
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
    return None


def row_to_expense_actual(row: Dict) -> ExpenseActual:
    """Convert a CSV row to an ExpenseActual model instance.
    
    Args:
        row: Dictionary from CSV reader
        
    Returns:
        ExpenseActual instance
    """
    gl_account = row.get("GXACCT", "").strip()
    parsed = parse_gl_account(gl_account)
    
    budget_entity = row.get("BUDGET", "").strip()
    plant_id = get_plant_id_from_budget(budget_entity)
    
    if plant_id is None and parsed:
        plant_id = get_plant_id_from_code(parsed.plant_code)
    
    trans_date = parse_date(row.get("X1TRANSDATE", ""))
    
    return ExpenseActual(
        gl_detail_id=row.get("GLDetailExpenseID", "").strip() or None,
        journal=row.get("GXJRNL", "").strip() or None,
        period_yyyymm=row.get("YYYYMM", "").strip(),
        gl_account=gl_account,
        account_description=row.get("CTDESC", "").strip()[:100] if row.get("CTDESC") else None,
        plant_id=plant_id,
        budget_entity=budget_entity or None,
        amount=parse_amount(row.get("GXFAMT", "0")),
        debit_credit=row.get("GXDRCR", "").strip()[:1] or None,
        department=row.get("GROUP", "").strip() or None,
        cost_type=row.get("TYPE", "").strip() or None,
        labor_nonlabor=row.get("LABOR-NONLABOR", "").strip() or None,
        outage_unit=row.get("OUTAGE UNIT", "").strip()[:10] if row.get("OUTAGE UNIT") else None,
        description=row.get("GXDESC", "").strip()[:100] if row.get("GXDESC") else None,
        description2=row.get("GXDSC2", "").strip()[:200] if row.get("GXDSC2") else None,
        trans_date=trans_date.date() if trans_date else None,
        work_order=row.get("X1WORKORDER", "").strip()[:30] if row.get("X1WORKORDER") else None,
        po_number=row.get("X1PONUM", "").strip()[:30] if row.get("X1PONUM") else None,
        project_id=row.get("X1PROJECTID", "").strip()[:30] if row.get("X1PROJECTID") else None,
        project_desc=row.get("PROJ_DESC", "").strip()[:100] if row.get("PROJ_DESC") else None,
        vendor_id=row.get("X1VENDOR", "").strip()[:20] if row.get("X1VENDOR") else None,
        vendor_name=row.get("X1VENDORNAME", "").strip()[:100] if row.get("X1VENDORNAME") else None,
        location=row.get("LOCATION", "").strip()[:30] if row.get("LOCATION") else None,
        location_desc=row.get("LOC_DESC", "").strip()[:100] if row.get("LOC_DESC") else None,
    )


def read_expense_csv(file_path: Path) -> Generator[Dict, None, None]:
    """Read GLDetailsExpense CSV file and yield rows."""
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def import_expense_actuals(
    db: Session,
    file_path: Path,
    clear_existing: bool = False,
    period_filter: str = None,
) -> Dict:
    """Import expense actuals from GLDetailsExpense CSV.
    
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
    
    logger.info(f"Importing expense actuals from {file_path}")
    
    if clear_existing:
        if period_filter:
            db.query(ExpenseActual).filter(
                ExpenseActual.period_yyyymm == period_filter
            ).delete()
        else:
            db.query(ExpenseActual).delete()
        db.commit()
        logger.info("Cleared existing expense actuals")
    
    batch_size = 1000
    batch = []
    
    for row in read_expense_csv(file_path):
        stats["total_rows"] += 1
        
        if period_filter and row.get("YYYYMM", "").strip() != period_filter:
            stats["skipped"] += 1
            continue
        
        try:
            actual = row_to_expense_actual(row)
            batch.append(actual)
            stats["total_amount"] += actual.amount
            stats["imported"] += 1
            
            if len(batch) >= batch_size:
                db.bulk_save_objects(batch)
                db.commit()
                batch = []
                logger.info(f"Imported {stats['imported']} rows...")
                
        except Exception as e:
            stats["errors"] += 1
            logger.warning(f"Error importing row {stats['total_rows']}: {e}")
    
    if batch:
        db.bulk_save_objects(batch)
        db.commit()
    
    logger.info(f"Import complete: {stats['imported']} rows, total amount: ${stats['total_amount']:,.2f}")
    return stats


def get_expense_summary_by_department(db: Session, period_yyyymm: str) -> List[Dict]:
    """Get summary of expenses by department for a period."""
    from sqlalchemy import func
    
    results = db.query(
        ExpenseActual.department,
        ExpenseActual.budget_entity,
        ExpenseActual.labor_nonlabor,
        func.sum(ExpenseActual.amount).label("total_amount"),
        func.count(ExpenseActual.id).label("transaction_count"),
    ).filter(
        ExpenseActual.period_yyyymm == period_yyyymm
    ).group_by(
        ExpenseActual.department,
        ExpenseActual.budget_entity,
        ExpenseActual.labor_nonlabor,
    ).order_by(
        ExpenseActual.budget_entity,
        ExpenseActual.department,
    ).all()
    
    return [
        {
            "department": r.department,
            "plant": r.budget_entity,
            "labor_nonlabor": r.labor_nonlabor,
            "total_amount": float(r.total_amount),
            "transaction_count": r.transaction_count,
        }
        for r in results
    ]


def get_outage_costs(db: Session, period_yyyymm: str, plant_id: int = None) -> List[Dict]:
    """Get outage costs (planned and unplanned) for a period."""
    from sqlalchemy import func
    
    query = db.query(
        ExpenseActual.department,
        ExpenseActual.budget_entity,
        ExpenseActual.cost_type,
        func.sum(ExpenseActual.amount).label("total_amount"),
    ).filter(
        ExpenseActual.period_yyyymm == period_yyyymm,
        ExpenseActual.cost_type.in_(["PLANNED", "UNPLANNED"]),
    )
    
    if plant_id:
        query = query.filter(ExpenseActual.plant_id == plant_id)
    
    results = query.group_by(
        ExpenseActual.department,
        ExpenseActual.budget_entity,
        ExpenseActual.cost_type,
    ).order_by(
        ExpenseActual.cost_type,
        ExpenseActual.department,
    ).all()
    
    return [
        {
            "department": r.department,
            "plant": r.budget_entity,
            "cost_type": r.cost_type,
            "total_amount": float(r.total_amount),
        }
        for r in results
    ]

