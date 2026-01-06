"""ETL pipeline for importing PTProd_AcctGL_Budget (budget data).

Imports budget data with:
- Monthly breakdown (Jan-Dec)
- Out-year projections (BudgetYear+1 to +4)
- Ranking/priority classification
"""

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Optional, Generator
import logging

from sqlalchemy.orm import Session

from src.models.actuals import BudgetLine
from src.etl.account_mapping import (
    parse_gl_account,
    get_plant_id_from_code,
    BUDGET_RANKINGS,
)

logger = logging.getLogger(__name__)


def parse_amount(amount_str: str) -> Decimal:
    """Parse amount string to Decimal."""
    if not amount_str or amount_str.strip() == "":
        return Decimal("0")
    
    try:
        cleaned = amount_str.strip().replace(",", "")
        return Decimal(cleaned)
    except Exception:
        return Decimal("0")


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string."""
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


def parse_ranking(ranking_str: str) -> Dict:
    """Parse ranking string to get priority and category."""
    if not ranking_str or ranking_str.strip() == "":
        return {"priority": None, "category": None}
    
    ranking_str = ranking_str.strip()
    
    # Check for known rankings
    if ranking_str in BUDGET_RANKINGS:
        info = BUDGET_RANKINGS[ranking_str]
        return {
            "priority": info.get("priority"),
            "category": info.get("category"),
        }
    
    # Try to parse unknown rankings (usually start with number)
    if ranking_str[0].isdigit():
        return {
            "priority": int(ranking_str[0]),
            "category": ranking_str[1:].strip() if len(ranking_str) > 1 else None,
        }
    
    return {"priority": None, "category": ranking_str}


def row_to_budget_line(row: Dict) -> BudgetLine:
    """Convert a CSV row to a BudgetLine model instance.
    
    Args:
        row: Dictionary from CSV reader
        
    Returns:
        BudgetLine instance
    """
    full_account = row.get("FullAccount", "").strip()
    parsed = parse_gl_account(full_account)
    
    budget_entity = row.get("BUDGET", "").strip()
    plant_id = get_plant_id_from_budget(budget_entity)
    
    if plant_id is None and parsed:
        plant_id = get_plant_id_from_code(parsed.plant_code)
    
    # Parse ranking
    ranking_str = row.get("Ranking", "").strip()
    ranking_info = parse_ranking(ranking_str)
    
    # Parse import date
    import_date = parse_date(row.get("ImportDate", ""))
    
    # Parse budget year
    budget_year_str = row.get("BudgetYear", "")
    try:
        budget_year = int(budget_year_str) if budget_year_str else 2025
    except ValueError:
        budget_year = 2025
    
    return BudgetLine(
        budget_history_link=row.get("BudgetHistoryLink", "").strip()[:20] or None,
        budget_key=row.get("KEY", "").strip()[:100] or None,
        budget_number=row.get("Budget#", "").strip()[:20] or None,
        full_account=full_account,
        account_code=row.get("Account", "").strip()[:50] or None,
        account_description=row.get("AcctDesc", "").strip()[:100] or None,
        line_description=row.get("Description", "").strip()[:500] or None,
        budget_entity=budget_entity or None,
        plant_id=plant_id,
        department=row.get("Dept", "").strip()[:30] or None,
        labor_nonlabor=row.get("L/N", "").strip()[:5] or None,
        budget_year=budget_year,
        jan=parse_amount(row.get("Jan", "0")),
        feb=parse_amount(row.get("Feb", "0")),
        mar=parse_amount(row.get("Mar", "0")),
        apr=parse_amount(row.get("Apr", "0")),
        may=parse_amount(row.get("May", "0")),
        jun=parse_amount(row.get("Jun", "0")),
        jul=parse_amount(row.get("Jul", "0")),
        aug=parse_amount(row.get("Aug", "0")),
        sep=parse_amount(row.get("Sep", "0")),
        oct=parse_amount(row.get("Oct", "0")),
        nov=parse_amount(row.get("Nov", "0")),
        dec=parse_amount(row.get("Dec", "0")),
        total=parse_amount(row.get("Total", "0")),
        year_plus_1=parse_amount(row.get("BudgetYear+1", "0")),
        year_plus_2=parse_amount(row.get("BudgetYear+2", "0")),
        year_plus_3=parse_amount(row.get("BudgetYear+3", "0")),
        year_plus_4=parse_amount(row.get("BudgetYear+4", "0")),
        ranking=ranking_str[:20] if ranking_str else None,
        ranking_priority=ranking_info["priority"],
        ranking_category=ranking_info["category"][:30] if ranking_info["category"] else None,
        comments=row.get("Comments", "").strip()[:500] or None,
        import_date=import_date.date() if import_date else None,
    )


def read_budget_csv(file_path: Path) -> Generator[Dict, None, None]:
    """Read budget CSV file and yield rows."""
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def import_budget(
    db: Session,
    file_path: Path,
    clear_existing: bool = False,
    budget_year: int = None,
) -> Dict:
    """Import budget data from PTProd_AcctGL_Budget CSV.
    
    Args:
        db: Database session
        file_path: Path to CSV file
        clear_existing: If True, delete existing records first
        budget_year: Optional year to filter import
        
    Returns:
        Dictionary with import statistics
    """
    stats = {
        "total_rows": 0,
        "imported": 0,
        "skipped": 0,
        "errors": 0,
        "total_budget": Decimal("0"),
    }
    
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    logger.info(f"Importing budget from {file_path}")
    
    if clear_existing:
        if budget_year:
            db.query(BudgetLine).filter(
                BudgetLine.budget_year == budget_year
            ).delete()
        else:
            db.query(BudgetLine).delete()
        db.commit()
        logger.info("Cleared existing budget lines")
    
    batch_size = 500
    batch = []
    
    for row in read_budget_csv(file_path):
        stats["total_rows"] += 1
        
        # Apply year filter if specified
        row_year = row.get("BudgetYear", "")
        if budget_year and row_year and int(row_year) != budget_year:
            stats["skipped"] += 1
            continue
        
        try:
            budget_line = row_to_budget_line(row)
            batch.append(budget_line)
            stats["total_budget"] += budget_line.total
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
    
    logger.info(f"Import complete: {stats['imported']} rows, total budget: ${stats['total_budget']:,.2f}")
    return stats


def get_budget_summary_by_entity(db: Session, budget_year: int) -> List[Dict]:
    """Get budget summary by entity for a year."""
    from sqlalchemy import func
    
    results = db.query(
        BudgetLine.budget_entity,
        func.sum(BudgetLine.total).label("total_budget"),
        func.count(BudgetLine.id).label("line_count"),
    ).filter(
        BudgetLine.budget_year == budget_year
    ).group_by(
        BudgetLine.budget_entity,
    ).order_by(
        BudgetLine.budget_entity,
    ).all()
    
    return [
        {
            "entity": r.budget_entity,
            "total_budget": float(r.total_budget) if r.total_budget else 0,
            "line_count": r.line_count,
        }
        for r in results
    ]


def get_budget_summary_by_department(
    db: Session,
    budget_year: int,
    budget_entity: str = None,
) -> List[Dict]:
    """Get budget summary by department."""
    from sqlalchemy import func
    
    query = db.query(
        BudgetLine.department,
        BudgetLine.budget_entity,
        func.sum(BudgetLine.total).label("total_budget"),
        func.count(BudgetLine.id).label("line_count"),
    ).filter(
        BudgetLine.budget_year == budget_year
    )
    
    if budget_entity:
        query = query.filter(BudgetLine.budget_entity == budget_entity)
    
    results = query.group_by(
        BudgetLine.department,
        BudgetLine.budget_entity,
    ).order_by(
        BudgetLine.budget_entity,
        BudgetLine.department,
    ).all()
    
    return [
        {
            "department": r.department,
            "entity": r.budget_entity,
            "total_budget": float(r.total_budget) if r.total_budget else 0,
            "line_count": r.line_count,
        }
        for r in results
    ]


def get_budget_by_month(
    db: Session,
    budget_year: int,
    budget_entity: str = None,
) -> Dict[int, Decimal]:
    """Get total budget by month."""
    from sqlalchemy import func
    
    query = db.query(BudgetLine).filter(BudgetLine.budget_year == budget_year)
    
    if budget_entity:
        query = query.filter(BudgetLine.budget_entity == budget_entity)
    
    lines = query.all()
    
    monthly_totals = {m: Decimal("0") for m in range(1, 13)}
    
    for line in lines:
        monthly = line.get_monthly_amounts()
        for month, amount in monthly.items():
            if amount:
                monthly_totals[month] += amount
    
    return monthly_totals

