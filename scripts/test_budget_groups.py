"""
Test the transaction_budget_groups view.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.db.postgres import get_engine
from sqlalchemy import text


def test_budget_groups():
    print("=" * 70)
    print("Testing transaction_budget_groups View")
    print("=" * 70)
    
    engine = get_engine()
    conn = engine.connect()
    
    # 1. Count total transactions
    result = conn.execute(text("SELECT COUNT(*) FROM transaction_budget_groups"))
    total = result.fetchone()[0]
    print(f"\nTotal transactions: {total:,}")
    
    # 2. Summary by dept_code
    print("\n" + "-" * 50)
    print("Transactions by Department")
    print("-" * 50)
    result = conn.execute(text("""
        SELECT dept_code, COUNT(*) as cnt, SUM(gxfamt) as total_amt
        FROM transaction_budget_groups
        GROUP BY dept_code
        ORDER BY cnt DESC
    """))
    for row in result.fetchall():
        print(f"{row[0]:<15} {row[1]:>8,} txns  ${row[2]:>15,.2f}")
    
    # 3. Summary by outage_group
    print("\n" + "-" * 50)
    print("Transactions by Outage Group")
    print("-" * 50)
    result = conn.execute(text("""
        SELECT 
            COALESCE(outage_group, 'Non-Outage') as grp,
            COUNT(*) as cnt, 
            SUM(gxfamt) as total_amt
        FROM transaction_budget_groups
        GROUP BY outage_group
        ORDER BY cnt DESC
    """))
    for row in result.fetchall():
        print(f"{row[0]:<15} {row[1]:>8,} txns  ${row[2]:>15,.2f}")
    
    # 4. Summary by plant_code
    print("\n" + "-" * 50)
    print("Transactions by Plant")
    print("-" * 50)
    result = conn.execute(text("""
        SELECT plant_code, COUNT(*) as cnt, SUM(gxfamt) as total_amt
        FROM transaction_budget_groups
        GROUP BY plant_code
        ORDER BY plant_code
    """))
    for row in result.fetchall():
        print(f"{row[0]:<15} {row[1]:>8,} txns  ${row[2]:>15,.2f}")
    
    # 5. Sample of outage transactions
    print("\n" + "-" * 50)
    print("Sample Outage Transactions (first 10)")
    print("-" * 50)
    result = conn.execute(text("""
        SELECT gxshut, outage_group, dept_code, plant_code, gxfamt
        FROM transaction_budget_groups
        WHERE is_outage = TRUE
        LIMIT 10
    """))
    print(f"{'Alias':<15} {'Outage Group':<15} {'Dept':<10} {'Plant':<6} {'Amount':>12}")
    print("-" * 60)
    for row in result.fetchall():
        print(f"{row[0]:<15} {row[1]:<15} {row[2]:<10} {row[3]:<6} ${row[4]:>10,.2f}")
    
    # 6. Transactions without department mapping
    print("\n" + "-" * 50)
    print("Unmapped Transactions (defaulted to MAINT)")
    print("-" * 50)
    result = conn.execute(text("""
        SELECT COUNT(*) as cnt
        FROM transaction_budget_groups t
        LEFT JOIN project_mappings pm ON TRIM(t.gxpjno) = pm.project_number
        LEFT JOIN gl_accounts a ON t.gxacct = a.ctacct
        LEFT JOIN account_dept_mappings adm ON TRIM(a.ctuf01) = adm.ctuf01
        WHERE pm.dept_code IS NULL AND adm.dept_code IS NULL
    """))
    unmapped = result.fetchone()[0]
    print(f"Transactions defaulting to MAINT: {unmapped:,} ({unmapped/total*100:.1f}%)")
    
    conn.close()
    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)


if __name__ == "__main__":
    test_budget_groups()

