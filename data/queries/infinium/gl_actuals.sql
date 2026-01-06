-- Infinium GL Actuals Extract
-- Table: GLCUFA.GLPTX1
-- Frequency: Daily/Monthly
-- Purpose: GL transaction detail for actuals

SELECT 
    -- Key identifiers
    GXJRNL,                 -- Journal number
    GXACCT,                 -- GL Account (36 char)
    GXCO,                   -- Company (003)
    
    -- Time dimensions
    TXYEAR,                 -- Year
    TXMNTH,                 -- Month
    THEDAT,                 -- Transaction date (YYYY-MM-DD)
    TH8DAT,                 -- Date as YYYYMMDD decimal
    
    -- Amount
    GXFAMT,                 -- Amount (17,2 decimal)
    GXDRCR,                 -- D=Debit, C=Credit
    
    -- Descriptions
    CTDESC,                 -- Account description
    GXDESC,                 -- Transaction description
    GXDSC2,                 -- Extended description (140 char)
    
    -- Source/Reference
    THSRC,                  -- Source code
    THREF,                  -- Reference
    
    -- Vendor
    "GXVND#" AS GXVNDNUM,   -- Vendor number
    GXVNDN,                 -- Vendor name
    
    -- Project
    GXPJCO,                 -- Project company
    GXPJNO,                 -- Project number
    PHDESC,                 -- Project description
    GXPJDEPT,               -- Project department
    GXPJDESC,               -- Project description (extended)
    
    -- WBS
    GXPWBS,                 -- WBS code
    WBDESC,                 -- WBS description
    GXWBS,                  -- Full WBS
    WBSSUB01,               -- WBS sub 1
    WBSSUB02,               -- WBS sub 2
    
    -- Equipment
    GXEQFC,                 -- Equipment facility code
    GXEQUN,                 -- Equipment unit
    GXEQOS,                 -- Equipment OS
    GXEQSC,                 -- Equipment system code
    GXEQCL,                 -- Equipment class
    GXEQTY,                 -- Equipment type (70 char)
    "GXEQ#" AS GXEQNUM,     -- Equipment number
    GXEQCT,                 -- Equipment category
    "GXEQC#" AS GXEQCNUM,   -- Equipment category number
    GXEQDV,                 -- Equipment division
    GXEQAR,                 -- Equipment area
    GXEQNM,                 -- Equipment name (65 char)
    
    -- Invoice/PO subsegments
    INVSUB01,               -- Invoice sub 1
    INVSUB02,               -- Invoice sub 2
    INVSUB03,               -- Invoice sub 3
    POSUB01,                -- PO sub 1
    POSUB02,                -- PO sub 2
    POSUB03,                -- PO sub 3
    POSUB04,                -- PO sub 4
    POSUB05,                -- PO sub 5
    CNSUB01,                -- Contract sub 1
    CNSUB02,                -- Contract sub 2
    CNSUB03,                -- Contract sub 3
    CNSUB04,                -- Contract sub 4
    
    -- Other reference fields
    GXPREF,                 -- Reference
    GXRFTY,                 -- Reference type
    "GXRF#" AS GXRFNUM,     -- Reference number
    GXPLAN,                 -- Plan
    GXCTID,                 -- CT ID
    GXWOTD                  -- Work order type description

FROM GLCUFA.GLPTX1 
WHERE TXYEAR = :year
  AND TXMNTH = :month

-- For full year:
-- WHERE TXYEAR = :year

-- Order by date and journal
ORDER BY THEDAT, GXJRNL
