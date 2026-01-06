# Data Integration Checklist

This document lists all source data, documents, and database access needed to integrate OVEC's actual data into the Budget System.

**Last Updated:** December 2024

---

## Source Files Inventory

### Files Received

| File | Location | Status | Notes |
|------|----------|--------|-------|
| `PTProd_AcctGL_GLDetailsExpense_202511_example.csv` | source_documents/ | **HAVE** | O&M expense transactions - 12,186 rows |
| `PTProd_AcctGL_GLDetailsEnergy.csv` | source_documents/ | **HAVE** | Fuel cost transactions - 99 rows |
| `PTProd_AcctGL_Budget.csv` | source_documents/ | **HAVE** | Budget line items - 2,300 rows |
| `RPTData_Kyger_example.csv` | source_documents/ | **HAVE** | Kyger actual/budget/forecast - 6,202 rows |
| `monthly_coal_purchase_and_consumed.csv` | source_documents/ | **HAVE** | Aligne coal data - 122 rows |
| `monthly_ending_coal_qty.csv` | source_documents/ | **HAVE** | Aligne inventory - 120 rows |
| `OVEC IKEC Energy Budget...xlsm` | source_documents/ | **HAVE** | Main fuel model - 44 tabs |
| `2025 - Fuel.xlsx` | source_documents/ | **HAVE** | Fuel KPIs - 13 monthly tabs |
| `2025 - Demand and Power Cost.xlsx` | source_documents/ | **HAVE** | $/MWhr tracking - 13 monthly tabs |
| `2025 Kyger Forecast.xlsx` | source_documents/ | **HAVE** | Dept budget input - 33 tabs |
| Monthly billable/operational reports | source_documents/Current output monthly/ | **HAVE** | Sample output formats |
| Yearly projection summaries | source_documents/Current yearly projection/ | **HAVE** | Long-term projection format |
| Variance report PDFs | source_documents/Current output monthly/ | **HAVE** | Visual reference |

---

## 1. Fuel Model (Priority: High)

### Status: **PARTIAL**

| Item | Status | Source File | Notes |
|------|--------|-------------|-------|
| Fuel Model Workbook | **HAVE** | `OVEC IKEC Energy Budget...xlsm` | 44 tabs including KC/CC Generation, Coal Burn, Supply, Emissions, Consumables, Byproducts |
| Driver Documentation | **NEED** | - | List of ~100 drivers with definitions/formulas needed |
| Coal Contract Summary | **PARTIAL** | "Coal Contracts Annual View" tab | Need contract details (Eastern/ILB) |
| Transportation Contract | **NEED** | - | Rail/barge agreements not provided |
| Historical Coal Prices | **NEED** | - | mmbtu pricing history |

### Key Tabs Identified in Fuel Model

**Input Tabs:**
- `CC Forecast Inputs` / `KC Forecast Inputs` - Manual forecast inputs
- `Northern Appalachia Coal Fcst` - Eastern coal assumptions
- `Illinois Basin Coal Fcst` - ILB coal assumptions
- `Urea Fcst` - Reagent assumptions
- `Limestone Mulzer` / `Limestone Hilltop` - Stone supplier assumptions
- `Allowance Costs` - Emission allowance pricing
- `Use Factor Input` - Capacity/availability assumptions
- `Scenario Data Block` - Scenario selections

**Calculation Tabs (per plant KC=Kyger, CC=Clifty):**
- `KC Generation` / `CC Generation` - MWh calculations
- `KC Reliability` / `CC Reliability` - Outage/availability
- `KC Coal Burn` / `CC Coal Burn` - Fuel consumption
- `KC Coal Supply` / `CC Coal Supply` - Contract deliveries
- `KC Emissions` / `CC Emissions` - SO2, NOx, etc.
- `KC Stone Supply` / `CC Stone Supply` - Limestone/lime
- `KC Consumables` / `CC Consumables` - Reagents (urea, mercury control)
- `KC Byproducts` / `CC Byproducts` - Ash/gypsum sales/disposal

**Output/Summary Tabs:**
- `SYS Cost Summary` / `SYS Cost Detail` - System-level totals
- `Coal Cost Analysis` - Blended coal cost calculations
- `AEP Upload` - Export format for AEP
- `Cheat Sheet` / `All-Years Cheat Sheet` - Quick reference

### Questions Remaining
- [ ] Driver dependency chain documentation?
- [ ] Coal quality assumptions by source?
- [ ] Take-or-pay minimums in contracts?
- [ ] Inventory valuation method (LIFO/FIFO/weighted avg)?

---

## 2. Generation Data (Priority: High)

### Status: **PARTIAL**

| Item | Status | Source File | Notes |
|------|--------|-------------|-------|
| Monthly MWh by plant | **PARTIAL** | `2025 - Demand and Power Cost.xlsx` | Contains PJM Delivered MWhrs |
| Net vs gross generation | **NEED** | - | Auxiliary load deductions |
| Outage rates | **PARTIAL** | Fuel model has Reliability tabs | Need to verify current data |
| Planned outage schedules | **NEED** | - | Calendar for next 2 years |

### Data Points Found
From `2025 - Demand and Power Cost.xlsx`:
- Monthly tabs (Jan-Dec) with projected vs actual $/MWhr
- PJM Delivered MWhrs tracked monthly per plant

### Questions Remaining
- [ ] How to get OATI/WebAccounting generation data automatically?
- [ ] Unit-level vs plant-level generation detail?
- [ ] Historical generation (3+ years) for trending?

---

## 3. Cost Actuals - GL Transactions (Priority: High)

### Status: **HAVE**

| Item | Status | Source File | Notes |
|------|--------|-------------|-------|
| O&M Expense Transactions | **HAVE** | `GLDetailsExpense_202511_example.csv` | Full detail with WO, PO, vendor |
| Fuel/Energy Transactions | **HAVE** | `GLDetailsEnergy.csv` | Fuel costs, byproduct sales |
| Budget Lines | **HAVE** | `Budget.csv` | Monthly budgets + 4 future years |
| Report Data (Kyger) | **HAVE** | `RPTData_Kyger_example.csv` | Actual/Budget/Forecast by type |

### Column Mapping - GLDetailsExpense

| Column | Description | Use |
|--------|-------------|-----|
| `GXACCT` | Full GL account (e.g., 003-1-20-401-20-320-922-321-5) | Account mapping |
| `CTDESC` | Account description | Display |
| `YYYYMM` | Period (e.g., 202511) | Time dimension |
| `GXFAMT` | Amount | Actuals |
| `GXDRCR` | D=Debit, C=Credit | Sign logic |
| `X1WORKORDER` | Work order number | Detail drill-down |
| `X1PONUM` | Purchase order | Procurement link |
| `X1VENDOR` | Vendor ID | Vendor analysis |
| `X1VENDORNAME` | Vendor name | Display |
| `BUDGET` | Budget category | Department mapping |
| `LOCATION` | Equipment location | Asset link |
| `GROUP` | Department group | Summary grouping |
| `LABOR-NONLABOR` | Labor vs NonLabor flag | Split reporting |
| `BudgetWithEO` | Budget with EO assignment | Plant allocation |

### Column Mapping - Budget.csv

| Column | Description | Use |
|--------|-------------|-----|
| `KEY` | Composite key (Budget+Account) | Unique identifier |
| `BUDGET` | Budget type (EO, Clifty, Kyger) | Plant/dept |
| `FullAccount` | GL account | Account mapping |
| `AcctDesc` | Account description | Display |
| `Description` | Line item description | Budget detail |
| `Dept` | Department code | Department mapping |
| `L/N` | Labor/NonLabor | Split |
| `Jan`-`Dec` | Monthly amounts | Monthly budget |
| `Total` | Annual total | Validation |
| `BudgetYear+1` to `+4` | Future years | Long-term projection |

### Account Structure
Format: `CCC-P-LL-AAA-BB-CCC-DDD-EEE-T`
- CCC: Company (003)
- P: Plant (1=Kyger, 2=Clifty)
- LL: Location (10=EO, 20=KC, 21=CC)
- AAA: Major account (401=O&M, etc.)
- BB-CCC-DDD-EEE: Sub-accounts/cost centers
- T: Type (4=NonLabor, 5=Labor)

---

## 4. Coal Inventory (Priority: High)

### Status: **HAVE**

| Item | Status | Source File | Notes |
|------|--------|-------------|-------|
| Monthly Purchased Tons | **HAVE** | `monthly_coal_purchase_and_consumed.csv` | By company (1=Kyger, 2=Clifty) |
| Monthly Consumed Tons | **HAVE** | `monthly_coal_purchase_and_consumed.csv` | Burn data |
| Inventory Adjustments | **HAVE** | `monthly_coal_purchase_and_consumed.csv` | INVENT_ADJ column |
| Month-End Inventory | **HAVE** | `monthly_ending_coal_qty.csv` | PERIODENDQTY in tons |

### Column Mapping - Coal Data

| File | Columns | Notes |
|------|---------|-------|
| `monthly_coal_purchase_and_consumed.csv` | YYYYMM, COMPANY_ID, PURCHASED, CONSUMED, INVENT_ADJ | Monthly coal flow |
| `monthly_ending_coal_qty.csv` | COMPANY_ID, YYYYMM, PERIODENDQTY | Ending inventory tons |

### Data Range
- Both files have 2020-2025 data (122 months × 2 plants)
- Sufficient for historical trending

---

## 5. Budget/Forecast Database (Priority: High)

### Status: **HAVE**

| Item | Status | Source File | Notes |
|------|--------|-------------|-------|
| Budget Structure | **HAVE** | `Budget.csv` | Account/Dept/Month structure |
| Current Year Budget | **HAVE** | `Budget.csv` | 2025 monthly detail |
| Future Year Budgets | **HAVE** | `Budget.csv` | 4 future years (annual) |
| Department Input Template | **HAVE** | `2025 Kyger Forecast.xlsx` | 22 department tabs |

### Department Structure (from Kyger Forecast)
Tabs 1-22 represent department input sheets:
- Each department has monthly columns
- Includes BUDGET, FcastAct, Var Rpt tabs for summaries
- COMBINED tab aggregates all departments

---

## 6. Sponsor Reporting (Priority: High)

### Status: **HAVE**

| Item | Status | Source File | Notes |
|------|--------|-------------|-------|
| Monthly Billable Report | **HAVE** | `2025mthlybillable...xlsx` | Current format |
| Operational Results | **HAVE** | `October Operational Results.xlsx` | Monthly operational data |
| Variance Reports | **HAVE** | PDFs in Current output monthly/ | Kyger and Clifty |
| Long-term Projections | **HAVE** | `2026-2040 Power Cost Summary.xlsx` | 15-year summary |
| Monthly Detail | **HAVE** | `2026 Monthly Detail - vBODxlsx.xlsx` | Next year monthly |
| Finance Billing | **HAVE** | `2026 Finance Billing.xlsx` | Billing projections |

---

## 7. Asset Health Database (Priority: Medium)

### Status: **NEED**

| Item | Status | Source File | Notes |
|------|--------|-------------|-------|
| Database Connection | **NEED** | - | Connection string required |
| Schema Documentation | **NEED** | - | Table structures |
| Sample Export | **NEED** | - | Example projected repairs |

### Questions Remaining
- [ ] What database platform (SQL Server)?
- [ ] What tables contain projected maintenance?
- [ ] How to map equipment to GL accounts?

---

## 8. Capital & Depreciation (Priority: Medium)

### Status: **NEED**

| Item | Status | Source File | Notes |
|------|--------|-------------|-------|
| Fixed Asset Register | **NEED** | - | Asset list with depreciation |
| Capital Projects | **NEED** | - | Approved/proposed projects |
| Depreciation Schedules | **NEED** | - | Monthly/annual depreciation |

---

## 9. Transmission Costs (Priority: Medium)

### Status: **NEED**

| Item | Status | Source File | Notes |
|------|--------|-------------|-------|
| Rate Schedules | **NEED** | - | Transmission rates |
| Historical Costs | **PARTIAL** | In GL actuals | Need to identify accounts |

---

## 10. Reference Data (Priority: Medium)

### Status: **PARTIAL**

| Item | Status | Source | Notes |
|------|--------|--------|-------|
| Account Mapping | **PARTIAL** | Embedded in CSV columns | GROUP, BUDGET columns provide some mapping |
| Department List | **HAVE** | Kyger Forecast tabs | 22 departments identified |
| Plant/Company Codes | **HAVE** | Multiple files | 1=Kyger, 2=Clifty |
| Cost Categories | **PARTIAL** | In data files | Need official hierarchy |

---

## Master Data to Gather

These reference tables define your system and should be provided separately from transaction files.

**Integration Types:**
- **One-Time** = Load once, manually update if changes (rare)
- **Periodic** = Refresh monthly/quarterly from source system
- **Integrate** = Build automated connection to source system

### 1. Organizational Structure

| Data | Format | What to Include | Type | Status |
|------|--------|-----------------|------|--------|
| Plant/Location List | Excel/CSV | Code, Name, Type (Generation/Admin), Active flag | One-Time | [ ] |
| Department List | Excel/CSV | Code, Name, Plant, Manager, Outage/Non-Outage flag | One-Time | [ ] |
| Cost Center Hierarchy | Excel/CSV | Cost center code, description, parent, level | One-Time | [ ] |

### 2. Chart of Accounts

| Data | Format | What to Include | Type | Status |
|------|--------|-----------------|------|--------|
| GL Account Master | Excel/CSV | Full account number, description, account type, active flag | Periodic | [ ] |
| Account Segment Definitions | Excel | Each segment position with valid values | One-Time | [ ] |
| FERC Account Mapping | Excel/CSV | GL account to FERC account crosswalk | One-Time | [ ] |
| Cost Category Mapping | Excel/CSV | GL account to reporting category (Fuel, O&M, A&G, Capital) | One-Time | [ ] |

### 3. Budget/Forecast Structure

| Data | Format | What to Include | Type | Status |
|------|--------|-----------------|------|--------|
| Budget Type List | Excel/CSV | Budget types (Annual Budget, Internal Forecast, External Forecast) | One-Time | [ ] |
| Fiscal Calendar | Excel/CSV | Period numbers, start/end dates, fiscal year | One-Time | [ ] |
| Approval Workflow | Document | Who approves what, in what order | One-Time | [ ] |

### 4. Fuel Model Reference

| Data | Format | What to Include | Type | Status |
|------|--------|-----------------|------|--------|
| Coal Supplier List | Excel/CSV | Supplier code, name, region (Eastern/ILB), active contracts | One-Time | [ ] |
| Coal Contract Summary | Excel | Contract ID, supplier, start/end dates, min/max tons, pricing formula | Periodic | [ ] |
| Reagent/Consumable Types | Excel/CSV | Code, name, unit of measure, GL account mapping | One-Time | [ ] |
| Byproduct Types | Excel/CSV | Ash, gypsum, etc. with disposal/sale indicator | One-Time | [ ] |
| Emission Types | Excel/CSV | SO2, NOx, CO2, Mercury - units and allowance account mapping | One-Time | [ ] |

### 5. Plant/Unit Technical Data

| Data | Format | What to Include | Type | Status |
|------|--------|-----------------|------|--------|
| Unit Master | Excel/CSV | Unit number, plant, nameplate capacity (MW), in-service date | One-Time | [ ] |
| Heat Rate by Unit | Excel | Design heat rate, typical operating heat rate (BTU/kWh) | Periodic | [ ] |
| Fuel Specifications | Excel | BTU/lb, sulfur %, ash %, moisture % by coal source | Periodic | [ ] |

### 6. Vendor/Supplier Master

| Data | Format | What to Include | Type | Status |
|------|--------|-----------------|------|--------|
| Vendor List | Excel/CSV | Vendor ID, name, type (Coal, Reagent, Contractor, etc.) | Periodic | [ ] |

### 7. Equipment/Asset Reference

| Data | Format | What to Include | Type | Status |
|------|--------|-----------------|------|--------|
| Equipment Categories | Excel/CSV | Category code, description, typical GL accounts | One-Time | [ ] |
| Major Equipment List | Excel/CSV | Equipment ID, description, plant, unit, category | **Integrate** | [ ] |

### 8. Reporting Reference

| Data | Format | What to Include | Type | Status |
|------|--------|-----------------|------|--------|
| Sponsor List | Excel/CSV | Sponsor code, name, ownership %, billing contact | One-Time | [ ] |
| Report Category Hierarchy | Excel | How costs roll up for sponsor reporting | One-Time | [ ] |
| $/MWhr Category List | Excel | Categories included in $/MWhr calculations | One-Time | [ ] |

### Summary by Type

**One-Time (14 items)** - Load once, update manually as needed:
- Plant/Location List
- Department List
- Cost Center Hierarchy
- Account Segment Definitions
- FERC Account Mapping
- Cost Category Mapping
- Budget Type List
- Fiscal Calendar
- Approval Workflow
- Coal Supplier List
- Reagent/Consumable Types
- Byproduct Types
- Emission Types
- Unit Master
- Equipment Categories
- Sponsor List
- Report Category Hierarchy
- $/MWhr Category List

**Periodic (5 items)** - Refresh quarterly or when changes occur:
- GL Account Master (new accounts added)
- Coal Contract Summary (new/expired contracts)
- Heat Rate by Unit (performance changes)
- Fuel Specifications (coal quality varies)
- Vendor List (new vendors added)

**Integrate (1 item)** - Build system connection:
- Major Equipment List → Asset Health DB

---

## Gap Summary

### HAVE - Ready for Import
1. **O&M Expense Actuals** - GLDetailsExpense CSV
2. **Fuel Cost Actuals** - GLDetailsEnergy CSV
3. **Budget Data** - Budget CSV with monthly + 4 future years
4. **Coal Inventory** - Aligne exports (purchased, consumed, ending)
5. **Kyger Actual/Budget/Forecast** - RPTData CSV
6. **Fuel Model Structure** - 44-tab Excel model
7. **Sample Reports** - Monthly and yearly output formats

### NEED - Required for Full Implementation

**High Priority:**
1. **Clifty RPTData** - Similar to Kyger example for Clifty plant
2. **Driver Documentation** - Fuel model driver definitions
3. **Coal Contract Details** - Contract terms, pricing, minimums
4. **Generation Actuals** - OATI/WebAccounting access or export

**Medium Priority:**
5. **Asset Health Database** - Connection and schema
6. **Capital Asset Register** - Depreciation data
7. **Historical Data** - 3+ years for trending (only have partial)

**Low Priority:**
8. **Transmission Details** - Rate schedules if separate from GL
9. **Inflation Assumptions** - Standard escalation rates

---

## Recommended Next Steps

### Phase 1: Account Mapping (1-2 weeks)
1. Extract unique GL accounts from provided CSVs
2. Create mapping table to cost categories
3. Validate with finance team

### Phase 2: Core Data Import (2-3 weeks)
1. Build import pipeline for GLDetails (Expense + Energy)
2. Build import pipeline for Budget data
3. Build import pipeline for Coal inventory
4. Build import pipeline for RPTData (need Clifty file)

### Phase 3: Fuel Model Analysis (3-4 weeks)
1. Document driver inputs and calculations
2. Extract input assumptions from Excel tabs
3. Design database structure for fuel forecasting
4. Build calculation engine prototype

### Phase 4: Integration (2-3 weeks)
1. Connect to Asset Health DB (when access provided)
2. Connect to Generation source (OATI or export)
3. Set up automated data refresh

---

## Database Access Summary

| System | Type | Status | Contact |
|--------|------|--------|---------|
| Forecast Database (CSV exports) | SQL Server | **HAVE exports** | - |
| Aligne (Coal inventory) | Export | **HAVE exports** | - |
| OATI/WebAccounting | Web/API | **NEED** | _______ |
| Asset Health DB | SQL Server | **NEED** | _______ |

---

## Folder Structure

### Master Data (One-Time CSVs)
Location: `data/master/`

| File | Description | Status |
|------|-------------|--------|
| `plants.csv` | Plant/location list | Draft - needs review |
| `departments.csv` | Department list with outage flags | Draft - needs review |
| `cost_centers.csv` | Cost center hierarchy | Draft - needs review |
| `account_segments.csv` | GL account segment definitions | Draft - needs review |
| `ferc_account_mapping.csv` | GL to FERC account mapping | Draft - needs review |
| `cost_category_mapping.csv` | GL to reporting category mapping | Draft - needs review |
| `budget_types.csv` | Budget/forecast type definitions | Draft - needs review |
| `fiscal_calendar.csv` | Fiscal periods 2025-2026 | Draft - extend as needed |
| `coal_suppliers.csv` | Coal supplier master | Empty - needs data |
| `reagent_types.csv` | Reagent/consumable types | Draft - needs review |
| `byproduct_types.csv` | Ash/gypsum types | Draft - needs review |
| `emission_types.csv` | Emission types | Draft - needs review |
| `units.csv` | Generating units | Draft - needs actual data |
| `equipment_categories.csv` | Equipment category mapping | Draft - needs review |
| `sponsors.csv` | Sponsor list with ownership % | Empty - needs data |
| `report_categories.csv` | Report category hierarchy | Draft - needs review |
| `mwhr_categories.csv` | Categories for $/MWhr calc | Draft - needs review |

### Periodic Queries by Source System
Location: `data/queries/`

```
data/queries/
├── infinium/           # Infinium ERP
│   ├── README.md       # Connection info
│   ├── gl_accounts.sql # GL account master (Quarterly)
│   └── vendors.sql     # Vendor master (Monthly)
│
├── maximo/             # Maximo Asset Management
│   ├── README.md       # Connection info
│   ├── equipment.sql   # Equipment master (Integration)
│   └── work_orders.sql # Work order details (Daily)
│
├── forecast_database/  # Existing Forecast DB
│   ├── README.md       # Connection info
│   ├── budget_lines.sql        # Budget data (Monthly)
│   ├── rpt_data.sql            # Actual/Budget/Fcst (Daily)
│   ├── gl_details_expense.sql  # O&M transactions (Daily)
│   └── gl_details_energy.sql   # Fuel transactions (Daily)
│
├── aligne/             # Aligne Fuel Management
│   ├── README.md       # Export info
│   ├── coal_purchase_consumed.sql  # Monthly coal flow (Daily)
│   ├── coal_ending_inventory.sql   # Ending inventory (Daily)
│   └── coal_quality.sql            # Coal quality (Weekly)
│
└── filesystem/         # Excel/File-based sources
    ├── README.md       # File paths
    ├── fuel_model_tabs.txt     # Tabs to extract
    └── contracts_template.txt  # Contract fields needed
```

---

*Document created: December 2024*  
*Last updated: December 2024*
