"""ETL pipeline for importing Aligne coal data.

Imports coal inventory data from Aligne exports:
- monthly_coal_purchase_and_consumed.csv
- monthly_ending_coal_qty.csv
"""

import csv
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Optional, Generator
import logging

from sqlalchemy.orm import Session

from src.models.actuals import CoalInventory

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


def company_id_to_plant_id(company_id: str) -> Optional[int]:
    """Convert Aligne COMPANY_ID to plant_id.
    
    Args:
        company_id: "1" for Kyger, "2" for Clifty
        
    Returns:
        Plant ID (1 or 2)
    """
    try:
        cid = int(company_id)
        if cid == 1:
            return 1  # Kyger Creek
        elif cid == 2:
            return 2  # Clifty Creek
    except (ValueError, TypeError):
        pass
    return None


def read_csv(file_path: Path) -> Generator[Dict, None, None]:
    """Read CSV file and yield rows."""
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def import_coal_purchase_consumed(
    db: Session,
    file_path: Path,
    clear_existing: bool = False,
) -> Dict:
    """Import coal purchase and consumption data.
    
    File format: YYYYMM, COMPANY_ID, PURCHASED, CONSUMED, INVENT_ADJ
    
    Args:
        db: Database session
        file_path: Path to monthly_coal_purchase_and_consumed.csv
        clear_existing: If True, delete existing records first
        
    Returns:
        Dictionary with import statistics
    """
    stats = {
        "total_rows": 0,
        "imported": 0,
        "updated": 0,
        "errors": 0,
    }
    
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    logger.info(f"Importing coal purchase/consumed from {file_path}")
    
    if clear_existing:
        db.query(CoalInventory).delete()
        db.commit()
        logger.info("Cleared existing coal inventory")
    
    for row in read_csv(file_path):
        stats["total_rows"] += 1
        
        try:
            period_yyyymm = row.get("YYYYMM", "").strip()
            company_id = row.get("COMPANY_ID", "").strip()
            plant_id = company_id_to_plant_id(company_id)
            
            if not period_yyyymm or not plant_id:
                stats["errors"] += 1
                continue
            
            # Check if record exists
            existing = db.query(CoalInventory).filter(
                CoalInventory.period_yyyymm == period_yyyymm,
                CoalInventory.plant_id == plant_id,
            ).first()
            
            purchased = parse_amount(row.get("PURCHASED", "0"))
            consumed = parse_amount(row.get("CONSUMED", "0"))
            adjustment = parse_amount(row.get("INVENT_ADJ", "0"))
            
            if existing:
                existing.purchased_tons = purchased
                existing.consumed_tons = consumed
                existing.inventory_adjustment = adjustment
                stats["updated"] += 1
            else:
                inventory = CoalInventory(
                    period_yyyymm=period_yyyymm,
                    plant_id=plant_id,
                    purchased_tons=purchased,
                    consumed_tons=consumed,
                    inventory_adjustment=adjustment,
                )
                db.add(inventory)
                stats["imported"] += 1
                
        except Exception as e:
            stats["errors"] += 1
            logger.warning(f"Error importing row {stats['total_rows']}: {e}")
    
    db.commit()
    logger.info(f"Import complete: {stats['imported']} new, {stats['updated']} updated")
    return stats


def import_ending_coal_qty(
    db: Session,
    file_path: Path,
) -> Dict:
    """Import ending coal inventory quantities.
    
    File format: COMPANY_ID, YYYYMM, PERIODENDQTY
    
    Args:
        db: Database session
        file_path: Path to monthly_ending_coal_qty.csv
        
    Returns:
        Dictionary with import statistics
    """
    stats = {
        "total_rows": 0,
        "updated": 0,
        "created": 0,
        "errors": 0,
    }
    
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    logger.info(f"Importing ending coal qty from {file_path}")
    
    for row in read_csv(file_path):
        stats["total_rows"] += 1
        
        try:
            company_id = row.get("COMPANY_ID", "").strip()
            period_yyyymm = row.get("YYYYMM", "").strip()
            plant_id = company_id_to_plant_id(company_id)
            
            if not period_yyyymm or not plant_id:
                stats["errors"] += 1
                continue
            
            ending_qty = parse_amount(row.get("PERIODENDQTY", "0"))
            
            # Check if record exists
            existing = db.query(CoalInventory).filter(
                CoalInventory.period_yyyymm == period_yyyymm,
                CoalInventory.plant_id == plant_id,
            ).first()
            
            if existing:
                existing.ending_inventory_tons = ending_qty
                stats["updated"] += 1
            else:
                # Create new record with just ending inventory
                inventory = CoalInventory(
                    period_yyyymm=period_yyyymm,
                    plant_id=plant_id,
                    ending_inventory_tons=ending_qty,
                )
                db.add(inventory)
                stats["created"] += 1
                
        except Exception as e:
            stats["errors"] += 1
            logger.warning(f"Error importing row {stats['total_rows']}: {e}")
    
    db.commit()
    logger.info(f"Import complete: {stats['created']} created, {stats['updated']} updated")
    return stats


def import_all_aligne_data(
    db: Session,
    purchase_consumed_path: Path,
    ending_qty_path: Path,
    clear_existing: bool = False,
) -> Dict:
    """Import all Aligne data files.
    
    Args:
        db: Database session
        purchase_consumed_path: Path to purchase/consumed CSV
        ending_qty_path: Path to ending qty CSV
        clear_existing: If True, clear existing data first
        
    Returns:
        Combined statistics
    """
    # Import purchase/consumed first
    stats1 = import_coal_purchase_consumed(
        db,
        purchase_consumed_path,
        clear_existing=clear_existing,
    )
    
    # Then update with ending quantities
    stats2 = import_ending_coal_qty(db, ending_qty_path)
    
    return {
        "purchase_consumed": stats1,
        "ending_qty": stats2,
    }


def get_coal_inventory_history(
    db: Session,
    plant_id: int = None,
    start_period: str = None,
    end_period: str = None,
) -> List[Dict]:
    """Get coal inventory history.
    
    Args:
        db: Database session
        plant_id: Optional filter by plant
        start_period: Optional start period (YYYYMM)
        end_period: Optional end period (YYYYMM)
        
    Returns:
        List of inventory records
    """
    query = db.query(CoalInventory)
    
    if plant_id:
        query = query.filter(CoalInventory.plant_id == plant_id)
    if start_period:
        query = query.filter(CoalInventory.period_yyyymm >= start_period)
    if end_period:
        query = query.filter(CoalInventory.period_yyyymm <= end_period)
    
    results = query.order_by(
        CoalInventory.period_yyyymm.desc(),
        CoalInventory.plant_id,
    ).all()
    
    return [
        {
            "period": r.period_yyyymm,
            "plant_id": r.plant_id,
            "plant_name": "Kyger Creek" if r.plant_id == 1 else "Clifty Creek",
            "purchased_tons": float(r.purchased_tons) if r.purchased_tons else 0,
            "consumed_tons": float(r.consumed_tons) if r.consumed_tons else 0,
            "inventory_adjustment": float(r.inventory_adjustment) if r.inventory_adjustment else 0,
            "ending_inventory_tons": float(r.ending_inventory_tons) if r.ending_inventory_tons else 0,
        }
        for r in results
    ]


def get_coal_summary_by_year(db: Session, plant_id: int = None) -> List[Dict]:
    """Get annual coal consumption summary."""
    from sqlalchemy import func
    
    query = db.query(
        func.substr(CoalInventory.period_yyyymm, 1, 4).label("year"),
        CoalInventory.plant_id,
        func.sum(CoalInventory.purchased_tons).label("total_purchased"),
        func.sum(CoalInventory.consumed_tons).label("total_consumed"),
    )
    
    if plant_id:
        query = query.filter(CoalInventory.plant_id == plant_id)
    
    results = query.group_by(
        func.substr(CoalInventory.period_yyyymm, 1, 4),
        CoalInventory.plant_id,
    ).order_by(
        func.substr(CoalInventory.period_yyyymm, 1, 4).desc(),
        CoalInventory.plant_id,
    ).all()
    
    return [
        {
            "year": r.year,
            "plant_id": r.plant_id,
            "plant_name": "Kyger Creek" if r.plant_id == 1 else "Clifty Creek",
            "total_purchased": float(r.total_purchased) if r.total_purchased else 0,
            "total_consumed": float(r.total_consumed) if r.total_consumed else 0,
        }
        for r in results
    ]

