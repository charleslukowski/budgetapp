"""
Transaction API endpoints.
"""

from fastapi import APIRouter, Query
from sqlalchemy import text
from typing import Optional, List
from decimal import Decimal

from src.db.postgres import get_engine
from src.api.schemas import Transaction, TransactionList

router = APIRouter()


@router.get("/transactions", response_model=TransactionList)
async def get_transactions(
    year: Optional[int] = Query(default=None),
    month: Optional[int] = Query(default=None),
    plant_code: Optional[str] = Query(default=None),
    dept_code: Optional[str] = Query(default=None),
    outage_group: Optional[str] = Query(default=None),
    account: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=1000)
):
    """
    Get filtered list of transactions with pagination.
    """
    engine = get_engine()
    
    # Build dynamic WHERE clause
    conditions = []
    params = {}
    
    if year:
        conditions.append("txyear = :year")
        params["year"] = year
    if month:
        conditions.append("txmnth = :month")
        params["month"] = month
    if plant_code:
        conditions.append("plant_code = :plant_code")
        params["plant_code"] = plant_code
    if dept_code:
        conditions.append("dept_code = :dept_code")
        params["dept_code"] = dept_code
    if outage_group:
        conditions.append("outage_group = :outage_group")
        params["outage_group"] = outage_group
    if account:
        conditions.append("gxacct LIKE :account")
        params["account"] = f"%{account}%"
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    # Calculate offset
    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset
    
    with engine.connect() as conn:
        # Get total count
        count_query = text(f"""
            SELECT COUNT(*) FROM transaction_budget_groups
            WHERE {where_clause}
        """)
        total = conn.execute(count_query, params).scalar()
        
        # Get transactions
        query = text(f"""
            SELECT 
                id, gxacct, ctdesc, txyear, txmnth, gxfamt, gxdrcr,
                gxpjno, gxshut, gxdesc, dept_code, outage_group, plant_code
            FROM transaction_budget_groups
            WHERE {where_clause}
            ORDER BY id
            LIMIT :limit OFFSET :offset
        """)
        
        result = conn.execute(query, params)
        rows = result.fetchall()
    
    transactions = [
        Transaction(
            id=row[0],
            gxacct=row[1],
            account_desc=row[2],
            txyear=row[3],
            txmnth=row[4],
            gxfamt=Decimal(str(row[5])) if row[5] else Decimal("0"),
            gxdrcr=row[6] or "",
            gxpjno=row[7],
            gxshut=row[8],
            gxdesc=row[9],
            dept_code=row[10] or "MAINT",
            outage_group=row[11],
            plant_code=row[12] or "KC"
        )
        for row in rows
    ]
    
    return TransactionList(
        transactions=transactions,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/transactions/summary")
async def get_transaction_summary(
    year: int = Query(...),
    month: Optional[int] = Query(default=None)
):
    """
    Get transaction summary statistics.
    """
    engine = get_engine()
    
    with engine.connect() as conn:
        if month:
            query = text("""
                SELECT 
                    COUNT(*) as total_txns,
                    SUM(CASE WHEN gxfamt > 0 THEN gxfamt ELSE 0 END) as total_debits,
                    SUM(CASE WHEN gxfamt < 0 THEN gxfamt ELSE 0 END) as total_credits,
                    SUM(gxfamt) as net_amount,
                    COUNT(DISTINCT dept_code) as dept_count,
                    COUNT(DISTINCT gxacct) as account_count
                FROM transaction_budget_groups
                WHERE txyear = :year AND txmnth = :month
            """)
            result = conn.execute(query, {"year": year, "month": month})
        else:
            query = text("""
                SELECT 
                    COUNT(*) as total_txns,
                    SUM(CASE WHEN gxfamt > 0 THEN gxfamt ELSE 0 END) as total_debits,
                    SUM(CASE WHEN gxfamt < 0 THEN gxfamt ELSE 0 END) as total_credits,
                    SUM(gxfamt) as net_amount,
                    COUNT(DISTINCT dept_code) as dept_count,
                    COUNT(DISTINCT gxacct) as account_count
                FROM transaction_budget_groups
                WHERE txyear = :year
            """)
            result = conn.execute(query, {"year": year})
        
        row = result.fetchone()
    
    return {
        "year": year,
        "month": month,
        "total_transactions": row[0],
        "total_debits": float(row[1]) if row[1] else 0,
        "total_credits": float(row[2]) if row[2] else 0,
        "net_amount": float(row[3]) if row[3] else 0,
        "department_count": row[4],
        "account_count": row[5]
    }

