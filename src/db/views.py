"""
Database views for budget reporting.
"""

from sqlalchemy import text
from src.db.postgres import get_engine
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# SQL to create the transaction_budget_groups view
CREATE_BUDGET_GROUPS_VIEW = """
DROP VIEW IF EXISTS transaction_budget_groups;

CREATE VIEW transaction_budget_groups AS
SELECT 
    t.id,
    t.gxacct,
    t.txyear,
    t.txmnth,
    t.gxfamt,
    t.gxdrcr,
    t.gxpjno,
    t.gxshut,
    t.gxdesc,
    t.thsrc,
    a.ctdesc,
    a.ctuf01,
    
    -- Derive plant_code from account or shutdown alias
    CASE 
        WHEN LEFT(t.gxshut, 1) = 'K' THEN 'KC'
        WHEN LEFT(t.gxshut, 1) = 'C' THEN 'CC'
        WHEN LEFT(t.gxacct, 1) = '1' THEN 'KC'  -- Kyger accounts start with 1
        WHEN LEFT(t.gxacct, 1) = '2' THEN 'CC'  -- Clifty accounts start with 2
        ELSE 'KC'  -- Default
    END AS plant_code,
    
    -- Department code: project mapping takes priority, then CTUF01 fallback
    COALESCE(pm.dept_code, adm.dept_code, 'MAINT') AS dept_code,
    
    -- Outage group: derived from shutdown alias pattern
    CASE 
        WHEN LENGTH(TRIM(COALESCE(t.gxshut, ''))) >= 6 
             AND SUBSTRING(t.gxshut, 6, 1) = 'P' 
        THEN 'PLANNED-' || SUBSTRING(t.gxshut, 2, 2)
        
        WHEN LENGTH(TRIM(COALESCE(t.gxshut, ''))) >= 6 
             AND SUBSTRING(t.gxshut, 6, 1) IN ('M', 'F') 
        THEN 'UNPLANNED'
        
        ELSE NULL
    END AS outage_group,
    
    -- Flag if this is an outage transaction
    CASE 
        WHEN LENGTH(TRIM(COALESCE(t.gxshut, ''))) >= 6 
             AND SUBSTRING(t.gxshut, 6, 1) IN ('P', 'M', 'F') 
        THEN TRUE
        ELSE FALSE
    END AS is_outage
    
FROM gl_transactions t
LEFT JOIN gl_accounts a ON t.gxacct = a.ctacct
LEFT JOIN project_mappings pm ON TRIM(t.gxpjno) = pm.project_number
LEFT JOIN account_dept_mappings adm ON TRIM(a.ctuf01) = adm.ctuf01;
"""


def create_budget_groups_view():
    """Create the transaction_budget_groups view."""
    logging.info("Creating transaction_budget_groups view...")
    
    engine = get_engine()
    
    with engine.connect() as conn:
        # Execute each statement separately
        conn.execute(text("DROP VIEW IF EXISTS transaction_budget_groups"))
        conn.commit()
        
        # Create the view
        create_sql = """
        CREATE VIEW transaction_budget_groups AS
        SELECT 
            t.id,
            t.gxacct,
            t.txyear,
            t.txmnth,
            t.gxfamt,
            t.gxdrcr,
            t.gxpjno,
            t.gxshut,
            t.gxdesc,
            t.thsrc,
            a.ctdesc,
            a.ctuf01,
            
            -- Derive plant_code from account or shutdown alias
            CASE 
                WHEN LEFT(t.gxshut, 1) = 'K' THEN 'KC'
                WHEN LEFT(t.gxshut, 1) = 'C' THEN 'CC'
                WHEN LEFT(t.gxacct, 1) = '1' THEN 'KC'
                WHEN LEFT(t.gxacct, 1) = '2' THEN 'CC'
                ELSE 'KC'
            END AS plant_code,
            
            -- Department code: project mapping takes priority, then CTUF01 fallback
            COALESCE(pm.dept_code, adm.dept_code, 'MAINT') AS dept_code,
            
            -- Outage group: derived from shutdown alias pattern
            CASE 
                WHEN LENGTH(TRIM(COALESCE(t.gxshut, ''))) >= 6 
                     AND SUBSTRING(t.gxshut, 6, 1) = 'P' 
                THEN 'PLANNED-' || SUBSTRING(t.gxshut, 2, 2)
                
                WHEN LENGTH(TRIM(COALESCE(t.gxshut, ''))) >= 6 
                     AND SUBSTRING(t.gxshut, 6, 1) IN ('M', 'F') 
                THEN 'UNPLANNED'
                
                ELSE NULL
            END AS outage_group,
            
            -- Flag if this is an outage transaction
            CASE 
                WHEN LENGTH(TRIM(COALESCE(t.gxshut, ''))) >= 6 
                     AND SUBSTRING(t.gxshut, 6, 1) IN ('P', 'M', 'F') 
                THEN TRUE
                ELSE FALSE
            END AS is_outage
            
        FROM gl_transactions t
        LEFT JOIN gl_accounts a ON t.gxacct = a.ctacct
        LEFT JOIN project_mappings pm ON TRIM(t.gxpjno) = pm.project_number
        LEFT JOIN account_dept_mappings adm ON TRIM(a.ctuf01) = adm.ctuf01
        """
        conn.execute(text(create_sql))
        conn.commit()
        
    logging.info("View created successfully")


if __name__ == "__main__":
    create_budget_groups_view()

